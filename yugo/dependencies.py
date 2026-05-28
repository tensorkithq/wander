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
