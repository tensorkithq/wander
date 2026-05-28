"""Sensor + spell (wand) schemas.

Two channels (see PRD 02-yugo-app §3 and module-wand-hash):
  - SpellTrace / SpellResult — the discrete one-shot gesture->trick mechanic.
  - SensorReading — the continuous ambient ingest stream.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

# A single magnetometer/accel sample as the phone sends it: [t_ms, x, y, z].
Sample = List[float]


class SpellTrace(BaseModel):
    """The /sensor/spell body: a full magnetometer trace for one button-hold.

    Each sample is [t_ms, x, y, z] (t_ms = ms since hold start; x,y,z µT).
    `accel` is the optional parallel IMU trace (m/s²). Bounds reject inputs too
    short to be a gesture (fires nothing -> 422) and cap work/payload size.
    """

    source: str = "phone-wand"
    sample_hz: float = 50.0
    magnetometer: List[Sample] = Field(..., min_length=4, max_length=2000)
    accel: Optional[List[Sample]] = Field(default=None, max_length=2000)


class SpellMatch(BaseModel):
    """The bucket the trace hashed to and the trick it maps to."""

    bucket: int
    move: str  # canonical SPORT_CMD move
    api_id: int


class SpellResult(BaseModel):
    """`matched` is computed ALWAYS (works offline); `fired` is true only when
    the move was actually published over the live WebRTC link."""

    ok: bool = True
    matched: SpellMatch
    fired: bool


class Vector3(BaseModel):
    x: float
    y: float
    z: float


class SensorReading(BaseModel):
    """The /sensor body: one continuous ambient wand reading (kept minimal)."""

    source: str
    magnetometer: Optional[Vector3] = None
    accel: Optional[Vector3] = None
    light: Optional[float] = None
    gesture: Optional[str] = None
    ts: Optional[float] = None
