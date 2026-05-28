"""The deadman switch, validated over real HTTP via the live API's responses.

Core guarantee: a motion command is only honoured while fresh. After the
deadman window elapses with no new command, the body's effective velocity reads
zero. We observe this purely through GET /state (which recomputes the
deadman-adjusted velocity on read) — no mocks, no peeking at internals.
"""

from __future__ import annotations

import time


def test_state_starts_stopped(client):
    """Before any command, the body is stopped (never-commanded -> zero)."""
    st = client.get("/state").json()
    assert st["moving"] is False
    assert (st["vx"], st["vy"], st["wz"]) == (0.0, 0.0, 0.0)
    assert st["last_cmd_age_s"] is None


def test_command_then_deadman_zeroes(client, deadman_window):
    """A nudge moves the body, then the deadman auto-zeroes it after the window."""
    r = client.post("/up")
    assert r.status_code == 200
    assert r.json()["vx"] > 0  # accepted forward velocity

    # Immediately after, the body is moving and the command is fresh.
    st = client.get("/state").json()
    assert st["moving"] is True
    assert st["vx"] > 0
    assert st["last_cmd_age_s"] is not None and st["last_cmd_age_s"] < deadman_window

    # Wait past the deadman window without sending anything.
    time.sleep(deadman_window + 0.2)

    st2 = client.get("/state").json()
    assert st2["moving"] is False, "deadman should have zeroed the velocity"
    assert (st2["vx"], st2["vy"], st2["wz"]) == (0.0, 0.0, 0.0)
    # The raw (last commanded) velocity is retained — only the effective is zeroed.
    assert st2["raw_vx"] > 0


def test_repoking_extends_the_window(client, deadman_window):
    """Re-calling within the window keeps the body alive (key-repeat / hold)."""
    deadline = time.time() + (deadman_window * 2.5)
    while time.time() < deadline:
        client.post("/up")
        time.sleep(deadman_window / 3)
        st = client.get("/state").json()
        assert st["moving"] is True, "held command should not have expired"


def test_stop_zeroes_immediately(client):
    """POST /stop is the panic stop: effective velocity is zero right away."""
    client.post("/up")
    assert client.get("/state").json()["moving"] is True

    r = client.post("/stop")
    assert r.status_code == 200
    assert (r.json()["vx"], r.json()["vy"], r.json()["wz"]) == (0.0, 0.0, 0.0)

    st = client.get("/state").json()
    assert st["moving"] is False
    assert (st["vx"], st["vy"], st["wz"]) == (0.0, 0.0, 0.0)


def test_deadman_offline_does_not_publish(client):
    """Offline, the reflex layer still works but reports not-connected."""
    st = client.get("/state").json()
    assert st["connected"] is False
    assert client.post("/up").json()["connected"] is False
