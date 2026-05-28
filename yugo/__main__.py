"""Interactive launcher so you don't type the full uvicorn line every session.

    .venv/bin/python -m yugo                 # prompts for the dog's IP (blank = offline)
    .venv/bin/python -m yugo --ip 1.2.3.4    # skip the prompt
    .venv/bin/python -m yugo --offline       # no robot (reflex layer only)
    ROBOT_IP=1.2.3.4 .venv/bin/python -m yugo  # env wins, no prompt

Bakes in host 0.0.0.0 / port 8080 / --reload (override with --host/--port/--no-reload).
Only the robot IP changes per session (DHCP), so that's the one thing we ask for.

This module must NOT import yugo.config/yugo.main before setting ROBOT_IP /
YUGO_NO_ROBOT — the config reads those at import time, so we set the env first,
then let uvicorn import the app.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080
_FALLBACK_IP = "192.168.203.75"


def _default_ip() -> str:
    """Last-known IP for the prompt hint: env > robot.yaml > fallback."""
    if os.environ.get("ROBOT_IP"):
        return os.environ["ROBOT_IP"]
    cfg = Path(os.environ.get("YUGO_ROBOT_CONFIG", str(Path(__file__).parent / "robot.yaml")))
    if cfg.exists():
        try:
            import yaml

            data = yaml.safe_load(cfg.read_text()) or {}
            ip = (data.get("robot") or {}).get("ip")
            if ip:
                return str(ip)
        except Exception:
            pass
    return _FALLBACK_IP


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m yugo", description="Launch the Yugo body API.")
    ap.add_argument("--host", default=DEFAULT_HOST, help=f"bind host (default {DEFAULT_HOST})")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"bind port (default {DEFAULT_PORT})")
    ap.add_argument("--no-reload", dest="reload", action="store_false", help="disable autoreload")
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--ip", help="robot LAN IP (skips the prompt)")
    src.add_argument("--offline", action="store_true", help="run without a robot (reflex layer only)")
    args = ap.parse_args()

    # Resolve the connection mode, then set env BEFORE uvicorn imports the app.
    if args.offline:
        os.environ["YUGO_NO_ROBOT"] = "1"
        mode = "OFFLINE (no robot)"
    elif args.ip:
        os.environ["ROBOT_IP"] = args.ip
        mode = f"robot {args.ip}"
    elif os.environ.get("ROBOT_IP"):
        mode = f"robot {os.environ['ROBOT_IP']} (from env)"
    elif sys.stdin.isatty():
        entered = input(f"Robot IP [{_default_ip()}] (blank = offline): ").strip()
        if entered:
            os.environ["ROBOT_IP"] = entered
            mode = f"robot {entered}"
        else:
            os.environ["YUGO_NO_ROBOT"] = "1"
            mode = "OFFLINE (no robot)"
    else:
        # Non-interactive (piped/CI) with no flag: don't block on input — go offline.
        os.environ["YUGO_NO_ROBOT"] = "1"
        mode = "OFFLINE (no robot; non-interactive, pass --ip to connect)"

    import uvicorn

    print(f"[yugo] {mode} → http://{args.host}:{args.port}  (reload={args.reload})", file=sys.stderr)
    uvicorn.run("yugo.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
