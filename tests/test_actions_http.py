"""Expressive actions over real HTTP.

The dog isn't attached, so each action route correctly returns 503 (the body
contract: control routes 503 when the link is down) — that response validates
the route is wired. The name->api_id mapping is validated offline via the
self-describing GET /actions and GET /tricks responses.
"""

from __future__ import annotations

import pytest

# Friendly route -> canonical SPORT_CMD move (the contract these routes expose).
EXPECTED_ACTIONS = {
    "hello": "Hello",
    "wiggle": "WiggleHips",
    "heart": "FingerHeart",
    "sit": "Sit",
    "standup": "StandUp",
    "standdown": "StandDown",
    "stretch": "Stretch",
    "dance": "Dance1",
}


def test_actions_catalog_lists_named_actions(client):
    actions = {a["name"]: a for a in client.get("/actions").json()["actions"]}
    for name, move in EXPECTED_ACTIONS.items():
        assert name in actions, f"missing action route /{name}"
        assert actions[name]["move"] == move
        assert isinstance(actions[name]["api_id"], int)


def test_catalog_api_ids_match_known_moves(client):
    actions = {a["name"]: a for a in client.get("/actions").json()["actions"]}
    # Spot-check a few stable Go2 SPORT_CMD ids.
    assert actions["hello"]["api_id"] == 1016
    assert actions["wiggle"]["api_id"] == 1033
    assert actions["heart"]["api_id"] == 1036
    assert actions["sit"]["api_id"] == 1009
    assert actions["standup"]["api_id"] == 1004
    assert actions["standdown"]["api_id"] == 1005


@pytest.mark.parametrize("name", list(EXPECTED_ACTIONS))
def test_action_route_503_when_offline(client, name):
    """Each action route exists and refuses safely with no dog attached."""
    r = client.post(f"/{name}")
    assert r.status_code == 503


def test_tricks_lists_canonical_moves(client):
    tricks = set(client.get("/tricks").json()["tricks"])
    for move in EXPECTED_ACTIONS.values():
        assert move in tricks


def test_unknown_trick_404(client):
    # /trick/{name} resolves names; an unknown one is 404 (when reachable). With
    # no dog the link check happens first (503); either way it is not a 2xx.
    assert client.post("/trick/Nope").status_code in (404, 503)


def test_action_not_overridable_via_query_param(client):
    """A query param must not be able to swap which move a named route fires.

    Offline this is still 503 (link check first), but the route must not accept
    a `move`/`_move` query param at all — guards against the route-factory
    closure leaking its captured value as a FastAPI query parameter.
    """
    schema = client.get("/openapi.json").json()
    hello = schema["paths"]["/hello"]["post"]
    params = {p["name"] for p in hello.get("parameters", [])}
    assert "move" not in params and "_move" not in params


def test_healthz_reports_disconnected_offline(client):
    h = client.get("/healthz").json()
    assert h["ok"] is True
    assert h["connected"] is False
