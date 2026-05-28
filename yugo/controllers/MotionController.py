"""Local motion / teleop with a deadman-guarded, timed-nudge model.

This is the body's reflex layer: it runs locally and stays alive even when the
robot link or the cloud is down. A nav/cmd_vel call sets a held velocity stamped
with a timestamp; the *effective* velocity is that command only while it is
younger than `command_timeout` — past the window it is zero (safe stop). That
single window is BOTH the deadman watchdog and the timed-nudge duration: one
`/up` call drives for `command_timeout` seconds, then auto-zeroes; re-poking
within the window extends it.

The decision is pure (`clamp`, `direction_to_velocity`, `deadman_adjust`) so it
is trivially unit-testable, and `state()` recomputes it on read so the deadman
is observable over HTTP without depending on the publish loop running.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from yugo.config import MotionConfig

# direction -> unit (sign) on (forward, strafe, yaw). ROS convention:
# +x forward, +y left strafe, +z yaw CCW (turn left).
_DIRECTIONS = {
    "up": (1.0, 0.0, 0.0),  # forward
    "down": (-1.0, 0.0, 0.0),  # back
    "left": (0.0, 0.0, 1.0),  # turn left (CCW)
    "right": (0.0, 0.0, -1.0),  # turn right (CW)
}

DIRECTIONS = tuple(_DIRECTIONS.keys())


def clamp(
    vx: float, vy: float, wz: float, max_linear: float, max_angular: float
) -> tuple[float, float, float]:
    """Clamp velocities to the configured envelope (clamped, never rejected)."""
    vx = max(-max_linear, min(max_linear, vx))
    vy = max(-max_linear, min(max_linear, vy))
    wz = max(-max_angular, min(max_angular, wz))
    return (vx, vy, wz)


def direction_to_velocity(
    direction: str, linear_step: float, angular_step: float
) -> tuple[float, float, float]:
    """Map a keyboard-nav direction to a (vx, vy, wz) velocity, or raise."""
    sign = _DIRECTIONS.get(direction)
    if sign is None:
        raise ValueError(f"unknown direction {direction!r} — use one of {DIRECTIONS}")
    fwd, strafe, yaw = sign
    return (fwd * linear_step, strafe * linear_step, yaw * angular_step)


def deadman_adjust(
    cmd: tuple[float, float, float],
    cmd_ts: Optional[float],
    now: float,
    timeout: float,
) -> tuple[float, float, float]:
    """The deadman decision: hold `cmd` only while fresh, else zero.

    `cmd_ts is None` means no command has ever been issued -> zero.
    """
    if cmd_ts is None or (now - cmd_ts) > timeout:
        return (0.0, 0.0, 0.0)
    return cmd


class MotionController:
    """Holds the latest velocity intent and (when connected) drives the dog.

    `set_velocity`/`drive`/`stop` mutate the held command; `state()` reports the
    deadman-adjusted velocity computed for *now*. When a live robot connection is
    present a background loop re-sends the effective velocity at `publish_hz` so
    movement is continuous within the window and stops at the deadman edge.
    """

    def __init__(self, conn, config: MotionConfig) -> None:
        self._conn = conn
        self._cfg = config
        self._lock = threading.Lock()
        self._cmd: tuple[float, float, float] = (0.0, 0.0, 0.0)
        self._cmd_ts: Optional[float] = None
        self._suspend_until: float = 0.0  # velocity loop muted until this monotonic time
        self._walk_ready: bool = False  # have we entered a walk gait for this drive?
        self._walk_enter_until: float = 0.0  # mute loop while RecoveryStand settles
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    @property
    def deadman_window(self) -> float:
        return self._cfg.command_timeout

    @property
    def connected(self) -> bool:
        c = self._conn
        ready = getattr(c, "connection_ready", None)
        return c is not None and ready is not None and ready.is_set()

    def set_velocity(self, vx: float, vy: float, wz: float) -> tuple[float, float, float]:
        vx, vy, wz = clamp(vx, vy, wz, self._cfg.max_linear, self._cfg.max_angular)
        # The WIRELESS_CONTROLLER joystick only WALKS in a locomotion gait; in
        # BalanceStand/posture mode it just tilts the body. A trick leaves the dog
        # in posture, so the first real nudge of a drive enters the walk gait.
        if abs(vx) > 1e-9 or abs(vy) > 1e-9 or abs(wz) > 1e-9:
            self._ensure_walk_mode()
        with self._lock:
            self._cmd = (vx, vy, wz)
            self._cmd_ts = time.monotonic()
            self._suspend_until = 0.0  # explicit motion overrides a trick mute
        return (vx, vy, wz)

    def drive(self, direction: str) -> tuple[float, float, float]:
        vx, vy, wz = direction_to_velocity(
            direction, self._cfg.linear_step, self._cfg.angular_step
        )
        return self.set_velocity(vx, vy, wz)

    def stop(self) -> None:
        """Immediate safe stop: zero the held command and push a zero to the dog.

        Overrides any trick mute — a stop must always reach the dog.
        """
        with self._lock:
            self._cmd = (0.0, 0.0, 0.0)
            self._cmd_ts = time.monotonic()
            self._suspend_until = 0.0
        self._publish((0.0, 0.0, 0.0))

    def suspend(self, seconds: Optional[float] = None) -> None:
        """Mute the velocity publish loop for `seconds` (default cfg.trick_suspend_s).

        Called while a trick (SPORT_MOD action) runs so the loop's zero-velocity
        `move(0,0,0)` stream can't clobber it. Any explicit nav / cmd_vel / stop
        clears the mute — motion and safety always win.
        """
        dur = self._cfg.trick_suspend_s if seconds is None else seconds
        with self._lock:
            self._suspend_until = time.monotonic() + max(0.0, dur)
            self._walk_ready = False  # a trick puts the dog back in posture mode

    def _ensure_walk_mode(self) -> None:
        """Enter a walk gait once per drive (idle→moving) via RecoveryStand.

        The joystick only walks in a locomotion gait; in BalanceStand/posture mode
        it tilts the body. Tricks (and connect) leave the dog in posture, so the
        first real nudge sends RecoveryStand once to switch into the walk gait.
        """
        with self._lock:
            if self._walk_ready:
                return
            self._walk_ready = True
            # Mute the velocity loop while RecoveryStand executes so the joystick
            # stream can't clobber it. Separate from the trick mute and NOT cleared
            # by set_velocity, so concurrent re-pokes (keyboard hold) can't unmute
            # it early; the loop resumes streaming velocity once it lapses.
            self._walk_enter_until = time.monotonic() + self._cfg.walk_enter_settle_s
        if not self._publish_sport("RecoveryStand"):
            with self._lock:
                self._walk_ready = False  # couldn't send (offline) — retry next nudge
                self._walk_enter_until = 0.0

    def _publish_sport(self, move: str) -> bool:
        if not self.connected:
            return False
        try:
            from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD

            self._conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD[move]})
            return True
        except Exception:
            return False

    def _effective(self) -> tuple[tuple[float, float, float], Optional[float]]:
        with self._lock:
            cmd, ts = self._cmd, self._cmd_ts
        now = time.monotonic()
        eff = deadman_adjust(cmd, ts, now, self._cfg.command_timeout)
        age = (now - ts) if ts is not None else None
        return eff, age

    def state(self) -> dict:
        eff, age = self._effective()
        with self._lock:
            raw = self._cmd
        return {
            "moving": any(abs(v) > 1e-9 for v in eff),
            "vx": eff[0],
            "vy": eff[1],
            "wz": eff[2],
            "raw_vx": raw[0],
            "raw_vy": raw[1],
            "raw_wz": raw[2],
            "last_cmd_age_s": age,
            "deadman_window": self._cfg.command_timeout,
            "connected": self.connected,
        }

    def _publish(self, vel: tuple[float, float, float]) -> bool:
        if not self.connected:
            return False
        try:
            # Imported lazily so unit tests of the pure decision never touch dimos.
            from dimos.msgs.geometry_msgs.Twist import Twist
            from dimos.msgs.geometry_msgs.Vector3 import Vector3

            vx, vy, wz = vel
            self._conn.move(
                Twist(Vector3(x=vx, y=vy, z=0.0), Vector3(x=0.0, y=0.0, z=wz))
            )
            return True
        except Exception:  # never let a transport hiccup kill the loop
            return False

    def start(self) -> None:
        """Start the publish loop. No-op without a live connection (state-only)."""
        if self._conn is None:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="YugoMotion"
        )
        self._thread.start()

    def stop_loop(self) -> None:
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self) -> None:
        # Re-send the effective velocity EVERY tick — this must be continuous.
        # The connection's own auto-stop (`stop_movement`) merely cancels a timer;
        # it does NOT command the dog to stop. So a reliable stop depends on us
        # STREAMING zero-velocity after the deadman edge (a single packet can be
        # lost / the firmware holds the last joystick). While suspended (a trick is
        # running) we stay off the channel so the zero stream can't clobber the
        # SPORT_MOD action.
        period = 1.0 / self._cfg.publish_hz
        while not self._stop_event.is_set():
            now = time.monotonic()
            with self._lock:
                suspended = now < self._suspend_until or now < self._walk_enter_until
            if not suspended:
                eff, _ = self._effective()
                self._publish(eff)  # eff is zero once the deadman window lapses
            self._stop_event.wait(period)
