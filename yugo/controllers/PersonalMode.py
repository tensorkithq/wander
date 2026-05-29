"""Personal mode — the body's **emotional mirror** vision loop.

While ``mode == personal`` the body samples the shared latest-frame buffer at
~1 fps, asks the mind to read the USER's facial mood
(``MindClient.vision_personal``), and mirrors it: it fires one bounded expressive
trick and sets the body's persisted mood (which drives the app aura via
``GET /api/moods/current``).

This is the simplest member of the shared *stream frame → ask mind → act* family
(see ``prd/module-personal-mode.md``). It owns only a background thread; the mode
state machine starts/stops it via the ``enter``/``exit`` hooks. Entering NEVER
moves the dog — reactions fire only on a debounced mood *transition*, and every
per-iteration failure is swallowed so a mind hiccup can never crash the loop or
drive the dog open-loop.

Emotion → reaction map (mind label → trick + persisted body mood / aura color):

    | mind emotion | trick    | body mood     | aura color |
    |--------------|----------|---------------|------------|
    | happy        | Dance1   | playful       | #ff4fa3    |
    | surprised    | Stretch  | zen           | #6a7bff    |
    | sad          | Sit      | calm          | #ffb86c    |
    | fearful      | Sit      | calm          | #ffb86c    |
    | angry        | None     | calm          | #ffb86c    |  (mood only, no trick)
    | disgusted    | None     | calm          | #ffb86c    |  (mood only, no trick)
    | neutral      | None     | (idle, no change) |        |
    | unknown      | None     | (idle, no change) |        |

Body mood labels are the keys of ``MoodController.MOODS`` so ``current_mood`` can
resolve a colour; angry/disgusted persist a calm aura but fire no move (a stable,
low-energy fallback — see PRD Safety). ``facePresent: False`` and neutral/unknown
are idle: no reaction, no mood change.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

from fastapi import FastAPI

from yugo.config import SessionLocal
from yugo.controllers import MoodController, RobotController

# Emotion (from the mind) -> (trick to fire | None, body mood label to persist | None).
# A `None` trick means "set the aura but don't move"; a `None` mood means "idle,
# leave the body mood untouched". Body mood labels MUST be keys of
# MoodController.MOODS so the aura colour resolves.
_REACTIONS: dict[str, tuple[Optional[str], Optional[str]]] = {
    "happy": ("Dance1", "playful"),
    "surprised": ("Stretch", "zen"),
    "sad": ("Sit", "calm"),
    "fearful": ("Sit", "calm"),
    "angry": (None, "calm"),
    "disgusted": (None, "calm"),
    "neutral": (None, None),
    "unknown": (None, None),
}

_SAMPLE_INTERVAL_S = 1.0  # ~1 fps: vision is slow + costs money
_COOLDOWN_S = 5.0  # min seconds between reactions so we don't spam tricks


class PersonalMode:
    """The Personal-mode vision loop, owned by the mode state machine.

    Constructed with the FastAPI ``app`` and reads ``app.state.{frames,mind,robot,
    motion}`` at runtime (so a robot that connects after construction is picked up).
    """

    def __init__(self, app: FastAPI) -> None:
        self._app = app
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._last_mood: Optional[str] = None  # last emotion we reacted to (debounce)
        self._last_reaction_ts: float = 0.0  # monotonic time of the last reaction

    # --- lifecycle hooks (registered with the ModeController) ----------------

    def enter(self) -> None:
        """Start the background loop. Does NOT move the dog by itself."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._last_mood = None
        self._last_reaction_ts = 0.0
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="YugoPersonal"
        )
        self._thread.start()

    def exit(self) -> None:
        """Stop the loop cleanly (signal + join with a timeout)."""
        self._stop.set()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=2.0)

    # --- the loop ------------------------------------------------------------

    def _run(self) -> None:
        # `wait` returns True once stopped, so this also throttles to ~1 fps.
        while not self._stop.wait(_SAMPLE_INTERVAL_S):
            try:
                self._tick()
            except Exception:
                # A mind/transport/DB hiccup must never crash the loop or move the
                # dog open-loop — drop the tick and try again next second.
                pass

    def _tick(self) -> None:
        frames = getattr(self._app.state, "frames", None)
        mind = getattr(self._app.state, "mind", None)
        if frames is None or mind is None or not frames.connected:
            return
        b64 = frames.latest_b64()
        if b64 is None:
            return  # idle before the first frame arrives

        result = mind.vision_personal(b64)  # one in-flight call (loop is serial)
        if not result.get("facePresent"):
            return  # no face -> idle, no reaction
        emotion = result.get("mood", "unknown")
        trick, mood_label = _REACTIONS.get(emotion, (None, None))
        if mood_label is None:
            return  # neutral / unknown -> idle, no mood change

        # Debounce: only react when the emotion CHANGES, and respect a cooldown so
        # a sustained-but-flickering expression can't drive back-to-back moves.
        if emotion == self._last_mood:
            return
        now = time.monotonic()
        if now - self._last_reaction_ts < _COOLDOWN_S:
            return
        self._last_mood = emotion
        self._last_reaction_ts = now

        self._set_mood(mood_label)
        if trick is not None:
            self._fire(trick)

    def _set_mood(self, label: str) -> None:
        """Persist the body mood so the app aura tracks it (one source of truth)."""
        db = SessionLocal()
        try:
            MoodController.set_mood(label, db)
        finally:
            db.close()

    def _fire(self, move: str) -> None:
        """Fire a bounded expressive trick — only when the dog is connected."""
        conn = getattr(self._app.state, "robot", None)
        frames = getattr(self._app.state, "frames", None)
        if conn is None or frames is None or not frames.connected:
            return
        motion = getattr(self._app.state, "motion", None)
        if motion is not None:
            motion.suspend()  # mute the velocity loop while the trick runs
        RobotController.fire(conn, move)
