from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yugo.config import Base, SessionLocal, engine, settings
from yugo.controllers.FindMode import FindMode
from yugo.controllers.FrameSource import FrameSource
from yugo.controllers.FriendMode import FriendMode
from yugo.controllers.MindController import MindClient
from yugo.controllers.ModeController import ModeController
from yugo.controllers.MoodController import MoodLoop
from yugo.controllers.MotionController import MotionController
from yugo.controllers.PersonalMode import PersonalMode
from yugo.routers import (
    ControlRouter,
    MoodRouter,
    OwnerRouter,
    SensorRouter,
    SystemRouter,
)

_DOC_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}


def _print_routes(app: FastAPI) -> None:
    """List available routes on startup so the API surface is visible at a glance."""
    from fastapi.routing import APIRoute, APIWebSocketRoute

    rows: list[tuple[str, str]] = []
    for r in app.routes:
        if isinstance(r, APIWebSocketRoute):
            rows.append(("WS", r.path))
        elif isinstance(r, APIRoute) and r.path not in _DOC_PATHS:
            methods = "|".join(
                sorted(m for m in (r.methods or set()) if m not in {"HEAD", "OPTIONS"})
            )
            rows.append((methods, r.path))
    rows.sort(key=lambda mp: mp[1])
    width = max((len(m) for m, _ in rows), default=4)
    print(f"[yugo] {len(rows)} routes available:")
    for methods, path in rows:
        print(f"[yugo]   {methods:<{width}}  {path}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _print_routes(app)
    # YUGO_NO_ROBOT=1 runs the body without a dog: the local reflex layer (nav,
    # deadman, /state) stays live for offline use and the HTTP test suite, while
    # robot-bound actions 503. Lets tests hit the *actual* API, not a mock.
    if os.environ.get("YUGO_NO_ROBOT"):
        print("[yugo] YUGO_NO_ROBOT set — running offline (no WebRTC link)")
        app.state.robot = None
    else:
        # Imported here so importing `yugo.main` (e.g. for tooling) doesn't try
        # to open a WebRTC link as a side effect.
        from dimos.robot.unitree.connection import UnitreeWebRTCConnection

        print(f"[yugo] connecting to Go2 at {settings.robot.ip} ...")
        conn = UnitreeWebRTCConnection(ip=settings.robot.ip)  # connects in a bg thread
        app.state.robot = conn
        if conn.connection_ready.wait(timeout=settings.robot.connect_timeout):
            print("[yugo] robot connected.")
        else:
            print(
                f"[yugo] WARNING: WebRTC not ready in {settings.robot.connect_timeout}s; "
                "control routes will 503 until it connects (check ROBOT_IP / power)."
            )

    motion = MotionController(app.state.robot, settings.motion)
    motion.start()
    app.state.motion = motion

    # Mode state machine (the backbone behavior modules register enter/exit hooks
    # into). Stateless w.r.t. the dog — a mode switch never publishes velocity.
    app.state.mode_ctrl = ModeController()

    # Mind integration: the cloud inference client + the latest-frame source the
    # vision modes (personal/find/friend) feed. FrameSource is a no-op offline.
    app.state.mind = MindClient(settings.mind.base_url)
    frames = FrameSource(app.state.robot)
    frames.start()
    app.state.frames = frames

    # Register the vision behavior modes into the mode machine. Each loop idles
    # until its mode is active AND the camera is connected; it reads frames/mind/
    # motion off app.state at runtime. (Bound methods keep the instances alive.)
    for _cls, _name in ((PersonalMode, "personal"), (FindMode, "find"), (FriendMode, "friend")):
        _m = _cls(app)
        app.state.mode_ctrl.register(_name, enter=_m.enter, exit=_m.exit)

    # Ensure DB tables exist (idempotent safety net; alembic owns schema evolution).
    Base.metadata.create_all(bind=engine)
    # Mood loop: picks a mood every settings.mood.update_seconds (demo: random),
    # persists it to SQLite for the app to poll, and performs a per-mood gesture.
    mood = MoodLoop(app.state.robot, motion, SessionLocal, settings.mood)
    mood.start()
    app.state.mood = mood
    yield
    frames.stop()
    mood.stop_loop()
    motion.stop_loop()
    # robot background thread is a daemon; nothing else to tear down explicitly


app = FastAPI(title="Yugo Body API", version="0.1.0", lifespan=lifespan)

# No auth by design — LAN/Tailscale tool. Do NOT expose this port publicly.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(SystemRouter.router)
app.include_router(ControlRouter.router)
app.include_router(SensorRouter.router)
app.include_router(OwnerRouter.router)
app.include_router(MoodRouter.router)


@app.get("/")
def root():
    return {"message": "Yugo body is running"}
