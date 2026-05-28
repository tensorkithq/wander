from __future__ import annotations

import time

from fastapi import HTTPException

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD

from yugo.config import settings

# Expressive moves the dog ignores unless it is upright first; these prepend a
# BalanceStand + settle. Keyed on the SPORT_CMD move name so /trick/{name} gets
# it too, not just the friendly /wiggle, /heart, /stretch, /dance routes.
NEEDS_BALANCE: set[str] = {
    "FingerHeart", "Stretch", "Dance1", "Dance2", "MoonWalk", "Pose", "Content",
}

# Friendly named actions -> canonical SPORT_CMD move. Each becomes a direct
# `POST /<name>` route. Extend this dict to expose more (every key in SPORT_CMD
# is also reachable generically via POST /trick/{name}).
ACTIONS: dict[str, str] = {
    "hello": "Hello",
    "heart": "FingerHeart",
    "sit": "Sit",
    "standup": "StandUp",
    "standdown": "StandDown",
    "stretch": "Stretch",
    "dance": "Dance1",
}


def list_tricks() -> list[str]:
    return sorted(SPORT_CMD.keys())


def action_catalog() -> list[dict]:
    """The friendly action set with resolved api_ids (validatable offline)."""
    return [
        {"name": name, "move": move, "api_id": SPORT_CMD[move]}
        for name, move in ACTIONS.items()
    ]


def fire(conn, move: str) -> dict:
    """Publish a single SPORT_CMD move over WebRTC.

    Expressive moves in NEEDS_BALANCE are ignored unless Yugo is upright, so we
    prepend BalanceStand and let it settle (`trick_balance_settle_s`) first.
    Note: the returned dict is a PUBLISH ack, not an execution ack.
    """
    cmd_id = SPORT_CMD.get(move)
    if cmd_id is None:
        raise HTTPException(404, f"unknown move {move!r} — see GET /tricks")
    if move in NEEDS_BALANCE:
        conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["BalanceStand"]})
        time.sleep(settings.motion.trick_balance_settle_s)
    conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": cmd_id})
    return {"ok": True, "move": move, "api_id": cmd_id}


def stop(conn) -> dict:
    """Global stop → safe upright stance (RecoveryStand → BalanceStand)."""
    fire(conn, "RecoveryStand")
    return fire(conn, "BalanceStand")


def sleep(conn) -> dict:
    """Park Yugo: lie down then go limp — the safe 'sleep' state (StandDown → Damp).

    A short settle lets StandDown finish so Damp relaxes from lying, not standing.
    """
    fire(conn, "StandDown")
    time.sleep(settings.motion.trick_balance_settle_s)
    return fire(conn, "Damp")
