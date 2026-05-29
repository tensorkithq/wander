from __future__ import annotations

from fastapi import APIRouter, Request

from yugo.config import settings
from yugo.controllers import RobotController
from yugo.controllers.RobotInfo import connected_robot_info
from yugo.schemas.RobotSchema import HealthStatus, RobotIdentity, TricksResponse

router = APIRouter(tags=["system"])


@router.get("/healthz", response_model=HealthStatus)
def healthz(request: Request):
    conn = getattr(request.app.state, "robot", None)
    connected = conn is not None and conn.connection_ready.is_set()
    return HealthStatus(robot_ip=settings.robot.ip, connected=connected)


@router.get("/robot/info", response_model=RobotIdentity)
def robot_info(request: Request):
    """Identity of the connected robot (by IP): name, ip, mac, serial, link state.
    Serial via LAN multicast, MAC via the host ARP table — both best-effort
    (need the dog on the LAN) and cached once found."""
    return connected_robot_info(getattr(request.app.state, "robot", None))


@router.get("/tricks", response_model=TricksResponse)
def tricks():
    return TricksResponse(tricks=RobotController.list_tricks())
