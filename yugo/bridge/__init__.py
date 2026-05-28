"""DEPRECATED package — the Go2 laptop WebBridge (camera + teleop on :5555).

As of this commit/release (2026-05-29) the WebBridge is **deprecated**. Its
teleop (`/cmd_vel`, `/stop`) and deadman loop are superseded by the unified hub
API (``yugo.main``, port 8080) — see ``yugo/controllers/MotionController.py`` and
the ``control``/``telemetry`` routes in ``yugo/openapi.yaml``.

Only the MJPEG camera stream (``GET /video_feed/color_image``) has no hub
equivalent yet; that is the sole remaining reason to run the bridge, and it will
move to the hub before this package is removed. Do not build new clients against
:5555. See ``yugo/bridge/web_bridge.py`` for the full migration map.
"""
