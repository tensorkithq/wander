from __future__ import annotations

import os
from pathlib import Path

import yaml
from pydantic import BaseModel
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

PKG_DIR = Path(__file__).resolve().parent
ROOT_DIR = PKG_DIR.parent

# --- Database (SQLite) -------------------------------------------------------
DB_PATH = os.environ.get("YUGO_DB", str(ROOT_DIR / "yugo.db"))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},  # FastAPI uses the session across threads
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# --- Robot config (YAML, no secrets) -----------------------------------------
class RobotConfig(BaseModel):
    ip: str = "192.168.203.75"
    connect_timeout: float = 25.0


class MotionConfig(BaseModel):
    max_linear: float = 0.6  # m/s clamp on vx / vy
    max_angular: float = 1.2  # rad/s clamp on wz
    # The deadman window AND the timed-nudge duration are one value: a single
    # nav/cmd_vel call drives for `command_timeout` seconds, then the body
    # auto-zeroes (safe stop). Re-poking within the window extends it.
    command_timeout: float = 0.5
    publish_hz: float = 20.0  # how often the held velocity is (re)sent to the dog
    linear_step: float = 0.4  # forward/back speed for /up,/down nudges (m/s)
    angular_step: float = 0.8  # turn rate for /left,/right nudges (rad/s)
    # While a trick (SPORT_MOD action) runs, the velocity loop is muted this long
    # so its zero-velocity stream can't clobber it. Covers the BalanceStand
    # preamble (trick_balance_settle_s) + the move; raise for long dances. Cleared
    # early by any explicit nav / cmd_vel / stop.
    trick_suspend_s: float = 8.0
    # Expressive moves (WiggleHips/FingerHeart/Stretch/Dance1) are ignored unless
    # Yugo is upright, so those tricks prepend BalanceStand and wait this long for
    # it to settle before firing the move.
    trick_balance_settle_s: float = 1.5
    # On the first nudge of a drive, nav sends RecoveryStand to enter a walk gait
    # (the joystick only walks in locomotion mode, not BalanceStand/posture). The
    # velocity loop is muted this long while RecoveryStand settles.
    walk_enter_settle_s: float = 1.5


class MoodConfig(BaseModel):
    # The body picks a mood every `update_seconds` and (demo) it's random until a
    # vision source replaces it. `poll_seconds` is the cadence the mobile app
    # should poll `GET /api/moods/current` at — advertised, not enforced.
    update_seconds: float = 90.0
    poll_seconds: float = 15.0
    gesture_on_change: bool = True  # fire Yugo's per-mood gesture on each new mood


class Settings(BaseModel):
    robot: RobotConfig = RobotConfig()
    motion: MotionConfig = MotionConfig()
    mood: MoodConfig = MoodConfig()


def _load_settings() -> Settings:
    cfg_path = Path(os.environ.get("YUGO_ROBOT_CONFIG", str(PKG_DIR / "robot.yaml")))
    data: dict = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text()) or {}
    s = Settings(**data)
    # The dog's IP is DHCP; let the env var win for a moved/relocated robot.
    if os.environ.get("ROBOT_IP"):
        s.robot.ip = os.environ["ROBOT_IP"]
    # Tests/dev shrink the deadman window so the HTTP suite runs fast.
    if os.environ.get("YUGO_MOTION_TIMEOUT"):
        s.motion.command_timeout = float(os.environ["YUGO_MOTION_TIMEOUT"])
    # Tests/dev shrink the mood interval to observe changes quickly.
    if os.environ.get("YUGO_MOOD_SECONDS"):
        s.mood.update_seconds = float(os.environ["YUGO_MOOD_SECONDS"])
    return s


settings = _load_settings()
