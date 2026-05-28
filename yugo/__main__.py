"""Run the Yugo body API with default config — non-interactive, no reload.

    .venv/bin/python -m yugo                 # 0.0.0.0:8080, config/env drive the rest
    .venv/bin/python -m yugo --port 9000     # override host/port if needed

Connection comes from config/env (no prompts): set ROBOT_IP=<dog-ip> to connect
(else robot.yaml's default), or YUGO_NO_ROBOT=1 for offline. For the dev workflow
(pass an IP, autoreload on save) use the Makefile: `make serve IP=<dog-ip>` /
`make offline`.
"""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    ap = argparse.ArgumentParser(prog="python -m yugo", description="Run the Yugo body API.")
    ap.add_argument("--host", default="0.0.0.0", help="bind host (default 0.0.0.0)")
    ap.add_argument("--port", type=int, default=8080, help="bind port (default 8080)")
    args = ap.parse_args()

    # No reload, no prompts: yugo.config/lifespan resolve the robot from
    # ROBOT_IP / robot.yaml / YUGO_NO_ROBOT.
    uvicorn.run("yugo.main:app", host=args.host, port=args.port)


if __name__ == "__main__":
    main()
