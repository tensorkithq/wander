# PRD — Body Module: Find Mode (vision servoing loop)

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `yugo/openapi.yaml` (`/cmd_vel`, `BalanceStand`, `Sit`, `/trick/{name}`, `/stop`, `/state`), `module-mode-state-machine.md` (registers as the `find` mode), `module-camera-feed.md` (frame source), Phase 1 mind GPT-4o Vision wrapper

## Objective
Make Yugo autonomously servo toward a named target. Given a target description ("find Sarah"),
the body runs a closed perception→action loop: stream a camera frame to the mind's GPT-4o vision
wrapper, get back the target's location plus **exactly two** nav commands (or `sit`), `BalanceStand`,
execute those two commands, return to a standing tilt/pan scan, and repeat — until the mind returns
`sit`, at which point Yugo sits and the loop exits.

The cadence is deliberate: **two nav commands per streamed frame, then tilt/scan until the next
command set comes back.** Pure frame-by-frame look→move→look. No map, no path, no odometry — Yugo
only ever knows what the last frame told it.

This is the fullest expression of the body's "stream frame → ask mind → act" machinery; Personal and
Friend modes are lighter variants of the same loop (see **Consolidation** below).

## Scope
A body-side behavior module in the FastAPI process (`yugo/`) that registers as the `find` mode's
`enter`/`exit` handler with the **mode state machine**. When `find` is active it owns one async
servoing loop:

1. Grab the latest decoded frame from the shared WebRTC frame source (the `/feed` buffer).
2. POST that frame + the target description to the mind's vision endpoint.
3. Receive `{target, commands[2]}` **or** `{target, action: "sit"}`.
4. `BalanceStand` (precondition gate), then execute the two nav commands as clamped, deadman-guarded
   `/cmd_vel` nudges through `MotionController`.
5. Return to a standing stance and tilt/pan to scan for the next frame.
6. Loop back to step 1; exit on `sit`.

The loop never publishes velocity directly — every step routes through the existing clamped,
deadman-guarded motion path. The target description is supplied when the mode is entered (e.g. via the
`POST /mode` payload or a follow-up call; exact wiring is an open question).

## Non-goals
- **No SLAM, no mapping, no localization.** No occupancy grid, no path planning, no odometry-based
  navigation. The Air has no LiDAR; perception is camera-first and frame-local. Yugo reacts to the
  current frame and forgets it.
- **No target re-identification across long gaps.** The mind decides target presence/position per
  frame; the body does not maintain a tracked-target state estimate between frames.
- Owning the mind's vision model or prompt — the mind is a stateless wrapper. This module owns the
  loop, the command shape it expects back, and the per-step motion execution.
- Owning the mode lifecycle — that is the mode state machine's job. This module only registers
  `enter`/`exit` and runs its loop while `find` is active.
- Driving the Realtime session. Find is body-driven; Realtime involvement is minimal/none.

## Requirements

### Loop state machine
The find loop is a small state machine, one iteration per streamed frame:

| State | What happens | Next |
|-------|--------------|------|
| `SAMPLE` | Grab latest frame from the shared WebRTC buffer | `ASK` |
| `ASK` | POST frame + target description to the mind vision endpoint | `ACT` on commands, `DONE` on `sit`, `SCAN` on error/no-result |
| `ACT` | `BalanceStand`, then execute the two returned nav commands as clamped nudges | `SCAN` |
| `SCAN` | Return to stand; tilt/pan to widen the next frame's view | `SAMPLE` |
| `DONE` | `Sit`; loop exits, mode stays `find` (or returns to default — open question) | — |

- The loop is a single async task started in `enter(find)` and cancelled in `exit(find)`.
- Exactly one iteration is in flight at a time — no overlapping frames or command sets.

### The two-commands-per-frame contract
- The mind returns **exactly two** nav commands per frame, or a single `sit`.
- Each command is `{action, steps}` where `action ∈ {forward, back, turn_left, turn_right}`
  (strafe optional — open question) and `steps` is a small positive integer count of timed nudges.
- The body translates each command to a clamped `/cmd_vel` nudge sequence: a `forward`/`back` step is
  `±vx` held for the deadman window; `turn_left`/`turn_right` is `±wz` held for the window. `steps`
  re-issues the nudge that many times within its window so the dog keeps moving (the deadman zeroes it
  between if a step is missed — see Safety).
- Two commands → executed in order (e.g. `[{turn_left,1},{forward,2}]` = nudge yaw once, then drive
  forward for two nudge windows).
- A malformed command set (not exactly two, unknown action, non-positive steps) is rejected: the body
  does not move on that frame and transitions to `SCAN` to fetch a clean frame.

### BalanceStand ↔ tilt/scan alternation
- Before executing nav commands the body issues `BalanceStand` (hard constraint #1: expressive/move
  commands are ignored unless upright; this also gates the nav nudges into a known stance).
- After the two commands complete, the body returns to a standing stance and performs a **tilt/pan
  scan** to present a fresh, wider view for the next frame.
- This alternation — **move on the command frame, scan between frames** — is the core rhythm. The
  body is either executing two commands or scanning; it is never doing both.
- How tilt/pan is achieved on the Go2 Air is an open question (see below) — it has no pan/tilt head.

### Sit exit condition
- When the mind judges the target close/centered it returns `sit` (instead of two commands).
- On `sit` the body fires the `Sit` SPORT_CMD (`api_id 1009`) via the existing action path and the
  loop exits cleanly (task completes, no further frames sampled).
- `sit` is the **only** success exit. Other exits (mode switch, `/stop`) are handled as aborts, not
  "found" (see Safety).

### What the mind returns
The mind vision endpoint receives `{frame, target_description}` and returns one of:
- **Pursue:** `{ target: {found: true, bbox|center, ...}, commands: [ {action, steps}, {action, steps} ] }`
- **Found:** `{ target: {found: true, centered: true}, action: "sit" }`
- **Lost:** target not in frame — handling is an open question (scan-in-place vs widen vs give up).

The mind is stateless: it sees only the current frame + description and returns the next two moves.
All loop state lives in the body.

## Safety
- **All motion is clamped and deadman-guarded.** Every nav command becomes a `/cmd_vel` nudge through
  `MotionController` — `vx`/`vy` clamped to ±0.6 m/s, `wz` to ±1.2 rad/s, each nudge honored only
  within the deadman window (default 0.5 s) then auto-zeroed. The find loop never bypasses this path
  and never publishes raw velocity.
- **Autonomous motion needs clear-space gating.** Find drives the dog on its own with no human in the
  control loop, so it must require a client "clear-space" acknowledgement before the servoing loop is
  allowed to move (same gate as tricks). Without it, the loop may scan but must not translate.
- **`POST /stop` aborts the loop instantly.** The panic stop zeroes motion immediately and must abort
  the find loop's in-flight step (cancel the current nudge sequence / pending mind call) — it does not
  wait out the deadman window or finish the current command pair. `/stop` outranks the loop.
- **The loop must not run away if the mind is slow or unreachable.** Each mind call has a timeout; on
  timeout/`502`/error the body does **not** execute stale or guessed commands — it holds position
  (deadman zeroes any residual velocity) and either retries the frame or transitions to `SCAN`. A
  slow mind means Yugo waits, never drifts. Because each nudge self-expires at the deadman window, a
  hung loop decays to a safe stop on its own rather than driving open-loop.
- **Mode teardown is safe.** `exit(find)` cancels the loop task and lets the deadman zero any residual
  velocity; the dog is never left drifting because the loop was killed mid-step.

## Dependencies
- **Mind GPT-4o Vision wrapper** (expressmind, Phase 1) — the endpoint that takes frame + target
  description and returns the two nav commands or `sit`. Stateless.
- **Camera feed module** (`module-camera-feed.md`, `/feed`) — the shared WebRTC color-frame source.
  Find samples the same latest-frame buffer; it must not open a second WebRTC link.
- **Mode state machine** (`module-mode-state-machine.md`) — Find registers as the `find` mode's
  `enter`/`exit` handler; the machine starts/stops the loop and guarantees only one mode's loops run.
- **Motion execution path** — `MotionController` and the reflex teleop routes (`/cmd_vel`, and by
  extension `/up`/`/down`/`/left`/`/right`) for the clamped, deadman-guarded nudges.
- **`BalanceStand`** (`/trick/{name}` / the upright gate) and **`Sit`** (`/sit`, `api_id 1009`) — the
  stance and exit actions.
- **`POST /stop`** — the abort path.

## Success criteria
- Given a target description, entering `find` starts the servoing loop and Yugo visibly servos toward
  the target: each streamed frame yields two nav nudges, with a tilt/pan scan between frames.
- When the target is close and centered, the mind returns `sit`, Yugo sits, and the loop exits — the
  end-to-end "find a person and sit when found" behavior from the roadmap (Phase 3, Find success
  criterion).
- Every move during the loop is clamped and deadman-guarded; `GET /state` shows the deadman zeroing
  between nudges.
- `POST /stop` at any point halts the dog immediately and aborts the loop.
- A slow/unreachable mind never causes the dog to drive open-loop: it holds/scans and the deadman
  keeps it safe.
- Switching out of `find` via `POST /mode` stops the loop cleanly with no residual motion.

## Consolidation (design consideration)
Personal, Friend, and Find modes all run the same skeleton: **stream a frame → ask the mind → act on
the result.** They differ only in three configurable dimensions:

| Mode | Prompt to the mind | Exit / loop condition | Command shape returned |
|------|--------------------|-----------------------|------------------------|
| **Personal** | "read this face's expression/mood" | Continuous (mirror, no terminal state) | mood label → trick/posture/LED |
| **Friend** | "where is [person]?" + voice-supplied directions | Until the companion is reached | step-nav parsed from voice + vision target ID |
| **Find** | "find [target]; return its location + 2 nav commands or sit" | Until the mind returns `sit` | exactly two `{action, steps}` nudges, or `sit` |

This strongly suggests a single **vision-driven behavior engine** parameterized per mode: one loop
runner (sample → POST to mind → apply result through the clamped motion/trick/LED paths) with a
per-mode config supplying the prompt, the result→behavior mapping, the exit condition, and the
move/scan cadence. Find is the fullest expression (closed servoing with a terminal `sit`); Personal
is the same loop with a continuous mood-mirror mapping and no exit; Friend adds a voice channel into
the same loop. Building Find as a configurable engine rather than a bespoke loop would let all three
modes share one tested perception→action core. **Recommendation:** design the find loop's runner with
this generalization in mind even if Personal/Friend ship as thin wrappers later.

## Open questions
- **Frame rate vs motion latency.** At what cadence does the loop sample? A mind round-trip is
  ~0.5–3 s; the two nudges take ~1 s of motion. Does the body move-then-wait (block on the mind
  between command sets), or pipeline (scan while the next mind call is in flight)? Pipelining risks
  acting on a stale frame; blocking is safer but slower. Likely move→wait for v1.
- **Lost-target behavior.** When the mind reports the target is not in frame: scan in place (rotate to
  search), widen the tilt/pan sweep, hold, or give up after N misses and exit the loop? Needs a
  defined miss policy and a max-miss bound so the loop terminates.
- **How tilt/pan is achieved on the Go2 Air.** The Air has no pan/tilt camera head. Is "scan" a small
  in-place yaw (`±wz` nudge), a body-pitch/`BalanceStand` posture tilt, or a fixed forward view with
  the yaw doing the scanning? This determines what the `SCAN` state actually publishes — and it must
  stay on the clamped/deadman path.
- **Consolidation timing.** Build Find standalone now and refactor Personal/Friend onto a shared
  vision engine later, or design the engine up front and ship all three as configs? (See Consolidation.)
- **Target description wiring.** How is the target ("find Sarah") supplied — extended `POST /mode`
  payload, a dedicated `POST /find {target}`, or via the Realtime session? Out of scope for the loop
  mechanics but required to drive it.
- **`sit` exit aftermath.** After the target is found and Yugo sits, does the mode stay `find` (idle,
  loop ended) or auto-return to the default mode?
