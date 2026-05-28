from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yugo.config import settings
from yugo.controllers.MotionController import MotionController
from yugo.routers import ControlRouter, MoodRouter, OwnerRouter, SystemRouter

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
    yield
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
app.include_router(OwnerRouter.router)
app.include_router(MoodRouter.router)


@app.get("/")
def root():
    return {"message": "Yugo body is running"}
