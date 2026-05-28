"""The offline body-control namespace.

One direct `POST` route per function — expressive actions (hello/wiggle/heart/
sit/standup/standdown/…), keyboard nav (up/down/left/right), raw teleop
(/cmd_vel), and the panic /stop — plus `GET /state` (live deadman/motion state)
and `GET /actions` (the friendly action catalog).

Two layers, two safety stances:
  - Expressive actions need the dog: they 503 when the link is down (body
    contract, hard constraint #2). Their name->api_id mapping is still
    inspectable offline via `GET /actions`.
  - Nav / cmd_vel / stop / state are the LOCAL reflex layer: they always work
    (200) and publish to the dog only while connected, so the deadman stays
    alive and observable even with the link down.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from yugo.controllers import RobotController
from yugo.controllers.MotionController import DIRECTIONS
from yugo.dependencies import get_motion, get_robot
from yugo.schemas.RobotSchema import (
    ActionsResponse,
    MotionState,
    MoveResult,
    TrickResult,
    Velocity,
)

router = APIRouter(tags=["control"])


# --- Expressive actions (need the robot) -------------------------------------

@router.get("/actions", response_model=ActionsResponse)
def actions():
    """The friendly action set with resolved api_ids (works offline)."""
    return ActionsResponse(actions=RobotController.action_catalog())


def _make_action_route(name: str, move: str) -> None:
    # `move` is captured from this factory's scope (a fresh binding per call) —
    # it must NOT be a path-op parameter, or FastAPI would expose it as a query
    # param and let a client override which move fires.
    @router.post(f"/{name}", response_model=TrickResult, name=f"action_{name}")
    def _action(conn=Depends(get_robot), motion=Depends(get_motion)):
        motion.suspend()  # mute the velocity loop so it can't clobber the trick
        return RobotController.fire(conn, move)

    _action.__doc__ = f"Fire the {move!r} action."


for _name, _move in RobotController.ACTIONS.items():
    _make_action_route(_name, _move)


@router.post("/trick/{name}", response_model=TrickResult)
def trick(name: str, conn=Depends(get_robot), motion=Depends(get_motion)):
    """Generic escape hatch: fire any SPORT_CMD move by name (see GET /tricks)."""
    motion.suspend()  # mute the velocity loop so it can't clobber the trick
    return RobotController.fire(conn, name)


@router.post("/sleep", response_model=TrickResult)
def sleep(conn=Depends(get_robot), motion=Depends(get_motion)):
    """Park Yugo: lie down then go limp (StandDown → Damp) — the safe 'sleep' state.

    Distinct from /stop (instant halt, stays standing). The next nav nudge will
    auto-RecoveryStand back into a walk gait.
    """
    motion.suspend()  # mute the velocity loop so it can't clobber the sequence
    return RobotController.sleep(conn)


# --- Keyboard nav + teleop (local reflex layer, deadman-guarded) -------------

def _move_result(action: str, vel, motion) -> MoveResult:
    vx, vy, wz = vel
    return MoveResult(
        action=action,
        vx=vx,
        vy=vy,
        wz=wz,
        duration_s=motion.deadman_window,
        connected=motion.connected,
    )


def _make_nav_route(direction: str) -> None:
    # `direction` is captured from the factory scope (see _make_action_route).
    @router.post(f"/{direction}", response_model=MoveResult, name=f"nav_{direction}")
    def _nav(motion=Depends(get_motion)):
        return _move_result(direction, motion.drive(direction), motion)

    _nav.__doc__ = (
        f"Nudge {direction}: drives for the deadman window then auto-stops. "
        "Re-call within the window to keep moving (key-repeat)."
    )


for _dir in DIRECTIONS:
    _make_nav_route(_dir)


@router.post("/cmd_vel", response_model=MoveResult)
def cmd_vel(vel: Velocity, motion=Depends(get_motion)):
    """Raw velocity teleop: clamped server-side, deadman-guarded. Returns the
    clamped values the body accepted."""
    accepted = motion.set_velocity(vel.vx, vel.vy, vel.wz)
    return _move_result("cmd_vel", accepted, motion)


@router.post("/stop", response_model=MoveResult)
def stop(motion=Depends(get_motion)):
    """Panic/stop: immediately zero the held velocity (and push zero to the dog)."""
    motion.stop()
    return _move_result("stop", (0.0, 0.0, 0.0), motion)


@router.get("/state", response_model=MotionState)
def state(motion=Depends(get_motion)):
    """Live motion + deadman state. After the deadman window, vx/vy/wz read 0."""
    return MotionState(**motion.state())
