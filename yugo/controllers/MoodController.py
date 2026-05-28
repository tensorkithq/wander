from __future__ import annotations

import random
import threading

from sqlalchemy.orm import Session

from yugo.models.MoodEventModel import MoodEventModel
from yugo.schemas.MoodSchema import MoodCreate

# The demo mood set: label -> {color (app aura tint), gesture (SPORT_CMD move
# Yugo performs on entering the mood), scalar (intensity 0..1)}. Gestures are
# safe expressive moves only — NOTE: WiggleHips is intentionally excluded (it was
# removed as broken). `zen` maps to Stretch.
MOODS: dict[str, dict] = {
    "happy":        {"color": "#ffcc44", "gesture": "Hello",       "scalar": 0.8},
    "playful":      {"color": "#ff4fa3", "gesture": "Dance1",      "scalar": 0.95},
    "affectionate": {"color": "#ff79c6", "gesture": "FingerHeart", "scalar": 0.7},
    "calm":         {"color": "#ffb86c", "gesture": "Sit",         "scalar": 0.3},
    "zen":          {"color": "#6a7bff", "gesture": "Stretch",     "scalar": 0.2},
}

_DEFAULT_MOOD = "calm"


def log_mood(data: MoodCreate, db: Session) -> MoodEventModel:
    event = MoodEventModel(**data.model_dump())
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def list_moods(db: Session, limit: int = 100) -> list[MoodEventModel]:
    return (
        db.query(MoodEventModel)
        .order_by(MoodEventModel.created_at.desc())
        .limit(limit)
        .all()
    )


def set_mood(label: str, db: Session, trigger: str = "auto") -> MoodEventModel:
    """Persist a mood transition (bypasses MoodCreate so the loop can write freely)."""
    event = MoodEventModel(state=label, trigger=trigger)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def current_mood(db: Session) -> dict:
    """The latest mood as `{state, color, gesture, scalar, created_at}` for the app
    to poll. Returns a neutral default if none has been recorded yet."""
    latest = (
        db.query(MoodEventModel).order_by(MoodEventModel.created_at.desc()).first()
    )
    label = latest.state if latest is not None else _DEFAULT_MOOD
    spec = MOODS.get(label, MOODS[_DEFAULT_MOOD])
    return {
        "state": label,
        "color": spec["color"],
        "gesture": spec["gesture"],
        "scalar": spec["scalar"],
        "created_at": latest.created_at if latest is not None else None,
    }


class MoodLoop:
    """Background loop: every `update_seconds` pick a mood, persist it to SQLite,
    and (when connected and not mid-drive) make Yugo perform that mood's gesture.

    Demo: the mood is random. Future: replace the source with a camera frame sent
    to a vision API. Either way the app just polls `GET /api/moods/current`.
    Runs even offline (still persists moods so the app has something to poll); it
    only fires a gesture when the dog is connected and idle.
    """

    def __init__(self, conn, motion, session_factory, config) -> None:
        self._conn = conn
        self._motion = motion  # to skip/suspend during an active drive
        self._SessionLocal = session_factory
        self._cfg = config
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def connected(self) -> bool:
        c = self._conn
        ready = getattr(c, "connection_ready", None)
        return c is not None and ready is not None and ready.is_set()

    def start(self) -> None:
        self._tick(fire=False)  # seed an initial mood so /current is populated now
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="YugoMood")
        self._thread.start()

    def stop_loop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.wait(self._cfg.update_seconds):
            self._tick(fire=self._cfg.gesture_on_change)

    def _tick(self, fire: bool) -> None:
        label = random.choice(list(MOODS))  # noqa: S311 — not security-sensitive
        db = self._SessionLocal()
        try:
            set_mood(label, db)
        except Exception:  # never let a DB hiccup kill the loop
            pass
        finally:
            db.close()
        if fire and self.connected and not self._is_moving():
            try:
                from yugo.controllers import RobotController

                if self._motion is not None:
                    self._motion.suspend()  # mute the velocity loop during the gesture
                RobotController.fire(self._conn, MOODS[label]["gesture"])
            except Exception:
                pass

    def _is_moving(self) -> bool:
        try:
            return bool(self._motion is not None and self._motion.state().get("moving"))
        except Exception:
            return False
