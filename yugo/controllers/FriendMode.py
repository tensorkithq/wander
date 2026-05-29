"""Friend mode — the **autonomous-approach** (vision-servo) variant.

The PRD (`prd/module-friend-mode.md`) shapes Friend as *conversational* step-nav:
a body-hosted OpenAI Realtime session adopts a "looking for [person]" persona, the
user gives spoken step directions, and the session parses them into `nav_steps`
tool calls that the body executes. That voice→intent path is **Realtime-dependent
and NOT yet available**, so it is left as a documented follow-up (see the skipped
``test_two_steps_forward_parses_to_clamped_cmd_vel_then_waits`` placeholder in
``tests/test_friend_mode_http.py``).

What we CAN build on today's foundation is the **mind-buildable autonomous
approach**: stream a camera frame → ask the mind to find the named companion
(``mind.vision_friend``) → gently servo toward them through the clamped,
deadman-guarded ``MotionController``. The human is no longer the localizer; the
mind's vision is. This is closer in spirit to Find mode's visual servoing, but
tuned to be *gentle* (small nudges, greet-on-arrival) — a friendly approach, not
a chase.

Safety contract (unchanged from the rest of the body):
- ALL motion flows through ``MotionController`` (clamps ±0.6 m/s / ±1.2 rad/s,
  deadman ~0.5 s). This module never publishes velocity directly.
- A slow / unreachable mind must NEVER drive the dog open-loop: every loop
  iteration is wrapped in a try/except, and motion is only nudged *per verdict*.
  The deadman zeroes velocity ~0.5 s after the last nudge, so a stalled mind call
  simply stops the dog rather than letting it run on the last command.
- ``enter()`` starts the loop but does NOT itself move the dog (no motion until a
  frame + a vision verdict arrive). ``exit()`` stops the loop and zeroes motion.
- ``/stop`` overrides everything via the shared ``MotionController``.
"""

from __future__ import annotations

import threading
import time
from typing import Optional


class FriendMode:
    """Vision-driven gentle approach toward a named companion.

    Constructed with the FastAPI ``app``; reads its collaborators off
    ``app.state`` (``frames``, ``mind``, ``motion``, ``robot``, ``mode_ctrl``) so
    it always sees the live instances even if they are (re)assigned. Registered
    into the mode state machine as the ``friend`` mode's enter/exit hooks.
    """

    # Approach tuning (normalized image coords: x in 0..1, 0.5 == centered).
    # A verdict's `location.x` tells us where the companion is horizontally; we
    # turn toward them until roughly centered, then step forward to close in.
    _CENTER = 0.5
    _CENTER_TOL = 0.15  # within this of center == "facing them, go forward"
    # "Close enough": the mind reports y growing as the person fills more of the
    # frame (nearer/lower in view). At/above this we consider them reached.
    _ARRIVE_Y = 0.75
    _ARRIVE_CONF = 0.5  # ignore low-confidence verdicts for the arrival call
    _PERIOD_S = 1.0  # pace the vision loop ~1 fps (one mind call per tick)

    def __init__(self, app) -> None:
        self._app = app
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # --- live collaborators (read off app.state every access) ----------------

    @property
    def _frames(self):
        return getattr(self._app.state, "frames", None)

    @property
    def _mind(self):
        return getattr(self._app.state, "mind", None)

    @property
    def _motion(self):
        return getattr(self._app.state, "motion", None)

    @property
    def _robot(self):
        return getattr(self._app.state, "robot", None)

    @property
    def _target(self) -> str:
        # The target person is passed into /mode separately; default to "friend"
        # until that wiring lands.
        return getattr(getattr(self._app.state, "mode_ctrl", None), "target", None) or "friend"

    # --- lifecycle hooks ------------------------------------------------------

    def enter(self) -> None:
        """Start the background approach loop. Does NOT move the dog by itself —
        motion only happens once a frame + a vision verdict arrive."""
        if self._thread is not None and self._thread.is_alive():
            return  # idempotent: already looking
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="YugoFriend"
        )
        self._thread.start()

    def exit(self) -> None:
        """Stop the loop cleanly and zero motion (leaving Friend never leaves the
        body moving)."""
        self._stop.set()
        t, self._thread = self._thread, None
        if t is not None:
            t.join(timeout=2.0)
        motion = self._motion
        if motion is not None:
            try:
                motion.stop()
            except Exception:
                pass

    # --- the loop -------------------------------------------------------------

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                # A slow/unreachable mind (or any per-iteration error) must never
                # drive the dog open-loop: swallow it and let the deadman zero
                # velocity ~0.5 s after our last nudge.
                pass
            # Pace ~1 fps; wake immediately on /stop-driven exit.
            self._stop.wait(self._PERIOD_S)

    def _tick(self) -> None:
        frames = self._frames
        motion = self._motion
        mind = self._mind
        # Only act with a live camera + an actual frame (offline => idle/listening).
        if frames is None or motion is None or mind is None or not frames.connected:
            return
        b64 = frames.latest_b64()
        if not b64:
            return

        verdict = mind.vision_friend(b64, self._target)  # may raise -> caught upstream
        if not verdict or not verdict.get("targetVisible"):
            # Don't see them: gently scan in place to look around (small turn).
            motion.drive("left")
            return

        loc = verdict.get("location") or {}
        x = _as_float(loc.get("x"), default=self._CENTER)
        y = _as_float(loc.get("y"), default=0.0)
        conf = _as_float(verdict.get("confidence"), default=0.0)

        offset = x - self._CENTER
        centered = abs(offset) <= self._CENTER_TOL
        close = y >= self._ARRIVE_Y and conf >= self._ARRIVE_CONF

        if centered and close:
            # Found them, facing them, and near: greet once and idle (stop).
            self._greet()
            motion.stop()
            return

        if not centered:
            # Turn toward them: x>center means they're to our right -> turn right.
            motion.drive("right" if offset > 0 else "left")
            return

        # Centered but not yet close: step forward a little to approach.
        motion.drive("up")

    def _greet(self) -> None:
        """A friendly 'found you' reaction. Best-effort: never blocks the loop's
        safety on the robot link, and NEVER WiggleHips (removed)."""
        conn = self._robot
        if conn is None:
            return
        try:
            from yugo.controllers import RobotController

            motion = self._motion
            if motion is not None:
                motion.suspend()  # mute the velocity loop during the gesture
            RobotController.fire(conn, "Hello")
        except Exception:
            pass


def _as_float(value, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
