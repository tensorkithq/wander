# Architecture — The Body (local FastAPI hub)

**Date:** 2026-05-29 · **Status:** canonical · **Pairs with:** `architecture-mind.md`
**Surface spec:** `../yugo/openapi.yaml`

## One line
The **body** is a single light FastAPI on the LAN computer that *is* Yugo's nervous system: it holds
the WebRTC link to the dog, owns robot state, executes all control locally, serves the app, and runs
the agent loop — but **delegates every "think" step to the mind (cloud)**. Body = I/O + control +
fast loop. Mind = intelligence. (See `architecture-mind.md`.)

## Why it lives local (non-negotiable)
The Go2 Air's WebRTC is **`LocalSTA`** — it only accepts a peer on its own wifi. So the body MUST run
on a machine on the dog's LAN. It stays **light** (`unitree_webrtc_connect` + FastAPI + HTTP clients —
**no torch, no models, no DimOS perception modules**), so a resource-constrained laptop runs it fine.
A $60 Pi can replace the laptop with no code change.

## Responsibilities (what runs in the body)
- **Robot link** — WebRTC `LocalSTA` to Yugo; holds the connection, reconnects on drop.
- **Control execution (local, LAN-fast):** velocity (`/cmd_vel`), tricks (`/trick` via `SPORT_CMD`),
  LED (`/led` via the VUI topic), `/dance`, `/breathe`, `/stop`.
- **Reflex / safety (must be local):** deadman watchdog (auto-stop on stale command), velocity
  clamps, global stop, "clear-space" gating for tricks.
- **State aggregation:** `/ws/state` push (battery, pose/IMU, mode, mood, detections) — merging
  robot telemetry with results returned by the mind.
- **Media:** camera out to clients — currently MJPEG on the deprecated WebBridge; the canonical plan
  is the `/feed` WebRTC relay on the hub (designed — see
  `../docs/plans/2026-05-29-webrtc-feed-relay-design.md`). Also samples frames to the mind for perception.
- **App contract:** the stable HTTP/WS API the Yugo app codes against (LAN, low latency).
- **Conversational brain (Realtime):** the body hosts the OpenAI **Realtime** session *in-process* —
  voice in → voice out **plus** tool calls that execute in-process against the controllers (no HTTP
  hop). The mind stays a thin STT/vision context wrapper. `POST /agent/say` is the **text-only
  fallback** into the same persona + tool layer. (See `module-realtime-session.md`.)
- **Wand ingest:** `/sensor` accepts the phone's magnetometer/IMU/gesture readings → feeds mood/music.

## What the body does NOT do (delegated to the mind)
- LLM reasoning → mind (OpenAI).
- Vision/perception → mind (sampled frames out, detections/scene back).
- Voice audio (STT/TTS) → **app-side** (Deepgram in, ElevenLabs out); the body carries *text* only.
- Heavy/generative music → mind (ElevenLabs), streamed/triggered.

## Data flows
```
RN app ──LAN HTTP/WS──▶ BODY (FastAPI) ──WebRTC LocalSTA──▶ Yugo     (control: local, fast)
      Realtime brain IN body ◀──────────────▶ OpenAI Realtime (voice+tools; /agent/say = text fallback)
                          │  sampled frames    ─────▶ MIND: perception (detections/scene)
                          │  mood/music cue    ─────▶ MIND: ElevenLabs (music gen)
RN app ──direct──▶ Deepgram STT / ElevenLabs TTS                      (voice audio: app-side)
```

## Build state (seed → target)
- **Implemented (2026-05-29):** the body lives in `yugo/` — `main.py` (FastAPI + lifespan, with a
  `YUGO_NO_ROBOT` offline mode), `routers/` + `controllers/` covering health/discovery, expressive
  actions, keyboard nav + deadman teleop (`MotionController`), `/state`, and owners/moods persistence.
  Real HTTP test suite in `../tests/` (`uv run pytest`); robot utilities in `../utils/`.
- **Deprecated:** `yugo/bridge/` (`WebBridge`: MJPEG + `/cmd_vel` + deadman on :5555) — teleop/deadman
  are superseded by the hub; only its camera MJPEG has no hub equivalent yet. (The earlier
  `fastapi/validate_api.py` connection-validator seed is gone, folded into the hub.)
- **Target:** the full hub surface in `../yugo/openapi.yaml` — control + state + agent + sensor +
  audio-trigger endpoints, with the conversational brain as a body-hosted **Realtime** session
  (`/agent/say` = text fallback) and the mind a thin STT/vision wrapper. Feature specs: `module-*.md`.
  Phased order: **P1** `/feed` + `/ws/state` (retire the bridge) → **P2** Realtime session + `/mode`
  → **P3** modes (personal/friend/find/wand) → **P4** meditation (`/breathe` + `/led`).

## Hard-won constraints (from live testing 2026-05-28/29)
- **Tricks need a precondition:** expressive moves (e.g., `WiggleHips` 1033) are ignored unless Yugo
  is upright; gate them behind an auto-`BalanceStand`. `Hello` (1016) works from most states.
- **WebRTC data channel can drop** mid-session and does NOT self-heal; `/healthz` must reflect the
  **live channel state** (not just the initial handshake) and the body must **auto-reconnect**.
- **`ok` ≠ executed:** publishing a `SPORT_CMD` returns success even if the dog ignores it (no
  execution ack). State/telemetry, not the publish result, is the source of truth.

## Reliability (cloud is load-bearing for intelligence)
The body must **degrade gracefully** if the mind/network is unreachable: keep reflex/deadman + a
safe local command set (stand/sit/stop) so a cloud blip never strands Yugo mid-demo.

## Tech
`unitree_webrtc_connect` (`UnitreeWebRTCConnection`, `SPORT_CMD`, `RTC_TOPIC["SPORT_MOD"]`, VUI for
LED) + FastAPI/uvicorn + `httpx`/websockets to the mind. Runs in the repo `.venv`. `ROBOT_IP` (DHCP —
re-discover per session). No torch.
