"""Acceptance tests for the WebRTC sibling paths of the camera feed:
``POST /feed/offer`` (WHIP-style signaling), ``GET /feed/health``, and the
``GET /feed/cockpit`` viewer — per docs/plans/2026-05-29-webrtc-feed-relay-design.md.

These need a live frame source, so they run only when the synthetic source is
enabled (``YUGO_FEED_FAKE=1``) — mirroring the design's fast-tier test plan
("an injected synthetic frame source ... no heavy in-process WebRTC media
loopback"). Without it the suite SKIPS (the shared offline server has no source,
so ``/feed/offer`` correctly 503s — covered by the offline ``test_feed_http``).

No mocks: the shared ``base_url`` fixture boots the REAL app under uvicorn; we
drive ``/feed/offer`` with a genuine aiortc-generated SDP offer and assert the
hub returns a well-formed answer.
"""

from __future__ import annotations

import asyncio
import os

import httpx
import pytest

from yugo.main import app

_PATHS = {getattr(r, "path", None) for r in app.routes}

pytestmark = pytest.mark.skipif(
    "/feed/offer" not in _PATHS or not os.environ.get("YUGO_FEED_FAKE"),
    reason="WebRTC feed siblings need a frame source (run with YUGO_FEED_FAKE=1)",
)


def test_feed_health_reports_active_source(base_url):
    h = httpx.get(base_url + "/feed/health", timeout=5.0).json()
    assert set(["viewers", "source_active"]).issubset(h)
    assert isinstance(h["viewers"], int) and h["viewers"] >= 0
    assert h["source_active"] is True


def test_feed_cockpit_serves_webrtc_viewer(base_url):
    r = httpx.get(base_url + "/feed/cockpit", timeout=5.0)
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/html")
    # The cockpit drives WebRTC against /feed/offer and reads /ws/state.
    assert "/feed/offer" in r.text and "/ws/state" in r.text


def test_feed_offer_returns_well_formed_answer(base_url):
    """A real aiortc offer → a `type:answer` SDP with a video m-line."""

    async def _run() -> dict:
        from aiortc import RTCPeerConnection

        pc = RTCPeerConnection()
        pc.addTransceiver("video", direction="recvonly")
        await pc.setLocalDescription(await pc.createOffer())
        for _ in range(50):  # wait for ICE gathering (host candidates bundled)
            if pc.iceGatheringState == "complete":
                break
            await asyncio.sleep(0.1)
        offer = pc.localDescription
        try:
            async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as ac:
                res = await ac.post(
                    "/feed/offer", json={"sdp": offer.sdp, "type": offer.type}
                )
                return {"status": res.status_code, "body": res.json()}
        finally:
            await pc.close()

    out = asyncio.run(_run())
    assert out["status"] == 200, f"expected 200, got {out['status']}"
    body = out["body"]
    assert body.get("type") == "answer"
    assert "m=video" in body.get("sdp", ""), "answer must carry a video m-line"


def test_feed_offer_rejects_malformed_body(base_url):
    """Missing `sdp` → 422 (FastAPI/pydantic validation)."""
    r = httpx.post(base_url + "/feed/offer", json={"type": "offer"}, timeout=5.0)
    assert r.status_code == 422
