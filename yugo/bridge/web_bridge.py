#!/usr/bin/env python3
# Reality Instrument — laptop bridge module.
#
# A single DimOS Module that bridges the Go2 to a network client:
#   - color_image: In[Image]  -> served as MJPEG at GET /video_feed/color_image
#   - cmd_vel:     Out[Twist] <- driven by POST /cmd_vel {vx,vy,wz}
#
# It embeds the DimOS FastAPI server (RobotWebInterface) for the app/CORS/run
# plumbing and adds the teleop + video routes. A watchdog (deadman) publishes a
# zero Twist whenever no command has arrived within `command_timeout` seconds, so
# a dropped/backgrounded client stops the dog. Velocities are clamped.

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

import asyncio

import cv2
import uvicorn
from fastapi import Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from dimos.core.core import rpc
from dimos.core.module import Module, ModuleConfig
from dimos.core.stream import In, Out
from dimos.msgs.geometry_msgs.Twist import Twist
from dimos.msgs.geometry_msgs.Vector3 import Vector3
from dimos.msgs.sensor_msgs.Image import Image
from dimos.utils.logging_config import setup_logger
from dimos.web.robot_web_interface import RobotWebInterface

logger = setup_logger()

STATIC_DIR = Path(__file__).resolve().parent / "static"


class WebBridgeConfig(ModuleConfig):
    server_port: int = 5555
    publish_hz: float = 20.0  # how often cmd_vel is (re)published
    command_timeout: float = 0.4  # deadman: stop if no command within this window
    max_linear: float = 0.6  # m/s clamp on vx / vy
    max_angular: float = 1.2  # rad/s clamp on wz


class WebBridge(Module):
    """Network bridge: MJPEG camera out, JSON velocity in -> Twist on cmd_vel."""

    config: WebBridgeConfig

    color_image: In[Image]
    cmd_vel: Out[Twist]

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)

        self._lock = threading.Lock()
        self._cmd: tuple[float, float, float] = (0.0, 0.0, 0.0)  # vx, vy, wz
        self._cmd_ts: float = 0.0
        self._latest_jpeg: bytes | None = None
        self._frame_logged = False

        self._stop_event = threading.Event()
        self._web_thread: threading.Thread | None = None
        self._loop_thread: threading.Thread | None = None

        self._server: uvicorn.Server | None = None
        # RobotWebInterface gives us the FastAPI app + CORS; we drive uvicorn
        # ourselves with an explicit loop (uvicorn's auto loop setup spawns a
        # loop-targeted thread that crashes inside a DimOS forkserver worker).
        self._web = RobotWebInterface(port=self.config.server_port)
        self._setup_routes()

    def _setup_routes(self) -> None:
        app = self._web.app

        @app.get("/healthz")
        async def healthz() -> dict[str, Any]:
            with self._lock:
                age = time.monotonic() - self._cmd_ts if self._cmd_ts else None
            return {
                "ok": True,
                "have_frame": self._latest_jpeg is not None,
                "last_cmd_age_s": age,
            }

        @app.get("/debug", response_class=HTMLResponse)
        async def debug() -> HTMLResponse:
            return HTMLResponse((STATIC_DIR / "debug.html").read_text())

        @app.post("/cmd_vel")
        async def cmd_vel(request: Request) -> JSONResponse:
            try:
                data = await request.json()
            except Exception:
                return JSONResponse(status_code=400, content={"ok": False, "error": "bad json"})
            self._set_cmd(
                float(data.get("vx", 0.0)),
                float(data.get("vy", 0.0)),
                float(data.get("wz", 0.0)),
            )
            return JSONResponse({"ok": True})

        @app.post("/stop")
        async def stop() -> JSONResponse:
            self._set_cmd(0.0, 0.0, 0.0)
            return JSONResponse({"ok": True})

        @app.get("/video_feed/color_image")
        async def video_feed() -> StreamingResponse:
            return StreamingResponse(
                self._mjpeg(),
                media_type="multipart/x-mixed-replace; boundary=frame",
            )

    def _set_cmd(self, vx: float, vy: float, wz: float) -> None:
        c = self.config
        vx = max(-c.max_linear, min(c.max_linear, vx))
        vy = max(-c.max_linear, min(c.max_linear, vy))
        wz = max(-c.max_angular, min(c.max_angular, wz))
        with self._lock:
            self._cmd = (vx, vy, wz)
            self._cmd_ts = time.monotonic()

    def _mjpeg(self):  # type: ignore[no-untyped-def]
        boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        while not self._stop_event.is_set():
            jpeg = self._latest_jpeg
            if jpeg is not None:
                yield boundary + jpeg + b"\r\n"
            time.sleep(1.0 / 30.0)

    def _on_image(self, img: Image) -> None:
        try:
            ok, buf = cv2.imencode(".jpg", img.to_opencv())
            if ok:
                self._latest_jpeg = buf.tobytes()
                if not self._frame_logged:
                    self._frame_logged = True
                    logger.info("BRIDGE_FRAME_OK", w=img.width, h=img.height)
        except Exception:
            logger.exception("frame encode failed")

    @rpc
    def start(self) -> None:
        super().start()
        self.color_image.subscribe(self._on_image)

        self._stop_event.clear()
        self._web_thread = threading.Thread(
            target=self._run_server, daemon=True, name="WebBridgeServer"
        )
        self._web_thread.start()

        self._loop_thread = threading.Thread(
            target=self._publish_loop, daemon=True, name="WebBridgePublish"
        )
        self._loop_thread.start()
        logger.info("WebBridge started", port=self.config.server_port)

    def _run_server(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        config = uvicorn.Config(
            self._web.app,
            host="0.0.0.0",
            port=self.config.server_port,
            log_level="error",
            loop="asyncio",
        )
        self._server = uvicorn.Server(config)
        loop.run_until_complete(self._server.serve())

    @rpc
    def stop(self) -> None:
        self._stop_event.set()
        if self._server is not None:
            self._server.should_exit = True
        if self._loop_thread is not None:
            self._loop_thread.join(timeout=1.0)
            self._loop_thread = None
        super().stop()

    def _publish_loop(self) -> None:
        period = 1.0 / self.config.publish_hz
        while not self._stop_event.is_set():
            with self._lock:
                vx, vy, wz = self._cmd
                age = time.monotonic() - self._cmd_ts if self._cmd_ts else 1e9
            if age > self.config.command_timeout:  # deadman -> stop
                vx = vy = wz = 0.0
            self.cmd_vel.publish(
                Twist(Vector3(x=vx, y=vy, z=0.0), Vector3(x=0.0, y=0.0, z=wz))
            )
            self._stop_event.wait(period)
