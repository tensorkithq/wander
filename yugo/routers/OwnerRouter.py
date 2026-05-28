from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from yugo.controllers import OwnerController
from yugo.dependencies import get_db
from yugo.schemas.OwnerSchema import OwnerCreate, OwnerRead, OwnerUpdate

router = APIRouter(prefix="/api/owners", tags=["memory"])


@router.post("/", response_model=OwnerRead)
def create_owner(data: OwnerCreate, db: Session = Depends(get_db)):
    return OwnerController.create_owner(data, db)


@router.get("/", response_model=List[OwnerRead])
def list_owners(db: Session = Depends(get_db)):
    return OwnerController.list_owners(db)


@router.get("/{owner_id}", response_model=OwnerRead)
def get_owner(owner_id: str, db: Session = Depends(get_db)):
    return OwnerController.get_owner(owner_id, db)


@router.put("/{owner_id}", response_model=OwnerRead)
def update_owner(owner_id: str, data: OwnerUpdate, db: Session = Depends(get_db)):
    return OwnerController.update_owner(owner_id, data, db)


@router.delete("/{owner_id}")
def delete_owner(owner_id: str, db: Session = Depends(get_db)):
    return OwnerController.delete_owner(owner_id, db)
