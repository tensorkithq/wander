"""Camera feed relay — serves the Go2's camera to viewers two ways from one
shared "latest frame":

- **MJPEG** (`GET /feed`): a `multipart/x-mixed-replace` JPEG stream (PRD wire
  contract; the simple, universally-playable path).
- **WebRTC** (`POST /feed/offer`): a WHIP-style single-shot signaling handshake;
  aiortc re-encodes the latest frame to each viewer's peer connection.

Frame source is injectable:
- **real:** `conn.raw_video_stream()` — a memoized RxPY `Observable[av.VideoFrame]`
  on the dog connection (per docs/plans/2026-05-29-webrtc-feed-relay-design.md).
- **synthetic:** color-bar frames when `YUGO_FEED_FAKE=1` — lets the stream +
  signaling be exercised with no dog (and is the fast-tier test source).

All outbound aiortc objects live on ONE dedicated asyncio loop (its own thread),
so aiortc never spans loops. Inbound frames cross to it under a lock. The feed is
non-critical telemetry: it may fail freely and shares no state with the
deadman/reflex layer.
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from fractions import Fraction
from typing import Optional


def _make_camera_track(relay: "FeedRelay"):
    """Build an aiortc video track that emits the relay's shared latest frame,
    paced to target fps with monotonic timestamps. aiortc is imported here (not at
    module load) so importing this module never requires aiortc."""
    from aiortc import MediaStreamTrack

    class RobotCameraTrack(MediaStreamTrack):
        kind = "video"

        def __init__(self) -> None:
            super().__init__()
            self._relay = relay
            self._pts = 0
            self._time_base = Fraction(1, 90000)  # 90 kHz video clock

        async def recv(self):
            import av

            fps = max(1.0, self._relay.target_fps)
            await asyncio.sleep(1.0 / fps)
            frame = self._relay.latest()
            if frame is None:
                import numpy as np

                # No frame yet — emit black so negotiation/decoding doesn't stall.
                frame = av.VideoFrame.from_ndarray(
                    np.zeros((480, 640, 3), dtype=np.uint8), format="rgb24"
                )
            self._pts += int(self._time_base.denominator / fps)
            frame.pts = self._pts
            frame.time_base = self._time_base
            return frame

    return RobotCameraTrack()


class FeedRelay:
    def __init__(self, conn, config, fake: bool = False) -> None:
        self._conn = conn
        self._cfg = config
        self._fake = fake
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._ready = threading.Event()
        self._latest = None  # av.VideoFrame
        self._lock = threading.Lock()
        self._pcs: set = set()
        self._subscription = None  # RxPY disposable (real source)
        self._fake_task: Optional[asyncio.Task] = None
        self._source_active = False

    @property
    def target_fps(self) -> float:
        return float(self._cfg.target_fps)

    @property
    def source_active(self) -> bool:
        return self._source_active

    # --- frame plumbing -----------------------------------------------------
    def set_frame(self, frame) -> None:
        with self._lock:
            self._latest = frame

    def latest(self):
        with self._lock:
            return self._latest

    def latest_jpeg(self) -> Optional[bytes]:
        frame = self.latest()
        if frame is None:
            return None
        try:
            img = frame.to_image()
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=int(self._cfg.jpeg_quality))
            return buf.getvalue()
        except Exception:
            return None

    # --- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._thread = threading.Thread(target=self._run_loop, daemon=True, name="YugoFeed")
        self._thread.start()
        self._ready.wait(timeout=5.0)
        if self._fake:
            self._source_active = True
            asyncio.run_coroutine_threadsafe(self._run_fake_source(), self._loop)
        else:
            self._attach_real_source()

    def _run_loop(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._ready.set()
        self._loop.run_forever()

    def _attach_real_source(self) -> None:
        """Subscribe to the dog's decoded-frame observable. Best-effort: if the
        connection or the `raw_video_stream` API is absent, the source stays
        inactive (→ /feed 503) rather than crashing."""
        conn = self._conn
        if conn is None:
            return
        try:
            obs = conn.raw_video_stream()  # Observable[av.VideoFrame] (dimos)
            self._subscription = obs.subscribe(
                on_next=self.set_frame,
                on_error=lambda _e: self._mark_source(False),
                on_completed=lambda: self._mark_source(False),
            )
            self._source_active = True
        except Exception:
            self._source_active = False

    def _mark_source(self, active: bool) -> None:
        self._source_active = active

    async def _run_fake_source(self) -> None:
        """Generate color-bar frames at the target fps (no dog needed)."""
        import av
        import numpy as np

        self._fake_task = asyncio.current_task()  # so close() can cancel it

        h, w = 480, 640
        bars = np.zeros((h, w, 3), dtype=np.uint8)
        palette = [
            (255, 255, 255), (255, 255, 0), (0, 255, 255), (0, 255, 0),
            (255, 0, 255), (255, 0, 0), (0, 0, 255),
        ]
        seg = w // len(palette)
        for i, c in enumerate(palette):
            bars[:, i * seg:(i + 1) * seg] = c
        i = 0
        while True:
            # A moving marker bar so successive frames differ.
            frame_arr = bars.copy()
            x = (i * 8) % w
            frame_arr[:, x:min(x + 8, w)] = (0, 0, 0)
            self.set_frame(av.VideoFrame.from_ndarray(frame_arr, format="rgb24"))
            i += 1
            await asyncio.sleep(1.0 / max(1.0, self.target_fps))

    # --- WebRTC signaling (runs ON the relay loop) --------------------------
    async def create_answer(self, offer_sdp: str, offer_type: str = "offer"):
        from aiortc import RTCConfiguration, RTCPeerConnection, RTCSessionDescription

        pc = RTCPeerConnection(RTCConfiguration(iceServers=[]))  # LAN: no STUN/TURN
        self._pcs.add(pc)

        @pc.on("connectionstatechange")
        async def _on_state() -> None:
            if pc.connectionState in ("failed", "closed", "disconnected"):
                await pc.close()
                self._pcs.discard(pc)

        pc.addTrack(_make_camera_track(self))
        await pc.setRemoteDescription(RTCSessionDescription(sdp=offer_sdp, type=offer_type))
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)
        # Non-trickle: localDescription now bundles the gathered host candidates.
        return pc.localDescription

    def answer_sync(self, offer_sdp: str, offer_type: str, timeout: float = 5.0):
        """Thread-safe entry from the uvicorn loop: marshal create_answer to the
        relay loop and block for the result."""
        fut = asyncio.run_coroutine_threadsafe(
            self.create_answer(offer_sdp, offer_type), self._loop
        )
        return fut.result(timeout=timeout)

    # --- introspection ------------------------------------------------------
    def health(self) -> dict:
        return {"viewers": len(self._pcs), "source_active": self._source_active}

    async def mjpeg_stream(self):
        """Async generator of multipart/x-mixed-replace parts (boundary `frame`).

        Runs on the uvicorn loop (StreamingResponse). Paces to target fps and
        serves only the latest frame (drops stale → bounded latency).
        """
        boundary = b"--frame\r\n"
        fps = max(1.0, self.target_fps)
        deadline = time.monotonic() + 2.0  # give the first frame a moment to arrive
        while True:
            jpeg = self.latest_jpeg()
            if jpeg is not None:
                yield boundary + b"Content-Type: image/jpeg\r\n"
                yield f"Content-Length: {len(jpeg)}\r\n\r\n".encode()
                yield jpeg + b"\r\n"
            elif time.monotonic() > deadline:
                # No frame after the grace window; keep the stream open but idle.
                pass
            await asyncio.sleep(1.0 / fps)

    def close(self) -> None:
        if self._subscription is not None:
            try:
                self._subscription.dispose()
            except Exception:
                pass
        loop = self._loop
        if loop is None:
            return

        async def _shutdown() -> None:
            if self._fake_task is not None:
                self._fake_task.cancel()
            for pc in list(self._pcs):
                try:
                    await pc.close()
                except Exception:
                    pass
            self._pcs.clear()

        try:
            asyncio.run_coroutine_threadsafe(_shutdown(), loop).result(timeout=3.0)
        except Exception:
            pass
        loop.call_soon_threadsafe(loop.stop)
