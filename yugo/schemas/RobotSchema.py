from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class OkResponse(BaseModel):
    ok: bool = True


class TrickResult(BaseModel):
    """`ok:true` means PUBLISHED, not executed (no execution ack from the dog)."""

    ok: bool = True
    move: str
    api_id: Optional[int] = None


class HealthStatus(BaseModel):
    ok: bool = True
    robot_ip: str
    connected: bool


class TricksResponse(BaseModel):
    tricks: List[str]
