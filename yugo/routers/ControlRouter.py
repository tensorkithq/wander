from __future__ import annotations

from fastapi import APIRouter, Depends

from yugo.controllers import RobotController
from yugo.dependencies import get_robot
from yugo.schemas.RobotSchema import TrickResult

router = APIRouter(tags=["control"])


@router.post("/hello", response_model=TrickResult)
def hello(conn=Depends(get_robot)):
    """Canonical 'curl → bot activity' check: Yugo rears up and waves."""
    return RobotController.fire(conn, "Hello")


@router.post("/trick/{name}", response_model=TrickResult)
def trick(name: str, conn=Depends(get_robot)):
    return RobotController.fire(conn, name)


@router.post("/stop", response_model=TrickResult)
def stop(conn=Depends(get_robot)):
    return RobotController.stop(conn)
