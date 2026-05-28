"""Wand / spell over real HTTP + pure-engine unit tests.

The shared conftest `app` won't include SensorRouter until the (parallel-owned)
main.py wiring lands, so this module boots the ACTUAL app under uvicorn with the
router included — same harness style as conftest (YUGO_NO_ROBOT=1, real httpx
client, NO mocks). Offline, /sensor/spell still returns its match (fired:false).
"""

from __future__ import annotations

import os
import socket
import threading
import time

os.environ.setdefault("YUGO_NO_ROBOT", "1")
os.environ.setdefault("YUGO_MOTION_TIMEOUT", "0.3")

import httpx
import pytest

from unitree_webrtc_connect.constants import SPORT_CMD

from yugo.controllers import SensorController


# --- live server (router included; mirrors conftest harness) -----------------

def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="module")
def spell_url():
    import uvicorn

    from yugo.main import app
    from yugo.routers import SensorRouter

    if not any(getattr(r, "path", None) == "/sensor/spell" for r in app.routes):
        app.include_router(SensorRouter.router)

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            httpx.get(url + "/healthz", timeout=1.0)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("spell test server did not start")

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def spell_client(spell_url):
    with httpx.Client(base_url=spell_url, timeout=5.0) as c:
        yield c


# --- sample traces -----------------------------------------------------------

def _sweep():
    return [[i * 20, 10.0 + i, -4.0, 40.0 - i * 0.5] for i in range(40)]


def _circle():
    import math
    out = []
    for i in range(48):
        a = 2 * math.pi * i / 24
        out.append([i * 20, 30 * math.cos(a), 30 * math.sin(a), 10.0])
    return out


def _wiggle():
    import math
    return [[i * 20, 20 * math.sin(i * 0.9), 5.0, 35.0] for i in range(36)]


# --- HTTP tests --------------------------------------------------------------

def test_spell_deterministic_same_trace(spell_client):
    body = {"source": "phone-wand", "sample_hz": 50, "magnetometer": _sweep()}
    a = spell_client.post("/sensor/spell", json=body)
    b = spell_client.post("/sensor/spell", json=body)
    assert a.status_code == 200 and b.status_code == 200
    assert a.json()["matched"]["move"] == b.json()["matched"]["move"]
    assert a.json()["matched"]["bucket"] == b.json()["matched"]["bucket"]


def test_spell_distinct_traces_can_differ(spell_client):
    moves = set()
    for trace in (_sweep(), _circle(), _wiggle()):
        r = spell_client.post(
            "/sensor/spell", json={"source": "phone-wand", "magnetometer": trace}
        )
        assert r.status_code == 200
        moves.add(r.json()["matched"]["move"])
    # Sanity: a few clearly different gestures shouldn't all collapse to one.
    assert len(moves) >= 2


def test_spell_move_is_valid_sport_cmd(spell_client):
    r = spell_client.post(
        "/sensor/spell", json={"source": "phone-wand", "magnetometer": _circle()}
    )
    m = r.json()["matched"]
    assert m["move"] in SPORT_CMD
    assert m["api_id"] == SPORT_CMD[m["move"]]


def test_spell_offline_matches_but_does_not_fire(spell_client):
    r = spell_client.post(
        "/sensor/spell", json={"source": "phone-wand", "magnetometer": _sweep()}
    )
    assert r.status_code == 200
    j = r.json()
    assert j["fired"] is False  # no dog attached (YUGO_NO_ROBOT=1)
    assert j["matched"]["move"] in SPORT_CMD


def test_spell_too_short_trace_422(spell_client):
    r = spell_client.post(
        "/sensor/spell", json={"source": "phone-wand", "magnetometer": [[0, 1, 2, 3]]}
    )
    assert r.status_code == 422


def test_sensor_valid_200(spell_client):
    body = {
        "source": "phone-wand",
        "magnetometer": {"x": 12.3, "y": -4.1, "z": 40.2},
        "accel": {"x": 0.1, "y": 0.0, "z": 9.8},
        "light": 320,
        "gesture": "wave",
        "ts": 1716960000.123,
    }
    r = spell_client.post("/sensor", json=body)
    assert r.status_code == 200 and r.json()["ok"] is True


def test_sensor_malformed_422(spell_client):
    # `source` is required; omitting it must 422.
    r = spell_client.post("/sensor", json={"light": 100})
    assert r.status_code == 422


# --- pure unit tests ---------------------------------------------------------

def test_spell_for_trace_deterministic():
    t = _sweep()
    assert SensorController.spell_for_trace(t) == SensorController.spell_for_trace(t)


def test_spell_for_trace_stable_bucket_in_range():
    for trace in (_sweep(), _circle(), _wiggle()):
        out = SensorController.spell_for_trace(trace)
        assert 0 <= out["bucket"] < SensorController.BUCKET_COUNT
        assert out["move"] == SensorController.TRICK_TABLE[out["bucket"]]
        assert out["api_id"] == SPORT_CMD[out["move"]]


def test_spell_for_trace_drift_invariant():
    """Same gesture shape started in a different baseline field hashes the same
    (start-zeroing). Add a constant offset to every sample -> identical bucket."""
    base = _circle()
    shifted = [[s[0], s[1] + 100, s[2] - 50, s[3] + 200] for s in base]
    assert (
        SensorController.spell_for_trace(base)["bucket"]
        == SensorController.spell_for_trace(shifted)["bucket"]
    )
