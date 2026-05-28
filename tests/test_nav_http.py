"""Keyboard-nav + raw teleop over real HTTP, validated from API responses."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _reset(client):
    """Stop between tests so a prior nudge never leaks into the next assertion."""
    yield
    client.post("/stop")


def test_up_drives_forward(client):
    d = client.post("/up").json()
    assert d["action"] == "up"
    assert d["vx"] > 0 and d["vy"] == 0 and d["wz"] == 0
    assert d["duration_s"] > 0  # the nudge auto-stops after this many seconds


def test_down_drives_backward(client):
    assert client.post("/down").json()["vx"] < 0


def test_left_turns_ccw(client):
    d = client.post("/left").json()
    assert d["wz"] > 0 and d["vx"] == 0


def test_right_turns_cw(client):
    d = client.post("/right").json()
    assert d["wz"] < 0 and d["vx"] == 0


def test_nav_velocity_within_clamp(client):
    """Nav steps never exceed the configured envelope."""
    st = client.get("/state").json()
    win = st["deadman_window"]  # noqa: F841 (kept for clarity)
    for direction in ("up", "down", "left", "right"):
        d = client.post(f"/{direction}").json()
        assert abs(d["vx"]) <= 0.6 + 1e-9
        assert abs(d["wz"]) <= 1.2 + 1e-9
        client.post("/stop")


def test_cmd_vel_clamps_out_of_range(client):
    """Raw teleop clamps (not rejects) out-of-range velocities."""
    d = client.post("/cmd_vel", json={"vx": 5.0, "vy": -9.0, "wz": 99.0}).json()
    assert d["vx"] == 0.6  # clamped to max_linear
    assert d["vy"] == -0.6
    assert d["wz"] == 1.2  # clamped to max_angular


def test_cmd_vel_passes_through_in_range(client):
    d = client.post("/cmd_vel", json={"vx": 0.25, "wz": -0.5}).json()
    assert d["vx"] == 0.25 and d["wz"] == -0.5


def test_cmd_vel_defaults_missing_to_zero(client):
    d = client.post("/cmd_vel", json={"vx": 0.3}).json()
    assert d["vx"] == 0.3 and d["vy"] == 0.0 and d["wz"] == 0.0
