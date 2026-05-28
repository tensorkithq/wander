# PRD — Module: Mode State Machine

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `yugo/main.py` (app + routers), `yugo/openapi.yaml` (`POST /mode`, `/ws/state`)

## Objective
Be the backbone every behavior module plugs into. The mode state machine owns the body's single
active mode, exposes `POST /mode {mode}` to switch it, reflects it on `/ws/state`, and guarantees
that switching cleanly tears down the previous mode's loops before starting the next one's. Modes
condition perception loops, Realtime personality/tools, and LED/motion tendencies — but a mode
switch by itself never drives locomotion.

The mode set is the demo arc's five modes: **personal, friend, find, wand, meditation**.

## Scope
A body-side state machine in the FastAPI process (`yugo/`). One source of truth for the active
mode, owned by a `ModeController` (sibling to `MotionController`, started in `lifespan`). It:
- validates and applies mode transitions from `POST /mode`,
- starts/stops the per-mode input loops and Realtime configuration via a registered handler per mode,
- publishes the current mode into the `/ws/state` aggregate.

The behavior of each mode (vision servoing, voice-nav parsing, wand hashing, breathing) lives in the
per-mode modules. This module owns only the lifecycle: which loops are running, and clean handoff
between modes.

## Non-goals
- Implementing the per-mode behaviors themselves (Find servoing loop, wand hash engine, Personal
  vision mapping, Friend voice-nav, meditation breathing) — those are separate modules that register
  with this one.
- Driving locomotion. Motion always flows through the clamped, deadman-guarded `/cmd_vel` paths in
  `MotionController`. The mode machine never publishes velocity directly.
- Owning the Realtime session lifecycle. This module asks the Realtime session module to swap its
  active tool set / personality on a mode change; it does not open or host that session.
- Persisting mode across restarts (default boot mode is fixed; persistence is an open question).

## Requirements

### Mode enum
- The valid mode set is `personal | friend | find | wand | meditation`.
- `POST /mode {mode}` accepts only these values; anything else returns `422` (`ValidationError`).
- A single default boot mode is defined (proposed: `personal`).

### What each mode activates / deactivates
On entering a mode, the controller runs that mode's `enter` handler; on leaving, the previous mode's
`exit` handler runs first. Each handler governs three concerns: active Realtime tools/personality,
which input loops run, and LED palette / motion tendencies.

| Mode | Realtime personality / tools | Input loop(s) started | LED / motion tendency |
|------|------------------------------|-----------------------|-----------------------|
| **personal** | Reactive companion; expression-mirror tools | Vision streaming (~1–3 fps) → mood → trick/posture | Warm palette; expressive moves |
| **friend** | Voice-navigation prompt ("you are looking for [person]"); step-nav tool | Realtime voice-nav active; vision for target ID | Neutral palette; step-based nudges |
| **find** | (minimal Realtime; loop is body-driven) | Vision servoing loop (frame → 2 nav cmds → move → scan → repeat → sit) | Focused palette; scan tilt/pan |
| **wand** | None (deterministic, no AI) | Magnetometer trace ingest → hash → trick lookup | Spell palette; trick on cast |
| **meditation** | Calm meditation personality; timed spoken prompts | Breathe timing loop (body-height oscillation at `rate`) | Calm indigo, slow pulse |

- Entering a mode must NOT start any motion on its own. Loops that move (Find servoing, breathing,
  Friend nudges) still issue motion only through the clamped/deadman paths.

### Clean transitions
- A mode switch is: `exit(previous)` → swap Realtime config → `enter(next)` → publish new mode.
- `exit` MUST stop all loops the previous mode started before `enter` runs — e.g. stop the Find
  servoing loop, stop breathing, stop vision streaming, cancel any in-flight scan step.
- Transitions are serialized: a second `POST /mode` while one is in progress either waits or is
  rejected (no overlapping enter/exit, no two input loops running at once).
- Switching to the same mode is idempotent (no teardown/restart churn) or an explicit no-op.
- A failed `enter` must leave the body in a safe, known state (loops stopped, motion zeroed), not a
  half-started mode.

### State reflected in `/ws/state`
- The active mode is published in every `StateFrame` (`mode` field) at the stream's ~10–20 Hz cadence.
- The mode value updates the instant a transition completes, so clients see the switch immediately.

### OpenAPI enum update (required as part of this module)
The `openapi.yaml` `mode` enum is **stale**. It currently lists
`creature | ghost | hunt | scanner | music | meditation` in three places:
- `POST /mode` request body schema (`paths./mode.post.requestBody`),
- `POST /mode` `200` response schema,
- the `StateFrame.mode` schema.

All three MUST be updated to `personal | friend | find | wand | meditation`. The `ghost` example
under `POST /mode` must also be replaced with a valid mode. PRD `01-laptop-bridge-api.md` carries the
same stale list (`POST /mode {creature|ghost|hunt|scanner|music|meditation}`) and should be
reconciled to the demo-arc set.

## Safety
- **A mode switch does not move the dog.** Entering or leaving a mode never publishes a velocity; all
  locomotion stays on the clamped (`±0.6 m/s`, `±1.2 rad/s`), deadman-guarded path in
  `MotionController`.
- **Transitions stop in-flight loops safely.** `exit` must halt any moving loop (Find servoing,
  breathing, Friend nudges) and let the deadman zero residual velocity — the dog must not be left
  drifting because a loop was killed mid-step.
- **`POST /stop` overrides any mode.** The panic stop zeroes motion regardless of active mode and
  does not require a mode change.
- **Degradation.** If the Realtime session is down, a mode switch still succeeds for its body-side
  loops and LED; the Realtime personality swap is best-effort and the body stays safe
  (reflex/deadman keep running).

## Dependencies
- **MotionController** (`yugo/controllers/MotionController.py`) — all loop-driven motion routes
  through it; the mode machine never bypasses the clamp/deadman.
- **Realtime session module** (Phase 2) — the mode machine requests the active tool set / personality
  swap on transition; it does not own the session.
- **Per-mode behavior modules** that register `enter`/`exit` handlers and own their loops:
  - Personal — vision-streaming mood-mirror module.
  - Friend — Realtime voice-navigation module.
  - Find — vision servoing loop module.
  - Wand — magnetometer hash engine module (`POST /sensor/spell`).
  - Meditation — breathing module (`POST /breathe`) + meditation personality.
- **Mind vision endpoint** (expressmind) — consumed by the Personal / Friend / Find loops, not by
  this module directly.

## Success criteria
- `POST /mode {mode}` switches among `personal | friend | find | wand | meditation`; invalid values
  return `422`.
- Switching modes stops the previous mode's loops before the new mode's loops start — verifiable that
  exactly one mode's loops run at a time (e.g. leaving Find stops the servoing loop; leaving
  meditation stops breathing).
- The active mode appears in `/ws/state` and updates the moment a transition completes.
- A mode switch alone produces no locomotion; the dog only moves through clamped/deadman paths.
- `openapi.yaml` (and `01-laptop-bridge-api.md`) reflect the new five-mode enum in all locations.
- Realtime-down: mode switch still applies body-side loops/LED and the body stays safe.

## Open questions
- Default boot mode — `personal`, or an explicit `idle`/no-mode state until the first `POST /mode`?
- Should the active mode persist across body restarts (SQLAlchemy), or always boot to the default?
- Transition policy when a switch arrives mid-transition: queue-and-apply-last, or reject with a busy
  error?
- Does `wand` need a Realtime personality at all, or is it fully silent (no session interaction)?
- Should `POST /stop` force a mode exit (e.g. drop meditation breathing), or only zero motion and
  leave the mode active?
