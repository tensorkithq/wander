"""Telemetry out: the `/ws/state` WebSocket that pushes an aggregated StateFrame
at ~10-20 Hz (drives the app's "aura"). Read-only and independent of any motion
path — a viewer connecting/dropping never touches the reflex/deadman layer.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["telemetry"])

# Push cadence. PRD asks for ~10-20 Hz; 12 Hz sits comfortably in band and keeps
# the per-tick StateFrame assembly (incl. one SQLite mood read) cheap.
_PUSH_HZ = 12.0


@router.websocket("/ws/state")
async def ws_state(websocket: WebSocket) -> None:
    await websocket.accept()
    agg = getattr(websocket.app.state, "state_agg", None)
    period = 1.0 / _PUSH_HZ
    try:
        while True:
            frame = (
                agg.frame()
                if agg is not None
                else {"connected": False, "mode": "creature"}
            )
            await websocket.send_json(frame)
            await asyncio.sleep(period)
    except WebSocketDisconnect:
        return
    except Exception:
        # Client gone / send failed — end the push loop quietly. The body stays
        # up; the next client gets a fresh stream.
        return
