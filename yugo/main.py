from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from yugo.config import settings
from yugo.routers import ControlRouter, MoodRouter, OwnerRouter, SystemRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Imported here so importing `yugo.main` (e.g. for tooling) doesn't try to
    # open a WebRTC link as a side effect.
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
    yield
    # background thread is a daemon; nothing to tear down explicitly


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
