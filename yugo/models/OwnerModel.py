from __future__ import annotations

import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, String, Text

from yugo.config import Base


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class OwnerModel(Base):
    """A person Yugo recognizes as its owner.

    Identity is keyed off a voice and/or image signature (the "memory" the
    spirit-animal trust beat keys on). `is_active` marks the single owner Yugo
    currently bonds to.
    """

    __tablename__ = "owners"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(80), nullable=False, index=True)
    voice_signature = Column(Text, nullable=True)
    image_signature = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)

    def __repr__(self) -> str:
        return f"<Owner(id={self.id}, name={self.name!r}, active={self.is_active})>"
