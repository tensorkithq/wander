from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

MoodLabel = Literal["charged", "safe", "curious"]


class MoodCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    state: MoodLabel
    trigger: Optional[str] = None


class MoodRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    state: str
    trigger: Optional[str] = None
    created_at: datetime
