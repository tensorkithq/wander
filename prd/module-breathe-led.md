# PRD — Module: Breathe + LED (Meditation Primitives)

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `../yugo/openapi.yaml` (`POST /breathe`, `POST /led`, `POST /mode`), Phase 2 Realtime session

## Objective
Deliver the body-side motion and light primitives for **meditation mode** (Phase 4 — "Calm"):
a slow "breathing" body-height oscillation and a calm front-lamp color. These primitives are
driven during meditation by the body's own OpenAI Realtime session, which speaks timed guided
prompts ("Breathe with Yugo... in... out") and fires `/breathe` and `/led` as **in-process tool
calls** — no mind, no HTTP hop. This closes the demo arc: see → talk → cast spells → find →
**Yugo guides you to relax**.

## Scope
Two endpoints on the hub (`:8080`, `ControlRouter`) plus the meditation behavior of the Realtime
session that orchestrates them.

- `POST /breathe {on, rate}` — toggle a slow, low-amplitude vertical body-height oscillation.
  `on:true` starts breathing at `rate` cycles/min (1–30); `on:false` stops. No locomotion.
- `POST /led {color|effect}` — set the front lamp via the VUI topic. Meditation driver: calm deep
  indigo, slow pulse. (Also generally useful for mood color and Ghost strobe; the meditation calm
  color is the case that drives this module.)
- **Meditation orchestration** in the Realtime session: a meditation personality/prompt set that
  emits timed spoken guidance and issues `/breathe` + `/led` tool calls synced to the breathing rate.

## Non-goals
- Locomotion of any kind during meditation (no `/cmd_vel`, no nav nudges).
- Mind involvement — meditation prompts come through the Realtime session voice, not GPT-4o vision
  or STT. The mind is not called in this mode.
- General `/led` palette/effects design beyond what meditation needs (Ghost strobe etc. live in their
  own modes; only referenced here for the shared contract).
- The Realtime session transport/wiring itself — that is Phase 2 (this module consumes it).
- App/client UI for entering meditation (the trigger is `POST /mode meditation`).

## Requirements

### `POST /breathe {on, rate}` — breathing oscillation contract
- Body: `{ on: boolean, rate?: number }`. `rate` is cycles/min, **1–30**, required-in-spirit when
  `on:true`, ignored when `on:false`. Out-of-range `rate` is clamped, not rejected.
- `on:true` starts a body-side oscillation loop that gently raises/lowers body height in a smooth
  sinusoid at `rate` breaths/min. `on:false` (and `POST /stop`) ends it and settles to the neutral
  upright height.
- **Low-amplitude vertical motion only.** No yaw, no translation. The oscillation runs as a body-side
  routine (like the planned `/dance` routine) until explicitly stopped.
- Requires an upright stance — the body gates breathing behind an auto-`BalanceStand` precondition
  (hard constraint #1). If not upright, the body stands first, then begins oscillating.
- Returns `200 {ok:true}` on toggle; `503` when the WebRTC link is down (hard constraint #2). Per
  hard constraint #3, `ok:true` means the breathing routine was **started/published**, not that the
  dog visibly executed it — confirm via `/ws/state` pose telemetry.
- Idempotent restart: a second `on:true` with a new `rate` re-paces the existing oscillation rather
  than stacking loops.

### `POST /led {color|effect}` — lamp contract
- Body: `{ color?: string, effect?: string }`, `anyOf` color/effect (provide one). `color` is a
  CSS/hex string; `effect` is a named effect (e.g. `breathe`, `strobe`, `off`).
- Publishes to the VUI topic over WebRTC. No motion, safe at any time.
- For meditation the driver is **calm deep indigo with a slow pulse** — e.g. `color: "#3a0ca3"` (or
  an indigo hex) combined with `effect: "breathe"` for a slow brightness pulse synced to the
  breathing cadence.
- Returns `200 {ok:true}`; `503` when disconnected.

### Meditation orchestration (Realtime session, body-hosted)
- `POST /mode meditation` switches the body into meditation mode (state machine) and selects the
  Realtime session's **meditation personality**: calm pacing, short guided lines, Yugo's third-person
  voice.
- On entry the session:
  1. Sets the calm LED (`/led` indigo slow pulse) as an in-process tool call.
  2. Starts breathing (`/breathe {on:true, rate}`) at a default calm rate (~6 cycles/min).
  3. Begins emitting **timed spoken prompts** ("Breathe with Yugo... in... and... out...") paced to
     the breathing rate.
- Tool calls execute **in-process** — `/breathe` and `/led` are direct function calls from the
  Realtime tool layer, no round-trip to the mind (per ROADMAP Phase 4: "tool calls: /breathe, /led
  triggered by the Realtime session in-process").

### Breathing-rate ↔ prompt-timing sync
- The breathing `rate` (cycles/min) is the **single source of truth** for pacing. The Realtime
  session derives prompt timing from it: one breath cycle = one "in / out" guidance pair, so the
  spoken "in..." lands on the inhale (height rising) and "out..." on the exhale (height falling).
- At the default ~6 cycles/min, that is a ~10 s cycle (~5 s in, ~5 s out). If the session changes
  `rate` mid-session, prompt cadence and LED pulse follow the same rate — no second timer to drift
  out of phase.
- The LED slow pulse, body oscillation, and spoken prompts all key off the one `rate` value so motion,
  light, and voice stay in phase.

## Safety
- **Low-amplitude, clamped motion.** Body-height oscillation amplitude is bounded to a gentle, safe
  envelope; like all motion paths it stays clamped and deadman-guarded. No locomotion velocity is ever
  commanded by breathing.
- **BalanceStand precondition** (hard constraint #1) — breathing only runs from an upright stance; the
  body auto-stands before oscillating.
- **`POST /stop` ends breathing immediately** — the always-available panic stop cancels the breathing
  routine and zeroes motion, exactly as it cancels any routine. Mode change away from `meditation`
  also stops breathing and reverts the LED.
- **Strobe sparingly (photosensitivity).** The meditation LED is a *slow* pulse, never a strobe. The
  `/led` strobe effect is a different-mode capability and must be used sparingly per the openapi safety
  note; meditation never invokes it.
- `503` on disconnect for both endpoints; the body stays safe (reflex/deadman keep running) if the
  Realtime session or link drops mid-meditation.

## Dependencies
- **VUI topic** over WebRTC for the front lamp (`/led` publish path) — exact topic/payload TBD.
- **Body-height control** over WebRTC LocalSTA — the mechanism `/breathe` oscillates (SPORT_CMD
  height/`BodyHeight`-style control or a pose loop on the Go2 Air).
- **Realtime session module** (Phase 2) — hosts the meditation personality, the timed prompt loop, and
  the in-process `/breathe` + `/led` tool definitions.
- **Mode state machine** (`POST /mode`, Phase 2) — `meditation` mode entry/exit drives this module's
  start/stop and LED revert.
- `BalanceStand` precondition gate and the clamp/deadman infrastructure (M0, done).

## Success criteria
- `POST /breathe {on:true, rate:N}` makes the body visibly breathe (smooth low-amplitude height
  oscillation) at the configured rate; `on:false` and `/stop` end it cleanly back to neutral upright.
- `POST /led` sets the front lamp to a calm deep indigo with a slow pulse in meditation.
- Entering `meditation` mode delivers **timed guided prompts in Yugo's voice** ("Breathe with
  Yugo... in... out") synced to the breathing cadence.
- Breathing motion, LED pulse, and spoken prompts stay in phase off the single `rate` value.
- Clean exit on `POST /stop` or mode change: breathing stops, LED reverts, no stuck routine, link-down
  leaves the body safe.

## Open questions
- **Body-height oscillation mechanics on the Go2 Air.** Is there a `BodyHeight`/pose SPORT_CMD that
  accepts a continuous height target, or must breathing be synthesized as a low-rate pose loop? What is
  the safe amplitude/rate envelope, and does the Air honor sub-stand height changes while balancing?
- **VUI LED topic specifics.** Exact `RTC_TOPIC` name, payload schema (RGB vs named effect), whether the
  lamp supports a hardware "breathe"/pulse effect or whether the slow pulse must be driven from the body
  by ramping color/brightness on the breathing timer.
