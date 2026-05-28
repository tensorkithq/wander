# yugo/ — Yugo robot/DimOS API ("the body")

**All Python / robot-control API work lives here.** This is the FastAPI layer that connects to
Yugo (Go2 Air) over WebRTC and exposes the HTTP/WS contract the Yugo app codes against.
`openapi.yaml` is the authoritative surface contract.

Distinct from `app/backend/` (Hono/Bun **TypeScript** — the app's general backend). Robot control
**must** be Python (DimOS / `unitree_webrtc_connect`), so it lives here, separately. The package is
named `yugo` (not `fastapi`) so it doesn't shadow the pip `fastapi` package.

Runs inside this repo's `.venv` (where `dimos` + `unitree_webrtc_connect` are installed).

## Layout
| Path | What |
|---|---|
| `main.py` | FastAPI app: CORS, lifespan (WebRTC connect → `app.state.robot`), router wiring. |
| `config.py` | SQLite engine / `SessionLocal` / `Base`, plus settings loaded from `robot.yaml`. |
| `robot.yaml` | Robot connection + motion config (IP, timeout, clamps). No secrets. `ROBOT_IP` env overrides the IP. |
| `dependencies.py` | `get_db` (DB session) and `get_robot` (live WebRTC conn or 503). |
| `routers/` | HTTP routes by contract group: `SystemRouter` (health/tricks), `ControlRouter` (hello/trick/stop), `OwnerRouter` + `MoodRouter` (persistence). |
| `controllers/` | Business logic: `RobotController` (SPORT_CMD over WebRTC), `OwnerController`, `MoodController`. |
| `models/` | SQLAlchemy models: `OwnerModel`, `MoodEventModel`. |
| `schemas/` | Pydantic request/response schemas. |
| `alembic/` | Migrations (`alembic upgrade head`). Schema lives here, not in code. |
| `bridge/` | The DimOS teleop runtime — a *different* process from the structured app. `web_bridge.py` (MJPEG camera out + `/cmd_vel` teleop, deadman + clamps), `run.py` (entrypoint), `static/debug.html`. |
| `openapi.yaml` | Authoritative API contract (body vs mind, implemented vs planned). |

Tests & utilities live outside this package: no-robot harness `../scripts/smoke_bridge.py`,
standalone robot utilities `../utils/go2_teleop.py` and `../utils/go2_trick.py`.

## Run (Yugo on the floor, ~2 m clear)
```bash
cd /Users/0x/srv/dimos

# one-time / after model changes: apply DB migrations
.venv/bin/alembic upgrade head

# structured body API (health, tricks, control, owners, moods):
ROBOT_IP=192.168.203.75 .venv/bin/uvicorn yugo.main:app --host 0.0.0.0 --port 8080
#   curl -X POST localhost:8080/hello
#   curl localhost:8080/api/owners/   (CRUD; no robot needed)

# teleop/camera bridge (separate DimOS runtime):
.venv/bin/python yugo/bridge/run.py --robot-ip 192.168.203.75 --port 5555
#   open http://localhost:5555/debug
```

## Data store
SQLite (`yugo.db` at repo root, gitignored) via SQLAlchemy + Alembic. Two tables: `owners`
(identity Yugo bonds to — voice/image signature, one `is_active`) and `mood_events` (log of
charged/safe/curious states). Robot connection/motion config is **not** in the DB — it lives in
`robot.yaml`. After changing a model: `alembic revision --autogenerate -m "..."` then
`alembic upgrade head`.

## Scope (per the PRDs)
This is **Tier 2 — the laptop bridge** (`../prd/01-laptop-bridge-api.md`): robot I/O + reflex/safety
+ the agent (DimOS agentic, `OPENAI_API_KEY`) + perception calls (OpenAI vision / Replicate) +
the HTTP/WS contract for the app. Audio (Deepgram STT, ElevenLabs voice/SFX/music) is app-side; the
bridge carries text, not audio.
