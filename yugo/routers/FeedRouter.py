"""Camera feed surface (tag `telemetry`):

- `GET  /feed`         — MJPEG `multipart/x-mixed-replace` stream (503 if no source)
- `POST /feed/offer`   — WHIP-style WebRTC signaling → SDP answer (503 if no source)
- `GET  /feed/health`  — `{viewers, source_active}`
- `GET  /feed/cockpit` — HTML cockpit: WebRTC video pane + `/ws/state` telemetry

The feed is non-critical: every path degrades to 503/empty rather than touching
the reflex/deadman layer.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse

from yugo.schemas.RobotSchema import FeedHealth, SdpAnswer, SdpOffer

router = APIRouter(tags=["telemetry"])

_COCKPIT = Path(__file__).resolve().parent.parent / "static" / "cockpit.html"


def _relay(request: Request):
    return getattr(request.app.state, "feed", None)


@router.get("/feed")
def feed(request: Request):
    relay = _relay(request)
    if relay is None or not relay.source_active:
        # Offline / no synthetic source: nothing to stream (hard contract).
        raise HTTPException(503, "no video source")
    return StreamingResponse(
        relay.mjpeg_stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.post("/feed/offer", response_model=SdpAnswer)
def feed_offer(offer: SdpOffer, request: Request):
    relay = _relay(request)
    if relay is None or not relay.source_active:
        raise HTTPException(503, "no video source")
    try:
        answer = relay.answer_sync(offer.sdp, offer.type)
    except Exception:
        # ICE/answer didn't complete in time — viewer can retry.
        raise HTTPException(504, "feed signaling timed out")
    return SdpAnswer(sdp=answer.sdp, type=answer.type)


@router.get("/feed/health", response_model=FeedHealth)
def feed_health(request: Request):
    relay = _relay(request)
    if relay is None:
        return FeedHealth(viewers=0, source_active=False)
    return FeedHealth(**relay.health())


@router.get("/feed/cockpit", response_class=HTMLResponse)
def feed_cockpit():
    return HTMLResponse(_COCKPIT.read_text(encoding="utf-8"))
