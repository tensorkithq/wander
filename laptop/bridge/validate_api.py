#!/usr/bin/env python3
"""Reality Instrument — connection-validation API (Yugo / Go2 Air).

Minimal, NO-AUTH FastAPI that proves the laptop -> Go2 path end to end:
a single curl triggers real robot activity. Uses unitree_webrtc_connect
DIRECTLY (the go2_trick.py pattern) — no DimOS module graph, so the missing
perception model tarballs (models_yolo / models_clip) can't block startup.

Run (inside the dimos venv, dog on the LAN):
    ROBOT_IP=192.168.203.75 python validate_api.py
    # or: ROBOT_IP=192.168.203.75 uvicorn validate_api:app --host 0.0.0.0 --port 8080

Validate:
    curl localhost:8080/healthz
    curl localhost:8080/tricks
    curl -X POST localhost:8080/hello            # Yugo rears up and waves
    curl -X POST localhost:8080/trick/WiggleHips
    curl -X POST localhost:8080/stop             # RecoveryStand -> BalanceStand

⚠️  SAFETY: tricks MOVE the robot. Put Yugo on the floor with ~2 m clear space.
NO AUTH by design (local validation tool) — do NOT expose this port publicly.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
from dimos.robot.unitree.connection import UnitreeWebRTCConnection

ROBOT_IP = os.environ.get("ROBOT_IP", "192.168.203.75")
CONNECT_TIMEOUT = float(os.environ.get("CONNECT_TIMEOUT", "25"))

_conn: UnitreeWebRTCConnection | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _conn
    print(f"[validate_api] connecting to Go2 at {ROBOT_IP} ...")
    _conn = UnitreeWebRTCConnection(ip=ROBOT_IP)  # connects in a background thread
    if _conn.connection_ready.wait(timeout=CONNECT_TIMEOUT):
        print("[validate_api] connected. AI motion mode engaged.")
    else:
        print(f"[validate_api] WARNING: WebRTC not ready in {CONNECT_TIMEOUT}s; "
              f"endpoints will 503 until it connects (check ROBOT_IP / robot power).")
    yield
    # background thread is a daemon; nothing to tear down explicitly


app = FastAPI(title="Yugo connection validator", lifespan=lifespan)


def _ready() -> bool:
    return _conn is not None and _conn.connection_ready.is_set()


def _fire(move: str) -> dict:
    cmd_id = SPORT_CMD.get(move)
    if cmd_id is None:
        raise HTTPException(404, f"unknown move '{move}' — see GET /tricks")
    if not _ready():
        raise HTTPException(503, f"robot not connected (ROBOT_IP={ROBOT_IP})")
    _conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": cmd_id})
    return {"ok": True, "move": move, "api_id": cmd_id}


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "robot_ip": ROBOT_IP, "connected": _ready()}


@app.get("/tricks")
def tricks() -> dict:
    return {"tricks": sorted(SPORT_CMD.keys())}


@app.api_route("/trick/{name}", methods=["GET", "POST"])
def trick(name: str) -> dict:
    return _fire(name)


@app.api_route("/hello", methods=["GET", "POST"])
def hello() -> dict:
    # canonical "curl => bot activity" validation: rear up and wave
    return _fire("Hello")


@app.api_route("/stop", methods=["GET", "POST"])
def stop() -> dict:
    if not _ready():
        raise HTTPException(503, "robot not connected")
    _fire("RecoveryStand")
    return _fire("BalanceStand")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
