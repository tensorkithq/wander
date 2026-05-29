"""Friend mode (conversational step-nav) acceptance over real HTTP — TDD contract.

Encodes the CONTRACT for the body's Friend mode (`prd/module-friend-mode.md`)
BEFORE the module is built. It rides the shared conftest harness: the `client`
fixture boots the REAL app under uvicorn with `YUGO_NO_ROBOT=1` and drives it
over live httpx — the offline reflex layer (`/state`, `/cmd_vel`, `/stop`) is
fully alive, no mocks.

Friend is a branch of the shared mode state machine, selected via
`POST /mode {"mode":"friend"}`. On entry the body-hosted Realtime session takes
a "looking for [person]" persona; the user gives spoken step directions
("2 steps forward, 3 left") which the session parses into a `nav_steps` tool
call; the body translates each step into a clamped, deadman-guarded `/cmd_vel`
nudge, executes one sequence, then waits for the next instruction.

What is testable over HTTP *without* the Realtime session is the mode switch
itself and the safety invariant that switching modes never moves the dog. The
voice -> step -> `/cmd_vel` parsing is Realtime-session-dependent and is recorded
below as an explicit skipped placeholder describing the expected behaviour.

Skip-guard: until the `/mode` route is wired into `yugo.main.app`, the whole
module SKIPS so the suite stays green. The instant the mode machine ships and
registers `/mode`, the HTTP assertions auto-activate.
"""

from __future__ import annotations

import pytest

from yugo.main import app

_PATHS = {getattr(r, "path", None) for r in app.routes}
pytestmark = pytest.mark.skipif(
    "/mode" not in _PATHS, reason="friend-mode / mode machine not implemented yet"
)


def test_set_mode_friend_returns_ok(client):
    """POST /mode {"mode":"friend"} -> 200 and the switch is accepted."""
    r = client.post("/mode", json={"mode": "friend"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["mode"] == "friend"


def test_active_mode_reflects_friend(client):
    """After switching, the active mode observably reflects `friend`.

    Per the PRD the active mode is the single source of truth published into the
    `/ws/state` aggregate (`StateFrame.mode`); the HTTP `GET /state` may also
    surface it. Assert reflection wherever the field is actually exposed. If
    neither read path carries `mode` yet, skip (the switch above already passed).
    """
    r = client.post("/mode", json={"mode": "friend"})
    assert r.status_code == 200, r.text

    state = client.get("/state").json()
    if "mode" in state:
        assert state["mode"] == "friend", state
        return
    pytest.skip("active mode not exposed on GET /state yet")


def test_entering_friend_does_not_move_the_dog(client):
    """SAFETY: entering Friend mode must not drive locomotion.

    Friend's default state is "stopped, listening" — no instruction means no
    motion (PRD: "the body does not drift, repeat the last step, or self-navigate
    while waiting"). All motion only ever flows through the clamped/deadman
    `/cmd_vel` path, never a bare mode change.
    """
    client.post("/stop")
    r = client.post("/mode", json={"mode": "friend"})
    assert r.status_code == 200, r.text

    st = client.get("/state").json()
    assert st["moving"] is False, st
    assert st["vx"] == 0.0 and st["vy"] == 0.0 and st["wz"] == 0.0, st


@pytest.mark.skip(reason="needs the Realtime session")
def test_two_steps_forward_parses_to_clamped_cmd_vel_then_waits(client):
    """PLACEHOLDER — Realtime-session-dependent step-nav contract.

    This is the heart of Friend mode but is NOT testable over plain HTTP: the
    voice -> intent parse lives inside the body-hosted Realtime session (see
    `prd/module-realtime-session.md`), which does not run in this offline harness.

    Expected behaviour once the Realtime session is wired in:

      1. In Friend mode with a named target, a spoken instruction
         ("2 steps forward, 3 steps left") is parsed by the Realtime session
         into `nav_steps` tool call(s) carrying a direction
         (forward|back|left|right|turn_left|turn_right) and a count N.
      2. The body translates each step into one bounded nudge — a clamped
         `/cmd_vel` command held for `step_duration`, re-fed at the publish
         cadence so the deadman never zeroes it mid-step — and sequences N of
         them ("2 steps forward" => 2 discrete deadman-guarded nudges).
      3. Every nudge stays inside the clamp envelope (±0.6 m/s linear,
         ±1.2 rad/s yaw) and is explicitly re-zeroed between steps; a mis-parsed
         large count cannot become one long runaway command.
      4. After executing the sequence the body returns to rest (velocity zeroed,
         deadman idle) and WAITS — yields back to the conversation for the next
         instruction. No drift, no repeat, no self-navigation while waiting.
      5. `/stop` cuts an in-flight sequence at the current nudge immediately.

    The underlying `/cmd_vel` it relies on is ALREADY implemented and
    clamped/deadman-guarded (M0); Friend introduces no new unclamped motion path.
    """
