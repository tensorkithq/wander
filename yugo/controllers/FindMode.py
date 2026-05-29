"""The body's **find** mode — closed vision-servoing loop ("find Sarah").

Registers as the `find` mode's enter/exit hooks on the mode state machine. While
active it owns ONE background loop that runs the PRD's
SAMPLE -> ASK -> ACT -> SCAN -> DONE cycle, one iteration per streamed frame:

  SAMPLE  grab the latest decoded frame from the shared `FrameSource` (`/feed`).
  ASK     `mind.vision_find(b64, target)` -> {targetVisible, location, decision,
          commands:[{action, steps}]}. The mind returns the nav commands; the body
          only executes them.
  ACT     on `decision == "navigate"`: execute EXACTLY the returned commands
          (capped at two), each mapped to a clamped, deadman-guarded
          `MotionController.drive` nudge — forward->"up", turn_left->"left",
          turn_right->"right" — re-poked `steps` times so the dog keeps moving.
          A malformed set (not 1-2 cmds / unknown action / non-positive steps) is
          rejected: no motion -> SCAN.
  SCAN    a small in-place yaw nudge to widen the next frame's view, then loop.
  DONE    on `decision == "sit"`: fire Sit and stop the loop (the ONLY success exit).

ALL motion routes through the clamped/deadman `MotionController`; the loop never
publishes raw velocity. Every per-iteration error is swallowed so a slow or
unreachable mind never drives the dog open-loop — the body holds/scans and the
deadman zeroes any residual motion. Entering does not move the dog by itself: the
loop starts, but the first move only happens after the first frame + command set.
"""

from __future__ import annotations

import threading
import time

# Cadence: one command-set per ~second (the mind round-trip is slow). To make a
# command's `steps` actually drive the dog, the nudge is re-poked a few times
# within the deadman window so the held velocity stays fresh across the step.
_LOOP_PERIOD_S = 1.0
_NUDGE_REPOKE_S = 0.2  # < deadman window (0.5s); re-issue the held velocity
_NUDGE_REPOKES = 2  # re-pokes per `step` -> ~one deadman window of motion each

_MAX_COMMANDS = 2  # exactly-two-commands-per-frame contract (cap defensively)

# Mind action -> MotionController.drive direction (clamped/deadman nudge).
_ACTION_TO_DRIVE = {
    "forward": "up",
    "turn_left": "left",
    "turn_right": "right",
}


class FindMode:
    """Vision-servoing loop for the `find` mode. Constructed with the FastAPI app;
    reads its collaborators off `app.state` so it always sees the live wiring."""

    def __init__(self, app) -> None:
        self._app = app
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    # --- live collaborators (read off app.state so we never cache a stale conn) -

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
        mode_ctrl = getattr(self._app.state, "mode_ctrl", None)
        return getattr(mode_ctrl, "target", None) or "person"

    # --- mode lifecycle hooks ------------------------------------------------

    def enter(self) -> None:
        """Start the servoing loop (idempotent). Does NOT move the dog by itself —
        the loop only acts once a frame + command set comes back."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="YugoFind")
        self._thread.start()

    def exit(self) -> None:
        """Stop the loop cleanly and zero any residual motion."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)
        motion = self._motion
        if motion is not None:
            try:
                motion.stop()
            except Exception:
                pass

    # --- the loop ------------------------------------------------------------

    def _run(self) -> None:
        # Pace at ~one command-set per second; `wait` returns True on /mode exit so
        # the loop drops out promptly. Every iteration is fully guarded — a slow or
        # unreachable mind must NEVER leave the dog driving open-loop.
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception:
                # Hold position; the deadman zeroes any residual velocity. Never
                # let a transient (mind timeout/502, bad frame) kill the loop or
                # drive the dog on stale data.
                pass
            self._stop.wait(_LOOP_PERIOD_S)

    def _tick(self) -> None:
        frames = self._frames
        mind = self._mind
        if frames is None or mind is None or not frames.connected:
            return  # offline / no source -> hold (no motion)
        b64 = frames.latest_b64()
        if not b64:
            return  # no frame yet -> hold

        # ASK the mind for the next move (or sit). Slow/erroring -> exception ->
        # caught in _run -> hold/retry next iteration; no stale commands executed.
        result = mind.vision_find(b64, self._target)
        decision = (result or {}).get("decision")

        if decision == "sit":
            self._sit()  # the ONLY success exit
            self._stop.set()
            return

        if decision == "navigate":
            commands = (result or {}).get("commands")
            if self._execute(commands):
                return  # moved this frame; next frame decides the next move
            # malformed set -> no motion -> fall through to SCAN

        # navigate-but-rejected, lost target, or any other decision -> SCAN to
        # widen the next view.
        self._scan()

    # --- ACT -----------------------------------------------------------------

    def _execute(self, commands) -> bool:
        """Validate and execute the mind's nav commands. Returns True if a valid
        1-2 command set was executed, False if malformed (-> caller SCANs)."""
        if not isinstance(commands, list) or not (1 <= len(commands) <= _MAX_COMMANDS):
            return False
        # Validate the WHOLE set up front: a malformed set moves the dog on NO frame.
        plan: list[tuple[str, int]] = []
        for cmd in commands:
            if not isinstance(cmd, dict):
                return False
            direction = _ACTION_TO_DRIVE.get(cmd.get("action"))
            steps = cmd.get("steps")
            if direction is None or not isinstance(steps, int) or steps <= 0:
                return False
            plan.append((direction, steps))

        motion = self._motion
        if motion is None:
            return False
        for direction, steps in plan:
            for _ in range(steps):
                if self._stop.is_set():
                    return True  # respect an explicit /stop / mode exit mid-set
                self._nudge(motion, direction)
        return True

    def _nudge(self, motion, direction: str) -> None:
        """One `step`: drive in `direction` and re-poke within the deadman window so
        the held velocity stays fresh for ~one window, then let the deadman zero it."""
        motion.drive(direction)
        for _ in range(_NUDGE_REPOKES):
            if self._stop.is_set():
                return
            time.sleep(_NUDGE_REPOKE_S)
            motion.drive(direction)

    # --- SCAN ----------------------------------------------------------------

    def _scan(self) -> None:
        """Widen the next frame's view: a single small in-place yaw nudge (the Air
        has no pan/tilt head). Clamped/deadman like every other move."""
        motion = self._motion
        if motion is None or self._stop.is_set():
            return
        try:
            motion.drive("left")
        except Exception:
            pass

    # --- DONE ----------------------------------------------------------------

    def _sit(self) -> None:
        conn = self._robot
        if conn is None:
            return  # offline -> nothing to fire; loop still exits as success
        try:
            from yugo.controllers import RobotController

            RobotController.fire(conn, "Sit")
        except Exception:
            pass
