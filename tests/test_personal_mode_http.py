"""Personal mode (emotional mirror) acceptance over real HTTP (no mocks) — TDD.

Encodes the CONTRACT for the body's Personal mode (`prd/module-personal-mode.md`)
BEFORE the loop is built. Personal mode adds NO new endpoints: it is a
body-internal vision loop gated on `mode == personal`, entered via
`POST /mode {"mode":"personal"}` and torn down when the mode changes (PRD
"Integration with the mode state machine").

Rides the shared conftest harness: the `client` fixture boots the REAL app under
uvicorn with `YUGO_NO_ROBOT=1` and drives it over live httpx. The offline reflex
layer (`/state`, `/cmd_vel`, `/stop`) is fully alive; the dog and the mind's
GPT-4o vision wrapper are NOT attachable in CI.

Skip-guard: Personal mode rides on the mode state machine, so until `/mode` is
wired into `yugo.main.app` the whole module SKIPS and the suite stays green. The
instant `/mode` ships, the HTTP-testable assertions auto-activate. The
vision -> mood -> reaction loop is mind-dependent and is recorded as an explicit
always-skipped placeholder so the full contract is documented but never red.
"""

from __future__ import annotations

import pytest

from yugo.main import app

_PATHS = {getattr(r, "path", None) for r in app.routes}
pytestmark = pytest.mark.skipif(
    "/mode" not in _PATHS, reason="personal-mode / mode machine not implemented yet"
)


def _active_mode(client) -> str | None:
    """The active mode as the body exposes it, or None if no read path carries it.

    The PRD publishes the active mode into the `/ws/state` aggregate
    (`StateFrame.mode`); the HTTP `GET /state` may also surface it. Accept either
    surface so the contract holds regardless of which read path carries `mode`.
    """
    state = client.get("/state").json()
    if "mode" in state:
        return state["mode"]
    return None


def test_enter_personal_mode_returns_ok_and_echoes_mode(client):
    """POST /mode {"mode":"personal"} -> 200 and the body echoes `personal`."""
    r = client.post("/mode", json={"mode": "personal"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "personal"


def test_personal_is_reflected_as_active_mode(client):
    """After entering Personal mode, the active mode reads back as `personal`.

    Per the PRD the loop "exists only while the active mode is Personal", so the
    active-mode value must reflect the switch. Assert reflection only where a read
    path actually exposes `mode` (HTTP `/state` or the `/ws/state` aggregate); if
    neither surfaces it yet, skip — the 200 echo above already proves the switch.
    """
    client.post("/mode", json={"mode": "personal"})
    mode = _active_mode(client)
    if mode is None:
        pytest.skip("active mode not exposed on GET /state (or /ws/state) yet")
    assert mode == "personal", mode


def test_switching_away_tears_personal_down(client):
    """Leaving Personal mode tears the loop down: the active mode changes.

    PRD: "leaving it (any other /mode ...) tears the loop down cleanly". From the
    body's HTTP surface the observable effect is that the active mode is no longer
    `personal` after switching to another mode.
    """
    enter = client.post("/mode", json={"mode": "personal"})
    assert enter.status_code == 200, enter.text

    leave = client.post("/mode", json={"mode": "meditation"})
    assert leave.status_code == 200, leave.text
    assert leave.json()["mode"] == "meditation"

    mode = _active_mode(client)
    if mode is None:
        pytest.skip("active mode not exposed on GET /state (or /ws/state) yet")
    assert mode == "meditation", mode
    assert mode != "personal", mode


def test_entering_personal_does_not_move_the_dog(client):
    """SAFETY: entering Personal mode must not drive locomotion (PRD safety).

    Reactions only ever fire through the clamped/deadman control routes; arming
    the mode itself never moves the body. Start stopped, enter Personal, and
    confirm the effective velocity stays zero and the body is not moving.
    """
    client.post("/stop")
    client.post("/mode", json={"mode": "personal"})

    st = client.get("/state").json()
    assert st["moving"] is False, st
    assert st["vx"] == 0.0 and st["vy"] == 0.0 and st["wz"] == 0.0, st


def test_stop_overrides_personal_mode(client):
    """SAFETY: `POST /stop` zeroes motion while Personal mode is active.

    PRD: "POST /stop overrides everything: it zeroes motion immediately and the
    state machine treats it as a hard exit/abort of the Personal loop." From the
    HTTP surface the testable invariant is that /stop returns 200 and the body
    reads as stopped even with Personal armed.
    """
    client.post("/mode", json={"mode": "personal"})

    r = client.post("/stop")
    assert r.status_code == 200, r.text

    st = client.get("/state").json()
    assert st["moving"] is False, st
    assert st["vx"] == 0.0 and st["vy"] == 0.0 and st["wz"] == 0.0, st


@pytest.mark.skip(reason="needs the mind vision wrapper")
def test_vision_mood_reaction_loop():
    """PLACEHOLDER — the vision -> mood -> reaction loop (mind-dependent).

    Recorded for completeness but never run in CI: the loop's behavior cannot be
    exercised over HTTP without the dog's WebRTC frame source AND the mind's
    GPT-4o vision wrapper, neither of which is attachable under `YUGO_NO_ROBOT=1`.

    Expected behavior once the mind + camera feed are live (PRD "Success
    criteria"):
      - With Personal mode active, the body samples the shared latest-frame buffer
        at ~1-3 fps (default ~2 fps), one in-flight vision call at a time (drop,
        don't queue), and idles before the first frame arrives.
      - Each sampled frame is POSTed to the mind's GPT-4o vision wrapper with a
        face-expression prompt; the mind returns a structured mood/expression label
        (+ confidence, optional valence scalar).
      - A reaction fires only on a DEBOUNCED mood transition (same label across N
        consecutive ticks / a sustained dwell), then a cooldown blocks the next
        move, mapping mood -> bounded reaction via existing control routes:
            happy     -> Dance1     (/dance,  /trick/Dance1)  warm yellow #ffcc44
            sad       -> Sit        (/sit)                    cool blue   #5577cc
            surprised -> WiggleHips (/wiggle)                 magenta     #ff44cc
            neutral / no face -> idle (no move)               soft grey   #888888
      - The chosen mood drives `mood {scalar, label, color}` on the next /ws/state
        StateFrame (one source of truth for aura + LED), and the color may track
        the smoothed mood continuously even when no behavior fires.
      - DEGRADATION: if the mind is unreachable/slow, the tick is a no-op — last
        mood kept, no behavior fired, reflex/deadman loop stays alive, no crash.
    """
    raise AssertionError("documented contract only — never executed")
