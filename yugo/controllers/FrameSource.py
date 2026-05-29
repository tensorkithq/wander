"""Latest camera frame as base64 JPEG — the input the mind's vision calls need.

Taps the robot connection's decoded video stream (`conn.get_video_stream()`, an
``Observable[Image]``) and keeps the most recent frame JPEG-encoded + base64'd, so
a vision-mode loop can grab ``latest_b64()`` without touching the WebRTC plumbing.
Offline (no connection) it simply holds ``None``.
"""

from __future__ import annotations

import base64
import threading
from typing import Optional


class FrameSource:
    def __init__(self, conn) -> None:
        self._conn = conn
        self._lock = threading.Lock()
        self._latest: Optional[str] = None
        self._sub = None

    @property
    def connected(self) -> bool:
        c = self._conn
        ready = getattr(c, "connection_ready", None)
        return c is not None and ready is not None and ready.is_set()

    def start(self) -> None:
        """Subscribe to the camera stream (no-op offline)."""
        if self._conn is None:
            return
        try:
            self._sub = self._conn.get_video_stream().subscribe(self._on_image)
        except Exception:
            self._sub = None

    def _on_image(self, img) -> None:
        try:
            import cv2  # heavy; imported lazily so offline/tests don't pay for it

            ok, buf = cv2.imencode(".jpg", img.to_opencv())
            if ok:
                b64 = base64.b64encode(buf.tobytes()).decode("ascii")
                with self._lock:
                    self._latest = b64
        except Exception:
            pass  # a bad frame must never kill the subscription

    def latest_b64(self) -> Optional[str]:
        """The most recent frame as raw base64 JPEG, or None if none yet."""
        with self._lock:
            return self._latest

    def stop(self) -> None:
        sub, self._sub = self._sub, None
        if sub is not None:
            try:
                sub.dispose()
            except Exception:
                pass
