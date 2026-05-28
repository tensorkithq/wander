"""Mood loop + `GET /api/moods/current` over real HTTP (no mocks).

The app boots with the MoodLoop, which seeds an initial mood, so the endpoint
returns a valid, colored mood even offline (`YUGO_NO_ROBOT`).
"""

from __future__ import annotations

from unitree_webrtc_connect.constants import SPORT_CMD

from yugo.controllers.MoodController import MOODS


def test_current_mood_is_valid_and_colored(client):
    m = client.get("/api/moods/current").json()
    assert m["state"] in MOODS, m
    spec = MOODS[m["state"]]
    assert m["color"] == spec["color"]
    assert m["gesture"] == spec["gesture"]
    assert isinstance(m["scalar"], float)
    assert m["color"].startswith("#")


def test_mood_gestures_are_valid_and_safe():
    # Every mood's gesture must be a real SPORT_CMD — and never the removed/broken
    # WiggleHips.
    for label, spec in MOODS.items():
        assert spec["gesture"] in SPORT_CMD, f"{label} -> unknown move {spec['gesture']!r}"
        assert spec["gesture"] != "WiggleHips", f"{label} maps to the removed WiggleHips"


def test_zen_maps_to_stretch():
    assert MOODS["zen"]["gesture"] == "Stretch"
