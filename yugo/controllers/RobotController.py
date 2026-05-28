from __future__ import annotations

from fastapi import HTTPException

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD


def list_tricks() -> list[str]:
    return sorted(SPORT_CMD.keys())


def fire(conn, move: str) -> dict:
    """Publish a single SPORT_CMD move over WebRTC.

    Note: a returned dict is a PUBLISH ack, not an execution ack — the dog may
    ignore the command (e.g. expressive moves while not upright).
    """
    cmd_id = SPORT_CMD.get(move)
    if cmd_id is None:
        raise HTTPException(404, f"unknown move {move!r} — see GET /tricks")
    conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": cmd_id})
    return {"ok": True, "move": move, "api_id": cmd_id}


def stop(conn) -> dict:
    """Global stop → safe upright stance (RecoveryStand → BalanceStand)."""
    fire(conn, "RecoveryStand")
    return fire(conn, "BalanceStand")
