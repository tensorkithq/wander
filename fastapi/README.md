# fastapi/ — Yugo robot/DimOS API

**All Python / robot-control API work lives here.** This is the FastAPI layer that connects to
Yugo (Go2 Air) over WebRTC and exposes the HTTP/WS contract the Yugo app codes against.

Distinct from `app/backend/` (Hono/Bun **TypeScript** — the app's general backend). Robot control
**must** be Python (DimOS / `unitree_webrtc_connect`), so it lives here, separately.

Runs inside this repo's `.venv` (where `dimos` + `unitree_webrtc_connect` are installed).

## Contents
| File | What |
|---|---|
| `validate_api.py` | No-auth connection validator — `curl /hello` → Yugo trick. Thin, no DimOS graph. |
| `web_bridge.py` | `WebBridge` DimOS module — MJPEG camera out + `/cmd_vel` teleop in, deadman + clamps. |
| `run.py` | Entrypoint: WebRTC connect (`--robot-ip`) + `WebBridge`. |
| `static/debug.html` | Browser debug client. |

Tests & utilities live outside this dir: no-robot harness `../scripts/smoke_bridge.py`,
standalone robot utilities `../utils/go2_teleop.py` and `../utils/go2_trick.py`.

## Run (Yugo on the floor, ~2 m clear)
```bash
cd /Users/0x/srv/dimos
# connection validator:
ROBOT_IP=192.168.203.75 .venv/bin/python fastapi/validate_api.py
#   curl -X POST localhost:8080/hello

# full bridge (camera + teleop):
.venv/bin/python fastapi/run.py --robot-ip 192.168.203.75 --port 5555
#   open http://localhost:5555/debug
```

## Scope (per the PRDs)
This is **Tier 2 — the laptop bridge** (`../prd/01-laptop-bridge-api.md`): robot I/O + reflex/safety
+ the agent (DimOS agentic, `OPENAI_API_KEY`) + perception calls (OpenAI vision / Replicate) +
the HTTP/WS contract for the app. Audio (Deepgram STT, ElevenLabs voice/SFX/music) is app-side; the
bridge carries text, not audio.
