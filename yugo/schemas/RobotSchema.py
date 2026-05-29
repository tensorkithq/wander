from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel

# The body's mode vocabulary — the five demo-arc modes + `creature` (idle/default).
ModeName = Literal["creature", "personal", "friend", "find", "wand", "meditation"]


class OkResponse(BaseModel):
    ok: bool = True


class TrickResult(BaseModel):
    """`ok:true` means PUBLISHED, not executed (no execution ack from the dog)."""

    ok: bool = True
    move: str
    api_id: Optional[int] = None


class HealthStatus(BaseModel):
    ok: bool = True
    robot_ip: str
    connected: bool


class TricksResponse(BaseModel):
    tricks: List[str]


class ActionInfo(BaseModel):
    name: str  # friendly route name, e.g. "wiggle"
    move: str  # canonical SPORT_CMD move, e.g. "WiggleHips"
    api_id: int


class ActionsResponse(BaseModel):
    actions: List[ActionInfo]


class Velocity(BaseModel):
    """Raw teleop command. Missing fields default to 0; values are clamped."""

    vx: float = 0.0  # forward (+) / back (-), m/s
    vy: float = 0.0  # left (+) / right (-) strafe, m/s
    wz: float = 0.0  # yaw rate (CCW +), rad/s


class MoveResult(BaseModel):
    """Echoes the velocity the body accepted (post-clamp) for a nav/teleop call."""

    ok: bool = True
    action: str
    vx: float
    vy: float
    wz: float
    duration_s: float  # how long this nudge holds before the deadman zeroes it
    connected: bool


class MotionState(BaseModel):
    """Live motion/deadman state — the deadman is observable here over HTTP."""

    moving: bool
    vx: float  # deadman-adjusted (effective) velocity right now
    vy: float
    wz: float
    raw_vx: float  # last commanded velocity, before the deadman window is applied
    raw_vy: float
    raw_wz: float
    last_cmd_age_s: Optional[float] = None
    deadman_window: float
    connected: bool
    mode: str = "creature"  # the body's active behavior mode (see ModeController)


class ModeRequest(BaseModel):
    """POST /mode body. The Literal makes an unknown mode a 422."""

    mode: ModeName
    target: Optional[str] = None  # optional subject for find/friend (person to seek)


class ModeResult(BaseModel):
    ok: bool = True
    mode: str


class SdpOffer(BaseModel):
    """WHIP-style signaling: the browser's SDP offer (POST /feed/offer body)."""

    sdp: str
    type: Literal["offer"] = "offer"


class SdpAnswer(BaseModel):
    """The hub's SDP answer returned from POST /feed/offer."""

    sdp: str
    type: Literal["answer"] = "answer"


class FeedHealth(BaseModel):
    """GET /feed/health — relay state observable over HTTP."""

    viewers: int  # active WebRTC peer connections
    source_active: bool  # is a frame source attached (dog or synthetic)
