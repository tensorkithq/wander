# yugo/ — Yugo robot/DimOS API ("the body")

**All Python / robot-control API work lives here.** This is the FastAPI layer that connects to
Yugo (Go2 Air) over WebRTC and exposes the HTTP API the Yugo app codes against.
`openapi.yaml` is the authoritative surface contract (each route is marked implemented vs planned).

Distinct from `app/backend/` (Hono/Bun **TypeScript** — the app's general backend). Robot control
**must** be Python (DimOS / `unitree_webrtc_connect`), so it lives here, separately. The package is
named `yugo` (not `fastapi`) so it doesn't shadow the pip `fastapi` package.

Runs inside this repo's `.venv` (where `dimos` + `unitree_webrtc_connect` are installed).

## Layout
| Path | What |
|---|---|
| `main.py` | FastAPI app: CORS, router wiring, lifespan — WebRTC connect → `app.state.robot`, start the `MotionController` reflex loop → `app.state.motion`. `YUGO_NO_ROBOT=1` skips the link and runs offline (reflex layer stays live). |
| `config.py` | SQLite engine / `SessionLocal` / `Base`, plus settings loaded from `robot.yaml`. |
| `robot.yaml` | Robot connection + motion config (IP, connect timeout, velocity clamps, deadman window, nav steps). No secrets. `ROBOT_IP` env overrides the IP. |
| `dependencies.py` | `get_db` (DB session), `get_robot` (live WebRTC conn or 503), `get_motion` (the local deadman/teleop reflex layer). |
| `routers/` | HTTP routes by contract group: `SystemRouter` (health/tricks), `ControlRouter` (**unified offline control**: expressive actions + keyboard nav + deadman teleop), `OwnerRouter` + `MoodRouter` (persistence). |
| `controllers/` | Business logic: `RobotController` (SPORT_CMD actions over WebRTC), `MotionController` (deadman-guarded, timed-nudge teleop/nav — the reflex layer), `OwnerController`, `MoodController`. |
| `models/` | SQLAlchemy models: `OwnerModel`, `MoodEventModel`. |
| `schemas/` | Pydantic request/response schemas. |
| `alembic/` | Migrations (`alembic upgrade head`). Schema lives here, not in code. |
| `bridge/` | **DEPRECATED (2026-05-29).** The old DimOS teleop runtime. `web_bridge.py` (MJPEG camera + `/cmd_vel` teleop + deadman), `run.py`, `static/debug.html`. Teleop/deadman are superseded by the hub (`MotionController`); only the MJPEG camera has no hub equivalent yet. Do not build new clients against :5555. |
| `openapi.yaml` | Authoritative API contract (body vs mind, implemented vs planned). |

The offline control surface is **unified on the hub** (one router): expressive
actions (`POST /hello /wiggle /heart /sit /standup /standdown /stretch /dance`,
catalog at `GET /actions`), keyboard nav (`POST /up /down /left /right`, timed
nudge), raw teleop (`POST /cmd_vel`), panic `POST /stop`, and live deadman state
at `GET /state`. Actions need the dog (503 offline); nav/teleop/deadman are local
reflex (always 200, publish only while connected).

Tests live in `../tests/` (`uv run pytest`) — they boot the **actual** app under
uvicorn (no robot, `YUGO_NO_ROBOT=1`) and validate the deadman/nav/actions purely
from real HTTP responses (no mocks). Other utilities: `../scripts/smoke_bridge.py`
(no-robot harness for the **deprecated** bridge), standalone `../utils/go2_teleop.py`,
`../utils/go2_trick.py`.

## Run (Yugo on the floor, ~2 m clear)
```bash
cd /Users/0x/srv/dimos

# one-time / after model changes: apply DB migrations
.venv/bin/alembic upgrade head

# structured body API (health, tricks, actions, nav, deadman, owners, moods):
ROBOT_IP=192.168.203.75 .venv/bin/uvicorn yugo.main:app --host 0.0.0.0 --port 8080
#   curl -X POST localhost:8080/hello          # expressive action
#   curl -X POST localhost:8080/up             # keyboard-nav nudge (deadman-guarded)
#   curl localhost:8080/state                  # live motion/deadman state
#   curl localhost:8080/api/owners/            # CRUD; no robot needed

# run WITHOUT a dog (offline) — reflex layer (nav/deadman/state) stays live:
#   YUGO_NO_ROBOT=1 .venv/bin/uvicorn yugo.main:app --port 8080

# DEPRECATED teleop/camera bridge (run only for the MJPEG camera stream):
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
This package is **the body** (canonical spec: `../prd/architecture-body.md`; detailed tier doc:
`../prd/01-laptop-bridge-api.md`): a light FastAPI on the dog's LAN that owns the WebRTC link,
executes control locally, and runs the fast/reflex (deadman) loop. Intelligence — LLM reasoning,
perception, voice/music — is delegated to **the mind** (cloud, `../prd/architecture-mind.md`); the
body carries text, not audio.

**Implemented today:** health/discovery (`/healthz`, `/tricks`, `/actions`), expressive actions,
keyboard nav + deadman teleop (`/up`…`/right`, `/cmd_vel`, `/stop`, `/state`), owners/moods
persistence.

**Designed, not yet built:** the `/ws/state` telemetry WebSocket and the WebRTC video feed
(`/feed`) — see `../docs/plans/2026-05-29-webrtc-feed-relay-design.md`. The agent loop (DimOS
agentic, `OPENAI_API_KEY`) and perception (OpenAI vision / Replicate) are mind-side and not in this
package yet.
