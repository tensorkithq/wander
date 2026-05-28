#!/usr/bin/env python3
"""Fire a sequence of Go2 sport tricks over WebRTC.

Usage:
    python go2_trick.py                 # uses ROBOT_IP env or default below
    python go2_trick.py 192.168.203.75  # explicit IP
    python go2_trick.py 192.168.203.75 Hello WiggleHips Stretch  # custom moves
"""
import os
import sys
import time

from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD
from dimos.robot.unitree.connection import UnitreeWebRTCConnection

DEFAULT_IP = "192.168.203.75"

# (move name, seconds to let it finish before the next one)
DEFAULT_ROUTINE = [
    ("RecoveryStand", 4),  # make sure it's upright & balanced first
    ("Hello", 6),          # rear up and wave
    ("WiggleHips", 5),     # shake it
    ("Stretch", 6),        # downward-dog stretch
    ("FingerHeart", 6),    # cute finale on hind legs
    ("BalanceStand", 3),   # settle back to a stable stance
]


def main() -> None:
    args = sys.argv[1:]
    ip = args[0] if args else os.environ.get("ROBOT_IP", DEFAULT_IP)
    moves = args[1:] if len(args) > 1 else [m for m, _ in DEFAULT_ROUTINE]
    delays = {m: d for m, d in DEFAULT_ROUTINE}

    print(f"Connecting to Go2 at {ip} ...")
    conn = UnitreeWebRTCConnection(ip=ip)  # auto-connects in a background thread
    if not conn.connection_ready.wait(timeout=25):
        print("ERROR: WebRTC connection not ready within 25s. Is ROBOT_IP correct and the robot on?")
        sys.exit(1)
    print("Connected. AI motion mode engaged.")

    print("\n⚠️  Robot is about to MOVE. Make sure it's on the floor with ~2m of clear space.")
    for n in (5, 4, 3, 2, 1):
        print(f"  starting in {n}...", end="\r", flush=True)
        time.sleep(1)
    print(" " * 30, end="\r")

    for move in moves:
        cmd_id = SPORT_CMD.get(move)
        if cmd_id is None:
            print(f"  ! unknown move '{move}', skipping")
            continue
        print(f"  ▶ {move} (api_id={cmd_id})")
        conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": cmd_id})
        time.sleep(delays.get(move, 5))

    print("\nDone. 🐕")


if __name__ == "__main__":
    main()
