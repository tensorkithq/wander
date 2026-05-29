"""Acceptance test for the Yugo body **camera-feed** module (`GET /feed`).

TDD / contract-first: the camera-feed module is NOT built yet. This suite
encodes the wire CONTRACT from `prd/module-camera-feed.md` (the authoritative
`/feed` requirement) and the design in
`docs/plans/2026-05-29-webrtc-feed-relay-design.md`, but stays GREEN by SKIPPING
whenever the `/feed` route is absent from the live app. The moment the route
ships, the skip-guard lifts and these assertions activate automatically.

Harness: mirrors `tests/conftest.py` + `tests/test_mood_http.py`. The `client`
httpx fixture boots the REAL app under uvicorn with `YUGO_NO_ROBOT=1`. No mocks.

Per the PRD, `GET /feed` serves a continuous `multipart/x-mixed-replace;
boundary=frame` MJPEG stream (each part `Content-Type: image/jpeg`). The frame
source is the hub's existing WebRTC color-image subscription; before the first
frame arrives the stream yields nothing. Offline (`YUGO_NO_ROBOT=1`) there is no
frame source, so the module may legitimately answer `503` ("no video source")
unless a synthetic source (`YUGO_FEED_FAKE=1`) is enabled — hence we accept
`200`-or-`503` and only validate the streaming content-type/boundary on `200`.

NOTE: the WebRTC relay design also adds sibling paths — `POST /feed/offer`
(WHIP-style signaling), `GET /feed/health` ({viewers, source_active}), and a
deferred snapshot path `GET /feed/frame.jpg` for cheap LLM-vision sampling. This
file deliberately covers only the `GET /feed` stream contract; those siblings
get their own tests when specified/shipped.
"""

from __future__ import annotations

import httpx
import pytest

from yugo.main import app

# Skip-guard: activate only once `/feed` is mounted on the live app.
_PATHS = {getattr(r, "path", None) for r in app.routes}
pytestmark = pytest.mark.skipif(
    "/feed" not in _PATHS, reason="camera-feed not implemented yet"
)

# Streaming-friendly content-types the PRD/design permit. The PRD is explicit:
# `multipart/x-mixed-replace` MJPEG. The WebRTC design may instead serve a video
# stream; either satisfies "an MJPEG/video stream".
_STREAM_CONTENT_TYPES = ("multipart/x-mixed-replace", "video/")


def test_feed_streams_or_503_offline(base_url):
    """`GET /feed` returns a streaming MJPEG/video response, or 503 when no
    frame source exists (offline). On 200, validate the streaming content-type
    and (for MJPEG) the multipart boundary, then read just the FIRST chunk so we
    never block on the infinite stream."""
    # Stream so we don't drain an unbounded MJPEG body; short timeout guards
    # against an open stream that legitimately yields nothing before the first
    # frame.
    with httpx.Client(base_url=base_url, timeout=httpx.Timeout(5.0, read=2.0)) as c:
        with c.stream("GET", "/feed") as r:
            assert r.status_code in (200, 503), (
                f"expected 200 (stream) or 503 (no frame source offline), "
                f"got {r.status_code}"
            )

            if r.status_code == 503:
                # Acceptable offline: no WebRTC frame source / synthetic source.
                return

            ctype = r.headers.get("content-type", "").lower()
            assert any(ctype.startswith(t) or t in ctype for t in _STREAM_CONTENT_TYPES), (
                f"200 /feed must be an MJPEG/video stream; got content-type {ctype!r}"
            )

            if "multipart/x-mixed-replace" in ctype:
                # PRD wire contract: boundary `frame`, parts of image/jpeg.
                assert "boundary=" in ctype, (
                    f"MJPEG stream must declare a boundary; got {ctype!r}"
                )

                # Read only the first chunk; don't block on the infinite stream.
                first = b""
                try:
                    for chunk in r.iter_bytes():
                        first += chunk
                        if len(first) >= 64:
                            break
                except (httpx.ReadTimeout, httpx.RemoteProtocolError):
                    # Stream open but yielding nothing yet (no frame): permitted.
                    first = b""

                if first:
                    boundary = ctype.split("boundary=", 1)[1].strip().strip('"')
                    # The MJPEG part stream is delimited by `--<boundary>` and
                    # each part is `Content-Type: image/jpeg` (PRD `_mjpeg()`).
                    assert (
                        f"--{boundary}".encode() in first
                        or b"image/jpeg" in first.lower()
                    ), f"first MJPEG chunk lacked boundary/jpeg markers: {first[:80]!r}"
