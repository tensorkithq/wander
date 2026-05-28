from __future__ import annotations

from fastapi import APIRouter, Request

from yugo.config import settings
from yugo.controllers import RobotController
from yugo.schemas.RobotSchema import HealthStatus, TricksResponse

router = APIRouter(tags=["system"])


@router.get("/healthz", response_model=HealthStatus)
def healthz(request: Request):
    conn = getattr(request.app.state, "robot", None)
    connected = conn is not None and conn.connection_ready.is_set()
    return HealthStatus(robot_ip=settings.robot.ip, connected=connected)


@router.get("/tricks", response_model=TricksResponse)
def tricks():
    return TricksResponse(tricks=RobotController.list_tricks())
