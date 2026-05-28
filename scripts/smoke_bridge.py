#!/usr/bin/env python3
# Pod-side verification for WebBridge — NO robot required.
#
# Wires a synthetic camera -> WebBridge -> a cmd_vel listener, runs the bridge,
# then a driver thread exercises the HTTP API. Verify by grepping stdout for:
#   BRIDGE_FRAME_OK     (camera In -> MJPEG encode path works)
#   HTTP_VIDEO_OK       (GET /video_feed returns a JPEG)
#   BRIDGE_CMD_RECV     (POST /cmd_vel -> Twist published downstream)
#
# Run:  PYTEST_VERSION=1 timeout -s INT 120 python smoke_bridge.py
import json
import os
import sys
import threading
import time
import urllib.request
from pathlib import Path

import numpy as np

BRIDGE_DIR = Path(__file__).resolve().parent.parent / "fastapi"
sys.path.insert(0, str(BRIDGE_DIR))
os.environ["PYTHONPATH"] = str(BRIDGE_DIR) + os.pathsep + os.environ.get("PYTHONPATH", "")

from dimos.core.coordination.blueprints import autoconnect, Blueprint
from dimos.core.coordination.module_coordinator import ModuleCoordinator, _all_name_types
from dimos.core.core import rpc
from dimos.core.module import Module
from dimos.core.stream import In, Out
from dimos.core.transport import pSHMTransport
from dimos.msgs.geometry_msgs.Twist import Twist
from dimos.msgs.sensor_msgs.Image import Image, ImageFormat

from web_bridge import WebBridge

PORT = 5566


class FakeCamera(Module):
    color_image: Out[Image]

    @rpc
    def start(self):
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        while True:
            img = Image.from_numpy(
                np.full((120, 160, 3), 64, np.uint8), format=ImageFormat.RGB, frame_id="cam"
            )
            self.color_image.publish(img)
            time.sleep(0.1)


class CmdListener(Module):
    cmd_vel: In[Twist]

    @rpc
    def start(self):
        self.cmd_vel.subscribe(self._on)

    def _on(self, t: Twist):
        if abs(t.linear.x) > 1e-6 or abs(t.angular.z) > 1e-6:
            print(f"BRIDGE_CMD_RECV vx={t.linear.x:.2f} wz={t.angular.z:.2f}", flush=True)


def force_shm(bp: Blueprint) -> Blueprint:
    return bp.transports(
        {(n, st): pSHMTransport(f"/{n}") for n, st in _all_name_types(bp)}
    )


def _driver():
    base = f"http://127.0.0.1:{PORT}"
    # wait for the server + first frame
    for _ in range(120):
        try:
            h = json.load(urllib.request.urlopen(base + "/healthz", timeout=2))
            if h.get("have_frame"):
                break
        except Exception:
            pass
        time.sleep(1)
    # video
    try:
        r = urllib.request.urlopen(base + "/video_feed/color_image", timeout=5)
        chunk = r.read(4096)
        if b"\xff\xd8" in chunk:  # JPEG SOI
            print("HTTP_VIDEO_OK", flush=True)
    except Exception as e:
        print(f"HTTP_VIDEO_FAIL {e}", flush=True)
    # teleop -> Twist downstream (send a few; deadman needs a recent command)
    for _ in range(10):
        try:
            urllib.request.urlopen(
                urllib.request.Request(
                    base + "/cmd_vel",
                    data=json.dumps({"vx": 0.30, "wz": 0.50}).encode(),
                    headers={"Content-Type": "application/json"},
                ),
                timeout=2,
            )
        except Exception as e:
            print(f"HTTP_CMD_FAIL {e}", flush=True)
            break
        time.sleep(0.1)


if __name__ == "__main__":
    threading.Thread(target=_driver, daemon=True).start()
    bp = autoconnect(
        FakeCamera.blueprint(),
        WebBridge.blueprint(server_port=PORT),
        CmdListener.blueprint(),
    )
    ModuleCoordinator.build(force_shm(bp)).loop()
