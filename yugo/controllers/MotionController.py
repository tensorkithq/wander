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
        # Publish ONLY while a command is fresh; on the deadman edge send exactly
        # one zero, then go quiet — no perpetual move(0,0,0) spam (that clobbers
        # tricks). While suspended (a trick is running) stay off the channel.
        period = 1.0 / self._cfg.publish_hz
        was_active = False
        while not self._stop_event.is_set():
            now = time.monotonic()
            with self._lock:
                suspended = now < self._suspend_until
            if suspended:
                was_active = False  # don't emit a stale closing zero after the trick
            else:
                eff, age = self._effective()
                fresh = age is not None and age <= self._cfg.command_timeout
                if fresh:
                    self._publish(eff)
                    was_active = True
                elif was_active:
                    self._publish((0.0, 0.0, 0.0))  # one closing stop, then quiet
                    was_active = False
            self._stop_event.wait(period)
