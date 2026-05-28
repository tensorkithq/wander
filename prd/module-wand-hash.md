# PRD — Module: Wand Hash (deterministic spell-casting)

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `POST /sensor` ingest (`SensorReading`, openapi.yaml), the trick execution path (`POST /trick/{name}` + `GET /tricks`), ROADMAP Phase 3 (Wand mode)

## Objective
Turn a phone gesture into a robot trick, deterministically. The user holds a button, sweeps the phone through a motion, releases. The magnetometer **trace** for that hold is sent to the body, which normalizes it, extracts features, hashes it to a bucket, looks the bucket up in a trick table, and fires the mapped `SPORT_CMD` move on Yugo.

This is **body-only computation**. No AI, no mind call, no cloud round-trip. The whole point is that the *same gesture always produces the same trick* — a repeatable, learnable spell vocabulary.

## Scope
A single body-side endpoint plus the hash engine behind it. Runs in-process in the FastAPI hub (port 8080), in the same process that holds the WebRTC link and owns the trick path.

- `POST /sensor/spell` — receives the raw magnetometer trace for one hold, runs the pipeline, fires the matched trick, returns what it matched.
- Hash engine: normalize → feature-extract → hash → bucket lookup. Pure function of the trace; no state, no clock, no randomness.
- Trick table: bucket index → `SPORT_CMD` move name (one of `GET /tricks`).

This is distinct from the existing `POST /sensor` (continuous wand ingest for sonification/mood). `/sensor` is a streaming single-reading reaction channel; `/sensor/spell` is a discrete one-shot gesture→trick mechanic.

## Non-goals
- **No AI.** No model inference, no learned classifier, no embedding similarity. Hashing is fixed deterministic math.
- **No mind involvement.** No call to expressmind, no network hop. `x-execution: local` end to end. A mind outage has zero effect on spell casting.
- **No gesture *recording* on the body.** The client owns sampling and button state; the body only receives the completed trace.
- **No magnitude-band mapping.** Rejected by the earlier design: only 3–4 reliable bands, mushy transitions between them, and raw field magnitude drifts with location/orientation. Pattern/trace hashing supersedes it — it is drift-invariant (normalized against the start reading) and yields far more distinct spells.
- **No new movement primitives.** Spells map onto existing `SPORT_CMD` tricks; this module does not define new robot motions.

## Mechanic (end to end)
1. **Client, button down** → starts recording magnetometer samples at ~50 Hz.
2. **User moves the phone** through a gesture (sweep, circle, thrust, wiggle, …).
3. **Client, button up** → stops recording, POSTs the accumulated trace to `POST /sensor/spell`.
4. **Body normalizes** the trace: resample to a fixed length, zero-mean each axis against the starting reading (kills baseline/offset drift).
5. **Body extracts features**: direction changes (sign flips per axis), peak count/positions, dominant axis, coarse shape signature.
6. **Body hashes** the feature vector to a bucket index (quantize → stable hash → modulo bucket count).
7. **Body looks up** the bucket in the trick table → a `SPORT_CMD` move name.
8. **Body fires** the trick over WebRTC (same path as `POST /trick/{name}`), returns the matched bucket + move.

## Requirements

### R1 — Trace ingest (`POST /sensor/spell`)
- Request body: a `MagTrace` — an array of magnetometer samples for one button-hold, each `{x, y, z}` (µT) plus a per-sample timestamp (epoch seconds, float), and a `source` id consistent with `SensorReading`.
- Reuse the existing `Vector3` schema for each sample. Timestamps may be a parallel `ts: number[]` array or carried per sample; pick one and document it (see open questions — phone vs body hashing affects this).
- Validation: reject (`422`) an empty trace, a trace below a minimum sample count (too short to be a gesture), or a trace whose total duration is implausibly long. Bound the maximum accepted sample count to cap work and payload size.
- The endpoint is `x-execution: local`. It does no mind call.

### R2 — Normalization (drift-invariant)
- **Resample** the trace to a fixed length `N` (e.g. 64 samples) by time-uniform interpolation, so cadence jitter and hold duration do not change the feature vector.
- **Zero-mean against the start**: subtract the first (or first-few-sample average) reading per axis, so the spell depends on the *shape of the motion*, not the absolute field — this is what makes it baseline-drift-invariant and location-independent.
- Optionally scale-normalize per axis so a big slow sweep and a small fast sweep of the same shape hash alike. Flag the exact normalization constants as fixed and versioned — changing them changes every spell.

### R3 — Feature extraction
- From the normalized trace, compute a compact, quantized feature vector. Candidate features: per-axis direction-change count (zero-crossings of the derivative), peak count and rough positions, dominant axis (largest-variance axis), and a coarse per-axis shape signature.
- Features must be **quantized** (binned) before hashing so that small natural variation in the same gesture lands in the same bins. Bin edges are fixed constants.
- The feature stage is a pure function: same normalized trace → same feature vector, on every machine, forever.

### R4 — Hashing → bucket
- Hash the quantized feature vector with a **stable, explicit** hash (e.g. FNV-1a / fixed seed) — **not** Python's salted `hash()`, which varies per process. Modulo into `BUCKET_COUNT` buckets.
- Determinism is the hard property: identical input bytes → identical bucket, across processes and restarts. This must be covered by a test that pins known traces to known buckets.

### R5 — Trick table (bucket → move)
- A table mapping each bucket index → a `SPORT_CMD` move name drawn from `GET /tricks` (e.g. bucket 3 → `Dance1`, bucket 7 → `WiggleHips`).
- Every mapped move name must be validated against the `SPORT_CMD` table at load time; an unknown name is a startup error, not a runtime `404`.
- Unmapped buckets resolve to a defined no-op / safe-default (see open questions on collisions).
- Whether the table ships pre-mapped or is user-bindable is an open question (below); the schema and lookup must support both without an endpoint change.

### R6 — Firing the trick
- On a match, publish the mapped `SPORT_CMD` over WebRTC using the existing trick execution path (the `POST /trick/{name}` mechanism) — one source of truth for trick firing; do not duplicate publish logic.
- Inherits the trick contract verbatim: `ok` means PUBLISHED, not executed (constraint #3); expressive moves are gated behind an auto-`BalanceStand` (constraint #1); requires the live link or returns `503` (constraint #2).

### R7 — Response
- On success: `{ ok: true, bucket: <int>, move: <string>, api_id: <int> }` — the matched bucket and the published move (mirrors `TrickResult` plus the bucket).
- `422` for an invalid/too-short trace; `503` when the robot link is down; a defined response for a bucket that maps to no trick (no-op, not an error).

## Safety
Firing a spell **moves the robot** — same exposure as `POST /trick/{name}`, so it inherits the same hard gating, no exceptions:
- **Clear-space acknowledgement.** Spells must be gated behind the client "clear-space" flag, exactly as tricks are (laptop-bridge PRD Safety). A spell is a trick trigger by another name.
- **BalanceStand precondition** (constraint #1): expressive moves are ignored unless upright; the body auto-`BalanceStand`s before firing.
- **Velocity clamps + deadman** remain in force on every motion path; `POST /stop` overrides and cancels.
- **No surprise moves from malformed input.** A too-short, empty, or out-of-bounds trace must `422` and fire nothing — never fall through to a default trick.
- The trick is the *only* side effect: no locomotion command is issued by this module itself.

## Dependencies
- The existing **trick / `SPORT_CMD` execution path** (`POST /trick/{name}`, the `RTC_TOPIC["SPORT_MOD"]` publish, the auto-`BalanceStand` gate) — reused, not reimplemented.
- `GET /tricks` — the authoritative move-name table used to validate the trick table at load.
- The WebRTC `LocalSTA` link (constraint #2) and the body's clear-space flag.
- `Vector3` schema (openapi.yaml) for samples; `SensorReading.source` convention.
- No dependency on the mind, the Realtime session, or any network service.

## Success criteria
- The **same gesture always fires the same trick** — repeated casts of one motion land in one bucket → one move, across process restarts and across machines. (Pinned-trace determinism test passes.)
- Distinct gestures (sweep vs circle vs thrust vs wiggle) reliably land in *different* buckets in hand testing.
- Baseline drift is invariant: starting the same gesture in a different magnetic environment / phone orientation still hashes to the same bucket (start-zeroing works).
- A too-short or empty trace returns `422` and fires nothing.
- A valid spell publishes its mapped move and returns the bucket + move; constraints #1/#2/#3 all hold (gated, `503` offline, `ok`≠executed).
- The hash engine is a pure function with no mind call and no robot traffic of its own.

## Open questions
- **Pre-mapped vs user-bindable spells.** Ship a fixed bucket→trick table, or let the user bind "cast this gesture, then pick the trick"? Binding needs persistence (SQLAlchemy, per the M0 stack) and a bind endpoint; pre-mapped is simpler for the demo. Lookup/schema should support both regardless.
- **How many distinguishable gestures?** What `BUCKET_COUNT` and feature set give reliably *separable* spells in practice — i.e. how many distinct motions a person can perform repeatably without collisions? Needs hand-testing to set bin edges and bucket count.
- **Hash collision handling.** Two different gestures can hash to one bucket (same trick) and one gesture can occasionally drift across a bin edge (different trick). Define the policy: accept collisions as "spells that share a trick," tune bins to minimize edge-straddling, and decide what an unmapped bucket does (no-op vs nearest-mapped).
- **Where does hashing run — phone or body?** ROADMAP allows `POST /sensor/spell` to receive *either* the raw trace *or* a pre-hashed bucket. Body-side hashing keeps determinism in one audited place and a thin client; phone-side cuts payload and latency but forces the hash algorithm + constants to be replicated and version-locked across client and body. Decide before fixing the request schema (raw `MagTrace` vs `{bucket}`).
