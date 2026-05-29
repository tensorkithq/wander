from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session

from yugo.config import SessionLocal, settings


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_robot(request: Request):
    """Yield the live WebRTC connection, or 503 if the channel is down.

    Per the body contract (hard constraint #2) this reflects the *live* channel
    state, not just that the initial handshake once succeeded.
    """
    conn = getattr(request.app.state, "robot", None)
    if conn is None or not conn.connection_ready.is_set():
        raise HTTPException(503, f"robot not connected (ROBOT_IP={settings.robot.ip})")
    return conn


def get_motion(request: Request):
    """Yield the local MotionController (the deadman/teleop reflex layer).

    Unlike `get_robot`, this never 503s on a missing dog: the deadman/nav state
    machine runs locally so the body stays controllable/observable even with the
    link down (it publishes to the dog only while connected).
    """
    motion = getattr(request.app.state, "motion", None)
    if motion is None:
        raise HTTPException(503, "motion controller not initialized")
    return motion


def get_mode(request: Request):
    """Yield the ModeController (the body's active-mode state machine)."""
    mode_ctrl = getattr(request.app.state, "mode_ctrl", None)
    if mode_ctrl is None:
        raise HTTPException(503, "mode controller not initialized")
    return mode_ctrl


def get_mind(request: Request):
    """Yield the MindClient (the cloud inference server wrapper — vision + STT)."""
    mind = getattr(request.app.state, "mind", None)
    if mind is None:
        raise HTTPException(503, "mind client not initialized")
    return mind


def get_frames(request: Request):
    """Yield the FrameSource (latest camera frame as base64, for vision calls)."""
    frames = getattr(request.app.state, "frames", None)
    if frames is None:
        raise HTTPException(503, "frame source not initialized")
    return frames
