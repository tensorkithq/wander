# PRD — Workstream 1: Laptop FastAPI Bridge

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `../yugo/` — the body/hub (`yugo.main`).
(The legacy `yugo/bridge/web_bridge.py` "bridge" this doc is named for is now **deprecated**; "bridge"
here = the body/hub. See `architecture-body.md` and `README.md`.)

## Objective
Be the **always-on local hub** between Yugo (Go2 Air) and everything else. It owns the single
WebRTC `LocalSTA` link to the dog and exposes one clean, **safe** HTTP/WebSocket API that the Yugo
app (and optionally the GPU skills server) code against to **perceive and control Yugo**.

This is the **integration contract** for the whole product. Get this stable and the app + GPU
server are just clients.

## Users / clients
- The **Yugo app** (primary client): camera, control, state, voice, wand ingest.
- The **GPU skills server** (optional): pulls frames/sensors, pushes mood/behavior back.
- A **browser debug client** (`/debug`, exists) for development.

## Scope
On the laptop, on the dog's LAN, reachable by the app over LAN or Tailscale. Single Python process
(DimOS modules + FastAPI/uvicorn). **Light install** (no torch/perception — that's the GPU).

## Non-goals
- Heavy perception / large models (→ GPU skills server, ws 3).
- Holding any state the design says lives elsewhere (mapping/nav — N/A on the Air).
- Public internet exposure without auth (LAN/Tailscale only for now).

## Requirements (objectives → endpoints)

### Already implemented (the hub — `yugo.main`)
- `POST /cmd_vel {vx,vy,wz}` — teleop; **velocity-clamped** (0.6 m/s, 1.2 rad/s), deadman-guarded.
- `POST /up`/`/down`/`/left`/`/right` — keyboard-nav timed nudges (deadman-backed).
- `POST /stop` — immediate zero (panic).
- **Deadman watchdog** (`MotionController`) — auto-stop on stale command (**0.5 s** window),
  observable at `GET /state`. (Safety-critical; keep.)
- `POST /trick/{name}` + friendly actions (`/hello`, `/wiggle`, `/heart`, `/sit`, `/standup`,
  `/standdown`, `/stretch`, `/dance`) — Go2 `SPORT_CMD` moves; catalog at `GET /actions`.
- `GET /healthz` (liveness + live connection), `GET /tricks`, `GET /state` (motion/deadman).
- _Deprecated (WebBridge, :5555):_ `GET /video_feed/color_image` MJPEG — the only camera path
  until `/feed` lands.

### To add — control
- `POST /routine {names:[...]}` — fire a *sequence* of `SPORT_CMD` moves (single moves are already
  done via `/trick/{name}` + the friendly actions).
- `POST /led {color|effect}` — front-lamp color via the VUI topic (mood color, Ghost strobe).
- `POST /mode {creature|ghost|hunt|scanner|music|meditation}` — set the active behavior mode.
- **`/dance` beat-sync** — `/dance` fires `Dance1` today; add `{bpm, style}` for beat-synced
  pose/height choreography ("Yugo dances to the music").
- `POST /breathe {on|off, rate}` — slow body-height oscillation for meditation mode.

### To add — perception / state out
- `GET /ws/state` (WebSocket) — push live telemetry at ~10–20 Hz:
  `battery`, `imu`/`pose`, `mode`, `mood` (scalar + label + color), `detections` (YOLO: labels +
  boxes + person count), `audio_level`. This drives the app's "aura."
- `GET /detections` — latest camera detections (snapshot form of the WS field).

### To add — agent (Yugo's brain) + voice routing
- **Agentic brain runs here.** The bridge embeds/launches DimOS `unitree-go2-agentic`
  (`export OPENAI_API_KEY`, `export ROBOT_IP`; NL→behavior via the OpenAI LLM). Camera-first on the
  Air — the blueprint's LiDAR/spatial-memory features are no-ops. Ref: `koolamusic/dimos` Go2 docs.
- `POST /agent/say {text}` — feed a recognized utterance (from the **app's Deepgram STT**) into the
  agent (the programmatic equivalent of the doc's `humancli`); returns Yugo's **reply text** +
  triggers behavior (move / trick / LED / mode). The **app** speaks the reply via **ElevenLabs TTS**.
- `POST /say {text}` — force a scripted line as a behavior cue + caption (broadcast on `/ws/state`).
  Audio playback is app-side (ElevenLabs).
- **Voice = app-side: Deepgram STT (ears) + ElevenLabs TTS (voice).** The bridge carries text, not audio.

### To add — wand ingest (the phone as a sensor node)
- `POST /sensor {source, magnetometer, accel, light, gesture, ts}` — ingest the phone's readings.
  Drives sonification, mode reactions (Yugo turns/flares toward a field), and music triggers
  (a `gesture:"wave"` starts/changes the track).

### To add — audio
- `POST /audio/play {style|seed}` / `POST /audio/stop` — trigger **ElevenLabs** soundscape/SFX/music
  (Yugo is mute on its own; sound plays on the app or laptop speaker). Music style also feeds
  `/dance`. Mood-driven music may be generated on the server brain and streamed; live-reactive wand
  tone is **local Web Audio in the app**, never an API.

## Safety (hard requirements)
- Deadman watchdog (exists) + velocity clamps (exists) on all motion paths, including `/trick`,
  `/dance`, `/breathe`.
- A global `POST /stop` that cancels any routine immediately.
- Tricks gated behind a "clear space" acknowledgement flag from the client.

## Dependencies
- DimOS `web` (FastAPI), `unitree` (WebRTC `GO2Connection`), `unitree_webrtc_connect`
  (`SPORT_CMD`, `RTC_TOPIC`), `sounddevice`/`expo-av`-side for audio, Deepgram SDK + API key.
- `ROBOT_IP` (DHCP — re-discover each session).

## Success criteria
- App can: see the camera, drive + stop, fire tricks/dance, read live state/mood, send wand data,
  make Yugo speak, and stream voice in — all over LAN/Tailscale, with the deadman keeping the dog
  safe.
- Runs light on the M2 Pro (no torch); reconnects cleanly when `ROBOT_IP` changes.

## Resolved decisions (2026-05-28)
- **Audio is app-side; bridge carries text.** Deepgram = **STT only** (app layer). ElevenLabs =
  Yugo's voice (TTS) + Sound Effects + Music. Live wand tone = local Web Audio. App: mic → Deepgram
  STT → `POST /agent/say` → reply text → ElevenLabs TTS. The bridge does **no** audio.
- **Brain = DimOS agentic mode with `OPENAI_API_KEY`** (`dimos run unitree-go2-agentic`), running on
  the bridge/laptop. Phase 1 keeps it local; the GPU skills server (ws3) is an optional later offload.

## Open questions
- Exact programmatic hook to inject text into the agent (wrap `humancli` vs a direct agent API) —
  confirm against `koolamusic/dimos` internals during build.
