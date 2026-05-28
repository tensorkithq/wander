#!/usr/bin/env python3
"""Terminal WASD teleop for the Go2 over WebRTC — no pygame, no window.

dimos's built-in keyboard teleop opens a pygame window in a worker thread, which
can't work on macOS (Cocoa GUI must be on the main thread). This reads raw
keystrokes from the terminal instead and drives the robot via the same
UnitreeWebRTCConnection.move() API.

Usage:
    python go2_teleop.py                 # uses ROBOT_IP env or default
    python go2_teleop.py 192.168.203.75
"""
import os
import select
import sys
import termios
import tty
import time

from dimos.msgs.geometry_msgs.Twist import Twist
from dimos.robot.unitree.connection import UnitreeWebRTCConnection
from unitree_webrtc_connect.constants import RTC_TOPIC, SPORT_CMD

DEFAULT_IP = "192.168.203.75"

LIN = 0.4   # m/s forward / strafe
ANG = 0.6   # rad/s turn
BURST = 0.35  # seconds of motion per keypress

HELP = """
Go2 terminal teleop — keep THIS terminal focused.
  w / s : forward / backward
  a / d : turn left / right
  q / e : strafe left / right
  space : stop
  z     : stand up (BalanceStand)
  x     : sit down
  Esc/Ctrl-C : quit
"""


def make_twist(fwd=0.0, strafe=0.0, yaw=0.0) -> Twist:
    # move() reads linear.y=forward(+), linear.x=right(+), angular.z=right(+)
    t = Twist()
    t.linear.y = fwd
    t.linear.x = strafe
    t.angular.z = yaw
    return t


def main() -> None:
    ip = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ROBOT_IP", DEFAULT_IP)
    print(f"Connecting to Go2 at {ip} ...")
    conn = UnitreeWebRTCConnection(ip=ip)
    if not conn.connection_ready.wait(timeout=25):
        print("ERROR: WebRTC not ready in 25s. Check ROBOT_IP / robot is on.")
        sys.exit(1)
    print("Connected.")
    # make sure it's standing and balanced before we drive
    conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["BalanceStand"]})
    print(HELP)

    keymap = {
        "w": (LIN, 0, 0), "s": (-LIN, 0, 0),
        "a": (0, 0, -ANG), "d": (0, 0, ANG),
        "q": (0, -LIN, 0), "e": (0, LIN, 0),
    }

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        while True:
            # wait up to 0.5s for a keypress
            if not select.select([sys.stdin], [], [], 0.5)[0]:
                continue
            ch = sys.stdin.read(1)
            if ch in ("\x1b", "\x03"):  # Esc or Ctrl-C
                break
            elif ch == " ":
                conn.move(make_twist(), duration=0.0)
                print("  stop")
            elif ch == "z":
                conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["BalanceStand"]})
                print("  stand")
            elif ch == "x":
                conn.publish_request(RTC_TOPIC["SPORT_MOD"], {"api_id": SPORT_CMD["StandDown"]})
                print("  sit")
            elif ch in keymap:
                fwd, strafe, yaw = keymap[ch]
                conn.move(make_twist(fwd, strafe, yaw), duration=BURST)
                print(f"  {ch}", end="\r")
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        conn.move(make_twist(), duration=0.0)  # final stop
        print("\nStopped. 🐕")


if __name__ == "__main__":
    main()
