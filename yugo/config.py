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
    max_linear: float = 0.6
    max_angular: float = 1.2


class Settings(BaseModel):
    robot: RobotConfig = RobotConfig()
    motion: MotionConfig = MotionConfig()


def _load_settings() -> Settings:
    cfg_path = Path(os.environ.get("YUGO_ROBOT_CONFIG", str(PKG_DIR / "robot.yaml")))
    data: dict = {}
    if cfg_path.exists():
        data = yaml.safe_load(cfg_path.read_text()) or {}
    s = Settings(**data)
    # The dog's IP is DHCP; let the env var win for a moved/relocated robot.
    if os.environ.get("ROBOT_IP"):
        s.robot.ip = os.environ["ROBOT_IP"]
    return s


settings = _load_settings()
