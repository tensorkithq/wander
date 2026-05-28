from __future__ import annotations

from sqlalchemy.orm import Session

from yugo.models.MoodEventModel import MoodEventModel
from yugo.schemas.MoodSchema import MoodCreate


def log_mood(data: MoodCreate, db: Session) -> MoodEventModel:
    event = MoodEventModel(**data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_moods(db: Session, limit: int = 100) -> list[MoodEventModel]:
    return (
        db.query(MoodEventModel)
        .order_by(MoodEventModel.created_at.desc())
        .limit(limit)
        .all()
    )
