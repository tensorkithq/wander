"""Sensor + spell (wand) schemas.

Two channels (see PRD 02-yugo-app §3 and module-wand-hash):
  - SpellTrace / SpellResult — the discrete one-shot gesture->trick mechanic.
  - SensorReading — the continuous ambient ingest stream.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

# A single motion sample: [t_ms, x, y, z] (t_ms = ms since cast start).
Sample = List[float]


class SpellTrace(BaseModel):
    """The /sensor/spell body: a full motion trace for one button-hold/cast.

    The wand casts from DEVICE MOTION: `accel` (user acceleration, gravity
    removed) is the primary channel and `gyro` (rotation rate) the secondary —
    both are hashed, so a gesture's path and its twist both shape the spell.
    The legacy `magnetometer` channel is still accepted (older phone build) and
    used as the primary when no `accel` is present. At least one of
    accel/magnetometer must carry >= 4 samples, else the trace is rejected (422
    -> fires nothing). Bounds also cap work/payload size.
    """

    source: str = "watch-wand"
    sample_hz: float = 50.0
    accel: Optional[List[Sample]] = Field(default=None, max_length=2000)
    gyro: Optional[List[Sample]] = Field(default=None, max_length=2000)
    magnetometer: Optional[List[Sample]] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def _need_a_gesture(self) -> "SpellTrace":
        # Mirror fire_spell dispatch: magnetometer = phone, else accel = watch.
        primary = self.magnetometer or self.accel
        if not primary or len(primary) < 4:
            raise ValueError("need >= 4 motion samples (magnetometer or accel) to cast")
        return self


class SpellMatch(BaseModel):
    """The bucket the trace hashed to and the trick it maps to."""

    bucket: int
    move: str  # canonical SPORT_CMD move
    api_id: int


class SpellResult(BaseModel):
    """`matched` is computed ALWAYS (works offline); `fired` is true only when
    the move was actually published over the live WebRTC link. `dropped` is true
    when the cast arrived while another was executing and was piped to null by
    the single-flight gate (nothing published)."""

    ok: bool = True
    matched: SpellMatch
    fired: bool
    dropped: bool = False


class SensorAck(BaseModel):
    """Ack for the ambient /sensor ingest. `dropped` is true when the reading was
    piped to null because a spell was mid-cast (single-flight gate)."""

    ok: bool = True
    dropped: bool = False


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
