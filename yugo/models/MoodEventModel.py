from __future__ import annotations

import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text

from yugo.config import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class MoodEventModel(Base):
    """A timestamped mood Yugo entered (charged | safe | curious) and what cued it."""

    __tablename__ = "mood_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    state = Column(String(20), nullable=False, index=True)
    trigger = Column(Text, nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
