# PRD — Body Module: Personal Mode (emotional mirror)

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `module-camera-feed.md` (frame source),
`../yugo/openapi.yaml` (`/mode`, `/trick/{name}`, named actions, `/ws/state` `StateFrame.mood`)

## Objective
Make Yugo an **emotional mirror**. While Personal mode is active, the body samples camera frames,
sends them to the mind's GPT-4o vision wrapper, and reads back a **mood assessment** of the user's
face (smile → "happy", frown → "sad", surprise → "surprised", …). The body maps that mood to a
**bounded behavior intent** and executes it on the robot (happy → dance, sad → sit, surprised →
wiggle), and drives the `mood` color/label on `/ws/state` so the app's aura reflects what Yugo sees.

This module is the body-side **vision-driven behavior loop** in its simplest form: one face, one
mood, one reaction. It runs entirely inside the body process; the only cloud hop is the per-frame
vision call delegated to the mind.

Authoritative contract: `../yugo/openapi.yaml`. Personal mode reuses existing operations
(`/mode`, the named action routes, `/trick/{name}`, `/ws/state`) — it adds **no new endpoints**, only
a body-internal loop gated on `mode == personal`.

## Shared machinery (read this first)
Personal, **Friend** (`module-friend-mode.md`), and **Find** (`module-find-mode.md`) modes all run
the same underlying loop:

> **stream frame → ask mind → act on the result.**

They differ only in two places:
1. **Prompt** sent to the mind's vision wrapper (Personal: "read this face's expression"; Find:
   "locate <target>, return nav commands"; Friend: target identity + voice-nav context).
2. **Exit condition** (Personal: mode change / `/stop`; Find: mind returns "sit"; Friend: target
   reached).

**Design consideration — consolidation.** These three should likely converge into **one
vision-driven behavior engine** parameterized by a per-mode config (prompt template, result schema,
mood/behavior or nav mapping, exit predicate, sampling cadence). This PRD specifies Personal mode as
a standalone module so it can ship first, but every requirement below is written so the loop, the
debounce, and the safety envelope can be lifted into a shared engine without rework. See Open
questions.

## Scope
- A body-internal loop, active only while `mode == personal` (set via `POST /mode`).
- **Frame sampling** at ~1–3 fps from the hub's single WebRTC color-image source (the same source
  `/feed` serves — one source of truth, no second link; see `module-camera-feed.md`).
- **Mind vision call** per sampled frame: send the frame + a face-expression prompt to the mind's
  GPT-4o vision wrapper; receive a structured mood result.
- **Mood → behavior mapping** (table below): translate the mood label into a single bounded trick or
  posture, fired through the existing local control paths.
- **Mood propagation:** update the body's aggregated `mood {scalar, label, color}` so it ships on the
  next `/ws/state` `StateFrame`.
- **Debounce / hysteresis** so Yugo reacts to a *sustained* expression, not every frame.

## Non-goals
- New HTTP endpoints. Personal mode reuses `/mode`, the named actions, `/trick/{name}`, and
  `/ws/state`. (`/mode`'s enum currently lists `creature|ghost|hunt|scanner|music|meditation`;
  reconciling it with the roadmap's `personal|friend|find|wand|meditation` set is a state-machine
  concern, not this module's — see Dependencies / Open questions.)
- The vision wrapper itself (GPT-4o prompt, model, response schema) — that lives in the mind
  (`expressmind/`, Phase 1). This module is the body-side **consumer**.
- The MJPEG `/feed` stream and the WebRTC link (`module-camera-feed.md`).
- Voice, the Realtime session, navigation, and target pursuit — those belong to Friend/Find/Meditation.
- Multi-face / crowd handling. Personal mode mirrors **one** face (the most prominent / nearest).

## Requirements

### Frame streaming cadence
- Sample the latest decoded frame from the body's existing WebRTC color-image buffer at **~1–3 fps**
  (configurable; default ~2 fps). Per the hard constraints, the Air is camera-first and frames are
  sampled at ~1–3 fps — do **not** stream at video rate to the mind.
- Sampling reads the **shared latest-frame buffer**; it must not open a second WebRTC link or
  interfere with `/feed` or the reflex/deadman loop.
- One in-flight vision call at a time: if the previous call has not returned, skip the next tick
  (drop, don't queue) so latency can't back up the loop.
- The loop starts on entering Personal mode and stops on leaving it (mode change or `/stop` →
  see Safety). Before the first frame arrives, the loop idles.

### Mind vision call (`delegates-to-mind`)
- Per sampled frame, POST the frame (base64/multipart, matching the mind's vision contract) with a
  **face-expression prompt** to the mind's GPT-4o vision wrapper.
- Expected structured result: a mood assessment — at minimum a `mood`/`expression` **label** and a
  confidence (and optionally a valence scalar the body can reuse for `mood.scalar`).
- **Degradation:** if the mind is unreachable or errors, treat the tick as a no-op — keep the last
  mood, fire no behavior, and keep the reflex/deadman loop alive. Repeated failures must not strand
  Yugo mid-mode (mirrors the `502 MindUnreachable` posture of `/agent/say`).

### Mood → behavior mapping
The body maps the mind's mood label to **one** bounded reaction via existing control paths. Initial
table (tunable — see Open questions):

| Mood label (from mind) | Behavior intent | Control path | Mood color (→ `/ws/state`) |
|------------------------|-----------------|--------------|-----------------------------|
| `happy` (smile)        | dance           | `Dance1` via `/dance` (`/trick/Dance1`) | warm yellow `#ffcc44` |
| `sad` (frown)          | sit             | `Sit` via `/sit`            | cool blue `#5577cc` |
| `surprised`            | wiggle          | `WiggleHips` via `/wiggle`  | bright magenta `#ff44cc` |
| `neutral` / no face    | idle (no move)  | none                        | soft grey `#888888` |

- Reactions fire through the **same local control routes** the rest of the body uses, inheriting
  their safety (BalanceStand precondition, clamps, deadman, `503` when the link is down).
- A reaction fires only on a **debounced mood transition** (see below), not on every matching frame.
- The chosen mood also updates `mood {scalar, label, color}` on the next `StateFrame` — **one source
  of truth**: the aura color and the LED (if/when `/led` lands) read from the same body mood state,
  never a duplicated copy.

### Debounce / hysteresis
- Require the **same mood label across N consecutive ticks** (or sustained for a minimum dwell, e.g.
  ~1–2 s) before firing its behavior. Default N/dwell configurable.
- After firing, enforce a **cooldown** (e.g. ≥ the trick's execution time, ~1–3 s) before another
  reaction, so Yugo finishes a move before reacting again and doesn't twitch frame-to-frame.
- `neutral`/no-face resets toward idle but should not itself spam posture changes.
- Mood-color updates on `/ws/state` may track the smoothed mood continuously even when no behavior
  fires (color is cheap; motion is not).

### Integration with the mode state machine
- The loop is **owned and gated by the mode state machine**: it exists only while the active mode is
  Personal. Entering Personal starts the sampler + debounce state; leaving it (any other `/mode`, or
  a `/stop` that the state machine treats as exit/abort) tears the loop down cleanly and cancels any
  pending vision call.
- On exit, the body returns to its baseline safe state (reflex/deadman running; no residual sampling).
- Because Personal/Friend/Find share this lifecycle, the state machine should expose **one** "vision
  loop running for mode X" abstraction rather than three bespoke loops (consolidation hook).

## Safety
- **Reactions are bounded tricks/postures only** — `Dance1`, `Sit`, `WiggleHips`, etc. — fired
  through existing control routes. No raw locomotion, no `/cmd_vel` from this loop.
- All motion stays **velocity-clamped and deadman-guarded**; expressive moves keep the
  **BalanceStand precondition** (hard constraint #1) and return `503` while the link is down
  (constraint #2). `ok` ≠ executed (constraint #3) — confirm via `/ws/state`, not the publish result.
- **`POST /stop` overrides everything:** it zeroes motion immediately and the state machine treats it
  as a hard exit/abort of the Personal loop — no further reactions fire until the mode is re-armed.
- **Mind/network failure is safe:** a failed or slow vision call is a no-op tick; the body never
  blocks its reflex loop on the cloud, and never fires a stale behavior.
- Debounce + cooldown are themselves safety properties: they cap reaction frequency so Yugo can't be
  driven into rapid back-to-back moves by a flickering expression.
- `Sit` as the "sad" reaction is a stable, low-energy posture — a safe default for the most common
  fallback mood.

## Dependencies
- **Mind GPT-4o vision wrapper** (`expressmind/`, Phase 1) — frame in → structured mood/expression
  out. This module is its first body-side consumer.
- **Camera feed module** (`module-camera-feed.md`) — provides the single shared WebRTC color-image
  frame source; Personal mode samples from the same buffer, no second link.
- **Mode state machine** (`POST /mode`, Phase 2) — owns activation/teardown of the loop and the
  active-mode value reflected on `/ws/state`. (Needs the `personal` mode value; reconcile the
  OpenAPI `/mode` enum with the roadmap's mode set.)
- **Local control surface** (existing hub `ControlRouter`): `/dance`, `/sit`, `/wiggle`,
  `/trick/{name}`, `/stop`, plus `/led` (planned) for mood color on the lamp.
- **`/ws/state`** (Phase 1) — carries the `mood {scalar, label, color}` this module sets.
- Sibling modules sharing the loop: `module-find-mode.md`, `module-friend-mode.md`.

## Success criteria
- With Personal mode active, **Yugo sees a smile → dances** (fires `Dance1`).
- **Yugo sees sadness → sits** (fires `Sit`).
- A surprised face → wiggle (`WiggleHips`); a neutral/empty frame → no movement.
- The `mood` field on `/ws/state` tracks the perceived expression (label + color) live.
- Reactions fire on a **sustained** expression (debounced), not on every frame, and respect a
  cooldown between moves.
- `POST /stop` halts motion and exits the loop immediately; leaving Personal mode tears the loop down
  with no residual sampling.
- Mind unreachable / slow → no behavior fires, no crash, reflex/deadman keep running.

## Open questions
- **Consolidation with Find/Friend.** Should Personal, Find, and Friend ship as one vision-driven
  behavior engine with three mode configs (prompt, result schema, mapping, exit predicate, cadence)?
  Personal is the simplest case (no navigation, no voice) and the natural first slice — build it so
  the loop, debounce, and safety envelope lift cleanly into a shared engine.
- **Mood → behavior map tuning.** The label set and the mood→trick table are placeholders. How many
  moods does the mind return, and what's the canonical label vocabulary? Which tricks read best as
  "happy/sad/surprised"? Should valence (`mood.scalar`) modulate reaction intensity (e.g. big smile →
  full dance, faint smile → just a tail/LED change)?
- **Debounce tuning.** Right values for N consecutive ticks / dwell time / cooldown at ~1–3 fps so
  reactions feel responsive but not twitchy — needs live testing on the dog.
- **`/mode` enum reconciliation.** The OpenAPI `/mode` enum
  (`creature|ghost|hunt|scanner|music|meditation`) predates the roadmap's
  `personal|friend|find|wand|meditation` set. Resolve the canonical mode names before wiring the loop.
- **Frame selection for multiple faces.** When more than one face is present, which drives the mood —
  nearest, largest bbox, or center-most? (Mind-side or body-side decision?)
- **Mood color source.** Does the mind return a color/valence, or does the body own the
  label→color table? Whichever it is, keep it single-sourced (the body's mood state feeds both aura
  and LED).
