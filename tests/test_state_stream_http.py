"""Acceptance test for the Yugo body **state-stream** module: ``WS /ws/state``.

TDD / contract-first. The endpoint is *not built yet* (PLANNED in
``yugo/openapi.yaml``). This file encodes the CONTRACT from
``prd/module-state-stream.md`` and the ``StateFrame`` schema so it auto-activates
the moment the route ships. Until then the whole module is SKIPPED (kept green)
via the skip-guard below — FastAPI WebSocket routes register in ``app.routes``
with a ``.path``, so we can detect presence without booting anything.

No mocks: the shared ``base_url`` fixture (see ``tests/conftest.py``) boots the
REAL app under uvicorn with ``YUGO_NO_ROBOT=1``. We connect a real ``ws://``
client (the ``websockets`` library) to the live server.

Per the PRD success criteria, offline (``YUGO_NO_ROBOT=1``) the stream still
pushes frames — robot-sourced fields (battery/pose/imu) may be ABSENT and
``connected`` is false, but mood/mode/last-known fields keep flowing. So the
assertions below tolerate omitted robot fields (every field is optional in
``StateFrame``) while still proving the stream pushes well-formed frames at the
~10–20 Hz cadence.
"""

from __future__ import annotations

import json
import time
from urllib.parse import urlsplit, urlunsplit

import pytest
from websockets.sync.client import connect

from yugo.main import app

# --- Skip-guard: auto-activates when the route ships ------------------------
# WebSocket routes appear in app.routes with a `.path`.
_PATHS = {getattr(r, "path", None) for r in app.routes}
pytestmark = pytest.mark.skipif(
    "/ws/state" not in _PATHS,
    reason="state-stream not implemented yet",
)

# Keep timeouts short so a present-but-broken endpoint fails fast. (When the
# route is absent the skip-guard prevents the run entirely.)
_CONNECT_TIMEOUT = 3.0
_FRAME_TIMEOUT = 2.0
# PRD push cadence is ~10–20 Hz. We assert the inter-frame gap is well under a
# second — generous enough to avoid flakiness on a loaded CI box, strict enough
# to prove the server PUSHES rather than waiting for a client poll.
_MAX_FRAME_GAP_S = 0.9

# Enum of valid behavior modes, per StateFrame.mode in yugo/openapi.yaml.
_VALID_MODES = {"creature", "personal", "friend", "find", "wand", "meditation"}


def _ws_url(base_url: str, path: str = "/ws/state") -> str:
    """Derive a ``ws://`` URL for ``path`` from the http(s) ``base_url`` fixture."""
    parts = urlsplit(base_url)
    scheme = "wss" if parts.scheme == "https" else "ws"
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def _recv_frame(ws) -> dict:
    """Receive one message and decode it as a JSON object (a ``StateFrame``)."""
    msg = ws.recv(timeout=_FRAME_TIMEOUT)
    if isinstance(msg, (bytes, bytearray)):
        msg = msg.decode("utf-8")
    frame = json.loads(msg)
    assert isinstance(frame, dict), f"expected a JSON object StateFrame, got {type(frame)}"
    return frame


def _assert_mood(mood) -> None:
    """A present `mood` must conform to MoodState {scalar, label, color}."""
    assert isinstance(mood, dict), "mood must be a MoodState object"
    assert set(["scalar", "label", "color"]).issubset(mood), (
        f"MoodState requires scalar/label/color, got keys {sorted(mood)}"
    )
    assert isinstance(mood["scalar"], (int, float))
    assert 0.0 <= float(mood["scalar"]) <= 1.0, "mood.scalar must be 0..1"
    assert isinstance(mood["label"], str) and mood["label"]
    assert isinstance(mood["color"], str) and mood["color"]


def _assert_detections(detections) -> None:
    """A present `detections` must be a list of Detection {label,bbox,confidence}."""
    assert isinstance(detections, list), "detections must be an array"
    for det in detections:
        assert isinstance(det, dict), "each detection is an object"
        assert set(["label", "bbox", "confidence"]).issubset(det), (
            f"Detection requires label/bbox/confidence, got {sorted(det)}"
        )
        assert isinstance(det["label"], str)
        bbox = det["bbox"]
        assert isinstance(bbox, list) and len(bbox) == 4, "bbox is [x,y,w,h]"
        assert all(isinstance(v, (int, float)) for v in bbox)
        assert 0.0 <= float(det["confidence"]) <= 1.0


def _assert_stateframe(frame: dict) -> None:
    """Validate a single frame against the StateFrame schema.

    Every field is optional in StateFrame, and offline the robot-sourced fields
    (battery/pose/imu) may be omitted — so we only validate the fields that are
    present, and require that at least one recognized state field exists (the
    frame must carry *something*, not be an empty object).
    """
    known = {
        "battery", "pose", "imu", "mode", "mood",
        "detections", "person_count", "audio_level",
        # connected is an Open-question addition in the PRD; tolerate if present.
        "connected",
    }
    present = set(frame) & known
    assert present, f"StateFrame carried no recognized fields: {sorted(frame)}"

    if "battery" in frame:
        assert isinstance(frame["battery"], (int, float))
        assert 0.0 <= float(frame["battery"]) <= 1.0, "battery is a 0..1 fraction"
    if "mode" in frame:
        assert frame["mode"] in _VALID_MODES, f"unexpected mode {frame['mode']!r}"
    if "mood" in frame:
        _assert_mood(frame["mood"])
    if "detections" in frame:
        _assert_detections(frame["detections"])
    if "person_count" in frame:
        assert isinstance(frame["person_count"], int) and frame["person_count"] >= 0
    if "audio_level" in frame:
        assert 0.0 <= float(frame["audio_level"]) <= 1.0
    if "connected" in frame:
        assert isinstance(frame["connected"], bool)
    if "pose" in frame:
        assert isinstance(frame["pose"], dict)
    if "imu" in frame:
        assert isinstance(frame["imu"], dict)


def test_ws_state_upgrades_and_pushes_a_stateframe(base_url):
    """Connect to ws://<host>/ws/state and receive >=1 well-formed StateFrame."""
    with connect(_ws_url(base_url), open_timeout=_CONNECT_TIMEOUT) as ws:
        frame = _recv_frame(ws)
        _assert_stateframe(frame)


def test_ws_state_pushes_at_high_cadence(base_url):
    """The server PUSHES frames (~10–20 Hz), not on client request.

    We receive two frames back-to-back without sending anything and assert the
    gap between them is well under a second — proving a push loop, not a poll.
    """
    with connect(_ws_url(base_url), open_timeout=_CONNECT_TIMEOUT) as ws:
        first = _recv_frame(ws)
        _assert_stateframe(first)

        t0 = time.monotonic()
        second = _recv_frame(ws)
        gap = time.monotonic() - t0

        _assert_stateframe(second)
        assert gap < _MAX_FRAME_GAP_S, (
            f"second frame arrived after {gap:.3f}s; expected a ~10–20 Hz push "
            f"(gap well under {_MAX_FRAME_GAP_S}s)"
        )


def test_ws_state_runs_offline(base_url):
    """Per the PRD: offline (YUGO_NO_ROBOT=1) the stream still pushes.

    Robot-sourced fields may be absent; if a `connected` field is present it
    must read false offline. The frame must still be a valid StateFrame.
    """
    with connect(_ws_url(base_url), open_timeout=_CONNECT_TIMEOUT) as ws:
        frame = _recv_frame(ws)
        _assert_stateframe(frame)
        if "connected" in frame:
            assert frame["connected"] is False, "offline link must read connected:false"
