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
from yugo.schemas.SensorSchema import (
    SensorAck,
    SensorReading,
    SpellResult,
    SpellTrace,
)

router = APIRouter(tags=["sensor"])


@router.post("/sensor/spell", response_model=SpellResult)
def spell(trace: SpellTrace, request: Request):
    """Cast a spell from a gesture trace. The match is deterministic and always
    computed; the trick is published only when the link is live (else
    fired:false). A cast that arrives while another is still executing is dropped
    by the single-flight gate (dropped:true, nothing published). A too-short/empty
    trace is rejected (422) and fires nothing."""
    conn = getattr(request.app.state, "robot", None)
    result = SensorController.fire_spell(conn, trace)
    return SpellResult(
        matched=result["matched"], fired=result["fired"], dropped=result["dropped"]
    )


@router.post("/sensor", response_model=SensorAck)
def sensor(reading: SensorReading, request: Request):
    """Continuous ambient wand ingest: validate, accept, keep the latest reading
    on app.state for later reaction loops. While a spell is mid-cast the reading
    is piped to null (dropped:true) so the cast isn't drowned out by the stream."""
    if SensorController.machine.busy:
        return SensorAck(dropped=True)
    request.app.state.last_sensor = reading
    return SensorAck()
