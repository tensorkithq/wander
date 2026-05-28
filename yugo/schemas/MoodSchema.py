from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

# The demo mood vocabulary. Each maps to a color (for the app's aura tint) and a
# Yugo gesture, defined in MoodController.MOODS.
MoodLabel = Literal["happy", "playful", "affectionate", "calm", "zen"]


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


class MoodCurrent(BaseModel):
    """Yugo's current mood for the app to poll and tint its surface to `color`."""

    state: str  # the mood label, e.g. "zen"
    color: str  # hex tint for the app's aura, e.g. "#6a7bff"
    gesture: str  # the SPORT_CMD move Yugo performs on entering this mood
    scalar: float  # mood intensity 0..1 (drives aura energy)
    created_at: Optional[datetime] = None
