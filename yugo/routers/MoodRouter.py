from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from yugo.controllers import MoodController
from yugo.dependencies import get_db
from yugo.schemas.MoodSchema import MoodCreate, MoodCurrent, MoodRead

router = APIRouter(prefix="/api/moods", tags=["memory"])


@router.post("/", response_model=MoodRead)
def log_mood(data: MoodCreate, db: Session = Depends(get_db)):
    return MoodController.log_mood(data, db)


@router.get("/current", response_model=MoodCurrent)
def current_mood(db: Session = Depends(get_db)):
    """Yugo's current mood — the app polls this and tints its surface to `color`."""
    return MoodController.current_mood(db)


@router.get("/", response_model=List[MoodRead])
def list_moods(limit: int = 100, db: Session = Depends(get_db)):
    return MoodController.list_moods(db, limit)
