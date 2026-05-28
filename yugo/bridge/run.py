#!/usr/bin/env python3
# DEPRECATED (2026-05-29) — the WebBridge is superseded by the unified hub API
# (`yugo.main`, port 8080). Prefer `uvicorn yugo.main:app` for teleop/deadman/
# actions; run this bridge only for the MJPEG camera stream, which has no hub
# equivalent yet. See yugo/bridge/web_bridge.py for the migration map.
#
# Reality Instrument — laptop bridge entrypoint.
#
# Runs on the LAPTOP node (on the dog's LAN). Connects to the Go2 over WebRTC and
# serves the camera + teleop bridge for the web debug client / companion app.
#
#   python run.py --robot-ip 192.168.1.123 [--port 5555]
#
# Then open http://<laptop-ip>:5555/debug  (or :5555/debug on the laptop itself).

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

BRIDGE_DIR = Path(__file__).resolve().parent
# WebBridge must be importable by the forkserver worker processes; put its dir on
# both sys.path (this process) and PYTHONPATH (inherited by spawned workers).
sys.path.insert(0, str(BRIDGE_DIR))
os.environ["PYTHONPATH"] = str(BRIDGE_DIR) + os.pathsep + os.environ.get("PYTHONPATH", "")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="DEPRECATED Go2 web/teleop bridge (laptop node) — prefer the hub (yugo.main)"
    )
    ap.add_argument("--robot-ip", required=True, help="Go2 LAN IP (WebRTC LocalSTA)")
    ap.add_argument("--port", type=int, default=5555, help="bridge HTTP port")
    args = ap.parse_args()

    print(
        "[yugo] WARNING: the WebBridge is DEPRECATED (2026-05-29). Teleop/deadman/"
        "actions now live on the hub: `uvicorn yugo.main:app`. Run this bridge only "
        "for the MJPEG camera stream. See web_bridge.py for the migration map.",
        file=sys.stderr,
    )

    from dimos.core.coordination.blueprints import autoconnect
    from dimos.core.coordination.module_coordinator import ModuleCoordinator
    from dimos.robot.unitree.go2.connection import GO2Connection

    from web_bridge import WebBridge

    blueprint = autoconnect(
        GO2Connection.blueprint(),
        WebBridge.blueprint(server_port=args.port),
    ).global_config(robot_ip=args.robot_ip, robot_model="unitree_go2")

    ModuleCoordinator.build(blueprint).loop()


if __name__ == "__main__":
    main()
