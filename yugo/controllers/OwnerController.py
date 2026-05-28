from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from yugo.models.OwnerModel import OwnerModel
from yugo.schemas.OwnerSchema import OwnerCreate, OwnerUpdate


def _deactivate_all(db: Session) -> None:
    db.query(OwnerModel).update({OwnerModel.is_active: False}, synchronize_session=False)


def create_owner(data: OwnerCreate, db: Session) -> OwnerModel:
    if data.is_active:
        _deactivate_all(db)
    owner = OwnerModel(**data.model_dump())
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def list_owners(db: Session) -> list[OwnerModel]:
    return db.query(OwnerModel).all()


def get_owner(owner_id: str, db: Session) -> OwnerModel:
    owner = db.get(OwnerModel, owner_id)
    if owner is None:
        raise HTTPException(404, "owner not found")
    return owner


def update_owner(owner_id: str, data: OwnerUpdate, db: Session) -> OwnerModel:
    owner = get_owner(owner_id, db)
    updates = data.model_dump(exclude_unset=True)
    if updates.get("is_active"):
        _deactivate_all(db)
    for key, value in updates.items():
        setattr(owner, key, value)
    db.commit()
    db.refresh(owner)
    return owner


def delete_owner(owner_id: str, db: Session) -> dict:
    owner = get_owner(owner_id, db)
    db.delete(owner)
    db.commit()
    return {"ok": True}
