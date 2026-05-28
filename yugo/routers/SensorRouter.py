"""The wand / sensor namespace.

  - POST /sensor/spell — the headline mechanic: a magnetometer trace -> a trick,
    DETERMINISTICALLY. The match is computed ALWAYS (so it works offline,
    returning fired:false); the trick fires only while the WebRTC link is live.
  - POST /sensor — continuous ambient ingest: validate + accept + keep the
    latest reading on app.state. No robot behaviour yet (PRD: minimal for now).

These do NOT use Depends(get_robot): get_robot 503s when the dog is offline, but
a spell must still return its match offline. We read the optional connection
straight off request.app.state.robot and fire only if it is present + ready.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from yugo.controllers import SensorController
from yugo.schemas.RobotSchema import OkResponse
from yugo.schemas.SensorSchema import SensorReading, SpellResult, SpellTrace

router = APIRouter(tags=["sensor"])


@router.post("/sensor/spell", response_model=SpellResult)
def spell(trace: SpellTrace, request: Request):
    """Cast a spell from a magnetometer trace. The match is deterministic and
    always computed; the trick is published only when the link is live (else
    fired:false). A too-short/empty trace is rejected (422) and fires nothing."""
    conn = getattr(request.app.state, "robot", None)
    result = SensorController.fire_spell(conn, trace)
    return SpellResult(matched=result["matched"], fired=result["fired"])


@router.post("/sensor", response_model=OkResponse)
def sensor(reading: SensorReading, request: Request):
    """Continuous ambient wand ingest: validate, accept, keep the latest reading
    on app.state for later reaction loops. No motion is triggered here yet."""
    request.app.state.last_sensor = reading
    return OkResponse()
