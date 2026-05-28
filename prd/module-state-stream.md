# PRD — Module: State Stream (`/ws/state`)

**Date:** 2026-05-28 · **Status:** draft · **Phase:** 1 (M1) · **Builds on:** M0 `GET /state` (motion+deadman, exists)

## Objective
Push an **aggregated `StateFrame`** over a WebSocket at ~10–20 Hz. Each frame merges robot
telemetry (battery, pose/IMU, motion/deadman, connection) with mind-sourced fields (mood,
detections, person_count) that arrive asynchronously from the vision pipeline. This is the single
stream that drives any client's "aura"/state display. The synchronous `GET /state` from M0 stays —
it is motion+deadman only; this module is the richer **superset** push.

The pushed payload conforms to `StateFrame` in `yugo/openapi.yaml` (authoritative). `MoodState` and
`Detection` schemas are likewise authoritative; this module does not redefine them.

## Scope
- New WebSocket route `GET /ws/state` (upgrade) on the hub (port 8080), in `yugo/`.
- A state-aggregation layer that reads from the live telemetry sources each tick and merges in the
  latest mind-sourced fields, then serializes a `StateFrame`.
- A write-side intake for mind-sourced fields (mood, detections, person_count) so the vision tier
  can update them out-of-band at its own (slower) cadence. The intake is in-process — same hub
  process; the WS aggregator reads the last-known value.
- Per-connection push loop with a fan-out for multiple subscribers.

## Non-goals
- **No perception.** Detections/mood are produced by the mind (expressmind, ws3 / Phase 2–3); this
  module only *carries* the latest values, it never runs a detector.
- No control. Read-only stream — it never publishes motion, tricks, LED, or mode changes.
- No persistence of frames (the mood *memory* table under `/api/moods` is separate).
- No camera bytes — video is `/feed` (separate Phase 1 module); a frame carries detection metadata
  only, not pixels.
- No auth (LAN/Tailscale only, per the document-level `security: [{}]`).

## Requirements

### Frame contents (per `StateFrame`)
Robot-sourced (this tick, read live):
- `battery` — fraction 0..1, from robot telemetry over WebRTC.
- `pose` — `{x,y,z,roll,pitch,yaw}` body pose estimate.
- `imu` — `{ax,ay,az,gx,gy,gz}` linear accel + angular rate.
- `mode` — current behavior mode (`creature|ghost|hunt|scanner|music|meditation`); from the body's
  mode state (set by `POST /mode`, Phase 2). Defaults to `creature` until set.
- Motion/deadman + connection are sourced from `MotionController.state()` (the M0 source of truth:
  effective `vx/vy/wz`, `connected`). These are not first-class `StateFrame` fields in the current
  schema; carry `connected` and surface motion via the existing `GET /state` unless the schema is
  extended (see Open questions).

Mind-sourced (latest known, may lag the push rate):
- `mood` — `MoodState {scalar,label,color}`.
- `detections` — array of `Detection {label,bbox,confidence}`.
- `person_count` — integer ≥ 0.
- `audio_level` — 0..1 normalized ambient level (client/app-sourced or mind-sourced; carried, not
  computed here).

All fields are optional in `StateFrame`; a frame omits a field rather than inventing a value when
its source has never reported (e.g. no pose before the first telemetry packet, no detections before
the first vision result).

### Push cadence
- Target **10–20 Hz** steady push per connected client (config: `state_stream_hz`, default ~15).
- The robot-sourced fields refresh every tick at read time (cheap, in-memory snapshot — same model
  as `MotionController.state()` recomputing on read, so the deadman edge is always reflected).
- Mind-sourced fields refresh at the perception tier's own (slower, ~1–3 fps) rate; between updates
  the frame repeats the **last-known** value. Every pushed frame is complete — clients never have to
  stitch partial frames.
- Use a single shared aggregator + a monotonic tick; do not run an independent timer per socket that
  drifts. One source of truth, fan out to all subscribers.

### Merging mind-sourced fields
- The vision pipeline writes mood/detections/person_count into an in-process **latest-value store**
  (last-writer-wins, timestamped). Initial Phase-1 path: an internal setter the body calls when it
  receives a mind result; a future `/say`-style or mind-callback intake can target the same store.
- The aggregator reads the store each tick and stamps freshness; it never blocks on the mind.
- Mood here is the **live** aura value. It is independent from the `/api/moods` SQLAlchemy memory log
  (that's durable history; this is the current frame).

### Connection lifecycle
- On connect: optionally send one frame immediately (don't make the client wait a full tick).
- On disconnect / send error: drop the subscriber cleanly; never let one dead socket stall the
  aggregator or other clients.
- Multiple concurrent subscribers supported (app + debug client).

## Safety (hard requirements)
- **Read-only.** The stream has zero side effects on the robot. It publishes no `SPORT_CMD`, no
  velocity, no LED/mode change. It cannot move Yugo.
- It MUST NOT interfere with the motion publish loop or the deadman. Reading
  `MotionController.state()` is non-mutating and already lock-guarded.
- Degradation: when the WebRTC link is down, robot-sourced fields go stale/absent and `connected`
  reads false, but the stream keeps pushing (mode/mood/last-known) so the app's aura degrades
  gracefully rather than freezing. When the mind is down, mind-sourced fields go stale; the frame
  still flows. A read-only stream never needs `502`/`503` — it reflects, it does not command.

## Dependencies
- FastAPI WebSocket support (already in the stack); hub process (`yugo.main:app`, port 8080).
- `MotionController` (exists, M0) — motion/deadman/connection source of truth.
- WebRTC telemetry channel for battery/pose/IMU — the body must subscribe to the robot's telemetry
  topics. This subscription may not yet exist; if so it is part of this module's work (or stubbed to
  omit those fields until the Phase-1 telemetry migration lands). Per the openapi header, telemetry
  is the capability moving off the deprecated bridge onto the hub.
- The mind (expressmind, Phase 1+) as the upstream producer of mood/detections — out of scope to
  build here, but the latest-value store is the contract it writes to.
- `StateFrame` / `MoodState` / `Detection` schemas in `yugo/openapi.yaml` (authoritative).

## Success criteria
- `ws://<hub>:8080/ws/state` upgrades and pushes well-formed `StateFrame` messages at ~10–20 Hz.
- Each frame validates against the `StateFrame` schema; mood/detections fields match `MoodState` /
  `Detection`.
- Robot-sourced fields track live telemetry; `connected` flips with the WebRTC link state.
- Mind-sourced fields update when the vision tier writes a new value and otherwise repeat the last
  known value (no flicker, no partial frames).
- Multiple clients can subscribe simultaneously; a client disconnecting does not disrupt others or
  the push loop.
- Runs offline (`YUGO_NO_ROBOT=1`): stream still pushes, with robot-sourced fields absent and
  `connected:false` — usable for the test suite and app dev without a dog.

## Open questions
- **`StateFrame` schema gaps.** The schema has no explicit motion/deadman or `connected` field.
  Either extend `StateFrame` (preferred: add `connected`, and maybe an embedded motion block so the
  aura can show movement) or have clients keep polling `GET /state` for motion. Decide before build.
- **Backpressure.** If a subscriber is slow (can't drain at 15 Hz), do we drop frames (latest-wins,
  recommended for a state aura) or buffer? Pick latest-wins with a bounded/zero queue per socket so
  a slow client can never balloon memory or slow the aggregator.
- **Stale mind fields.** When mood/detections are older than some threshold, do we (a) keep emitting
  the last value silently, (b) decay it (e.g. shrink `person_count`/clear detections after N
  seconds), or (c) attach a freshness/`age_s` marker so the client decides? The schema has no
  freshness field today — resolving this may require a schema addition.
- **Push rate vs. `mode`/audio sourcing.** `mode` lands with Phase 2 (`POST /mode`); `audio_level`
  source (app-sent vs. mind-sent vs. local) is unsettled. Until then both default/omit.
- **Telemetry availability on the Air.** Confirm which of battery/pose/IMU the Go2 Air actually
  exposes over the WebRTC telemetry channel; omit fields the hardware doesn't report rather than
  fabricate zeros.
