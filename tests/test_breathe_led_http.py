"""Acceptance contract for the Yugo body module **breathe-led** (`POST /breathe`,
`POST /led`) over real HTTP (no mocks).

TDD / contract-first: these routes are PLANNED (see `prd/module-breathe-led.md`
and the `/breathe` + `/led` operations in `yugo/openapi.yaml`) and may not be
implemented yet. The whole module is SKIPPED until the routes exist on the live
app, then auto-activates once they ship.

Offline policy (mirrors the rest of the suite): the server boots with
`YUGO_NO_ROBOT=1`, so these robot-bound expressive actions drive the dog over
WebRTC and report `503` when the link is down. Both `200` (accepted/published)
and `503` (link down) are correct, asserted behaviour offline; the contract here
is "accepted or honestly-unavailable, never a 5xx crash and never a wrong code".
"""

from __future__ import annotations

import pytest

from yugo.main import app

_PATHS = {getattr(r, "path", None) for r in app.routes}

pytestmark = pytest.mark.skipif(
    "/breathe" not in _PATHS,
    reason="breathe-led not implemented yet",
)

# 200 = breathing/lamp toggle published; 503 = WebRTC link down offline
# (hard constraint #2). Both are correct per the PRD.
OK_OR_OFFLINE = (200, 503)


def test_breathe_on_with_rate_is_accepted_or_offline(client):
    # PRD: `on:true, rate:6` starts the calm ~6 cycles/min oscillation.
    r = client.post("/breathe", json={"on": True, "rate": 6})
    assert r.status_code in OK_OR_OFFLINE, r.text
    if r.status_code == 200:
        assert r.json().get("ok") is True, r.text


def test_breathe_off_is_accepted_or_offline(client):
    # PRD: `on:false` stops breathing and settles to neutral upright. `rate`
    # is not required when stopping.
    r = client.post("/breathe", json={"on": False})
    assert r.status_code in OK_OR_OFFLINE, r.text
    if r.status_code == 200:
        assert r.json().get("ok") is True, r.text


def test_breathe_requires_on_field(client):
    # openapi: `on` is required on the request body.
    r = client.post("/breathe", json={"rate": 6})
    assert r.status_code == 422, r.text


def test_breathe_out_of_range_rate_is_bounded_or_clamped(client):
    # openapi bounds `rate` to 1..30. The schema either rejects out-of-range
    # (422) or — per the PRD — clamps it rather than rejecting (200/503).
    # Either is an acceptable, safe contract; what must NOT happen is a crash.
    r = client.post("/breathe", json={"on": True, "rate": 999})
    assert r.status_code in (422, *OK_OR_OFFLINE), r.text


def test_led_color_is_accepted_or_offline(client):
    # PRD/openapi: a CSS/hex color sets the front lamp; no motion, safe any time.
    r = client.post("/led", json={"color": "#33ccff"})
    assert r.status_code in OK_OR_OFFLINE, r.text
    if r.status_code == 200:
        assert r.json().get("ok") is True, r.text


def test_led_effect_is_accepted_or_offline(client):
    # openapi: a named effect is the alternative to `color` (anyOf color/effect).
    r = client.post("/led", json={"effect": "breathe"})
    assert r.status_code in OK_OR_OFFLINE, r.text
    if r.status_code == 200:
        assert r.json().get("ok") is True, r.text


def test_led_requires_color_or_effect(client):
    # openapi: `anyOf` color/effect — providing NEITHER is a validation error.
    r = client.post("/led", json={})
    assert r.status_code == 422, r.text
