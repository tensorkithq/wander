# Architecture — The Body (local FastAPI hub)

**Date:** 2026-05-29 · **Status:** canonical · **Pairs with:** `architecture-mind.md`
**Surface spec:** `../fastapi/openapi.yaml`

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
- **Media:** camera MJPEG out (`/video_feed/...`); samples frames to send to the mind for perception.
- **App contract:** the stable HTTP/WS API the Yugo app codes against (LAN, low latency).
- **Agent orchestration loop:** runs *here*, but each step calls the mind — `/agent/say` forwards an
  utterance to the cloud agent and applies the returned behavior + reply.
- **Wand ingest:** `/sensor` accepts the phone's magnetometer/IMU/gesture readings → feeds mood/music.

## What the body does NOT do (delegated to the mind)
- LLM reasoning → mind (OpenAI).
- Vision/perception → mind (sampled frames out, detections/scene back).
- Voice audio (STT/TTS) → **app-side** (Deepgram in, ElevenLabs out); the body carries *text* only.
- Heavy/generative music → mind (ElevenLabs), streamed/triggered.

## Data flows
```
RN app ──LAN HTTP/WS──▶ BODY (FastAPI) ──WebRTC LocalSTA──▶ Yugo     (control: local, fast)
                          │  POST /agent/say  ─────▶ MIND: OpenAI    (reply text + behavior)
                          │  sampled frames    ─────▶ MIND: perception (detections/scene)
                          │  mood/music cue    ─────▶ MIND: ElevenLabs (music gen)
RN app ──direct──▶ Deepgram STT / ElevenLabs TTS                      (voice audio: app-side)
```

## Build state (seed → target)
- **Seed (exists):** `fastapi/validate_api.py` (no-auth connection validator — `curl /hello` → trick;
  proven against the real Yugo), `fastapi/web_bridge.py` (`WebBridge`: MJPEG + `/cmd_vel` + deadman),
  `fastapi/run.py`. Tests in `scripts/`, robot utilities in `utils/`.
- **Target:** the full hub surface in `fastapi/openapi.yaml` — control + state + agent + sensor +
  audio-trigger endpoints, with the mind delegated behind `/agent/say` and the perception adapter.

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
