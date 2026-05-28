from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class OwnerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str
    voice_signature: Optional[str] = None
    image_signature: Optional[str] = None
    is_active: bool = False


class OwnerCreate(OwnerBase):
    pass


class OwnerUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: Optional[str] = None
    voice_signature: Optional[str] = None
    image_signature: Optional[str] = None
    is_active: Optional[bool] = None


class OwnerRead(OwnerBase):
    id: str
    created_at: datetime
    updated_at: datetime
