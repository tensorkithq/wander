"""Acceptance contract for the Yugo body **find-mode** (vision servoing — "find Sarah").

TDD / contract-first: find-mode is NOT built yet. These tests encode the contract
from `prd/module-find-mode.md` (+ `prd/module-mode-state-machine.md`). They drive
the REAL app under uvicorn over real HTTP (no mocks), exactly like
`tests/test_mood_http.py` and the `client` fixture in `tests/conftest.py`
(`YUGO_NO_ROBOT=1`).

The whole module is SKIPPED until `POST /mode` exists, so the suite stays GREEN
while the feature is unimplemented. Once `/mode` ships, the skip lifts and these
HTTP-observable assertions become live.

What is testable over HTTP without the dog or the mind:
  - `POST /mode {"mode":"find","target":"Sarah"}` is accepted (200).
  - A target is accepted and the active mode reflects `find`.
  - Entering `find` with NO target behaves per the PRD (which leaves the wiring as
    an open question) — assert it is *handled deliberately*, not 500: either 422
    (target required) or 200 (accepted, awaiting a prompt). See note on the test.

The perception -> 2-nav-commands servoing loop is mind-dependent and cannot be
exercised over plain HTTP offline; it is recorded as an explicit skipped
placeholder describing the expected look->move->look behavior.
"""

from __future__ import annotations

import pytest

from yugo.main import app

# Skip-guard: the whole module is inert until the mode machine / `/mode` ships.
_PATHS = {getattr(r, "path", None) for r in app.routes}
pytestmark = pytest.mark.skipif(
    "/mode" not in _PATHS,
    reason="find-mode / mode machine not implemented yet",
)


def _active_mode(client) -> str | None:
    """Read the body's active mode the way the PRD says it is reflected.

    The mode-state-machine PRD publishes the active mode in the `/ws/state`
    `StateFrame.mode` field, and `POST /mode` echoes `{ok, mode}`. The exact
    read-back surface for the active mode is not frozen yet (open question:
    `GET /mode` vs `/state.mode` vs `/ws/state`), so probe the plausible
    HTTP surfaces and return the first that reports a mode.
    """
    # 1. A dedicated GET /mode, if it exists.
    try:
        r = client.get("/mode")
        if r.status_code == 200:
            body = r.json()
            if isinstance(body, dict) and body.get("mode"):
                return body["mode"]
    except Exception:
        pass
    # 2. The mode mirrored onto /state.
    try:
        body = client.get("/state").json()
        if isinstance(body, dict) and body.get("mode"):
            return body["mode"]
    except Exception:
        pass
    return None


def test_enter_find_mode_with_target_is_accepted(client):
    """POST /mode {"mode":"find","target":"Sarah"} -> 200 and the body accepts it.

    Per the find-mode PRD the target description is supplied when the mode is
    entered (the extended `POST /mode` payload being the leading candidate). The
    request must be accepted and must NOT move the dog (entering a mode never
    publishes velocity — mode-state-machine Safety + find-mode: "entering find
    starts the loop" but the loop only scans/moves under clear-space gating).
    """
    resp = client.post("/mode", json={"mode": "find", "target": "Sarah"})
    assert resp.status_code == 200, resp.text

    body = resp.json()
    assert body.get("ok") is True, body
    # The echoed mode reflects find.
    assert body.get("mode") == "find", body


def test_active_mode_reflects_find_after_enter(client):
    """After entering find, the active mode the body reports is `find`."""
    resp = client.post("/mode", json={"mode": "find", "target": "Sarah"})
    assert resp.status_code == 200, resp.text

    mode = _active_mode(client)
    # If the body exposes the active mode over any HTTP surface, it must say find.
    # (If no read-back surface exists at all, the POST echo above already proved
    # the switch; don't fail on an absent surface.)
    if mode is not None:
        assert mode == "find", f"active mode should be 'find', got {mode!r}"


def test_entering_find_mode_does_not_move_the_dog(client):
    """Switching into find must not, by itself, command any velocity.

    mode-state-machine Safety: "A mode switch does not move the dog." find-mode
    Safety: autonomous motion needs a clear-space ack before the loop may
    translate. So immediately after entering find, /state must show no commanded
    motion attributable to the switch.
    """
    client.post("/stop")  # known-stopped baseline (shared session server)
    resp = client.post("/mode", json={"mode": "find", "target": "Sarah"})
    assert resp.status_code == 200, resp.text

    state = client.get("/state").json()
    # The switch itself issues no command: the body stays as stopped as before.
    assert state["vx"] == 0 and state["vy"] == 0 and state["wz"] == 0, state
    assert state["moving"] is False, state


def test_enter_find_mode_without_target_is_handled_deliberately(client):
    """Entering find with NO target must be a deliberate, documented outcome.

    The find-mode PRD leaves target wiring as an OPEN QUESTION ("Target
    description wiring ... required to drive it") and does not freeze whether a
    targetless find is rejected (422, target required) or accepted (200, the loop
    waits for a target/prompt before servoing). This test pins down only what the
    PRD *does* guarantee: the body handles it deliberately — never a 5xx / unhandled
    error. When the wiring is decided this assertion should be tightened to the
    single chosen behavior.
    """
    client.post("/stop")  # known-stopped baseline (shared session server)
    resp = client.post("/mode", json={"mode": "find"})
    assert resp.status_code in (200, 422), resp.text

    if resp.status_code == 200:
        # Accepted: the switch succeeded and the mode reflects find (loop idles
        # until a target/prompt arrives — it must not start servoing motion).
        body = resp.json()
        assert body.get("ok") is True, body
        assert body.get("mode") == "find", body
        state = client.get("/state").json()
        assert state["moving"] is False, state
    # 422: target is required to enter find — also acceptable per the PRD.


@pytest.mark.skip(reason="needs the mind vision wrapper")
def test_find_servoing_loop_look_move_look():
    """PLACEHOLDER — the perception->action servoing loop (mind-dependent).

    Cannot be exercised over plain HTTP offline; requires the mind GPT-4o vision
    wrapper and a live frame source. The contract this placeholder stands in for
    (`prd/module-find-mode.md`, "Loop state machine" + "two-commands-per-frame"):

      SAMPLE  grab the latest decoded frame from the shared /feed WebRTC buffer.
      ASK     POST {frame, target_description} to the mind vision endpoint.
      ACT     on `{commands: [c1, c2]}`: BalanceStand (upright gate), then execute
              EXACTLY TWO {action, steps} nav commands as clamped, deadman-guarded
              /cmd_vel nudges (action in {forward, back, turn_left, turn_right}).
              A malformed set (not exactly two / unknown action / non-positive
              steps) is rejected -> no motion -> SCAN.
      SCAN    return to stand and tilt/pan to widen the next frame's view.
      ...     loop: move on the command frame, SCAN between frames (look->move->look).
      DONE    on `{action: "sit"}` (target close & centered): fire Sit (api_id 1009)
              and exit the loop cleanly. `sit` is the ONLY success exit.

    Plus the safety invariants to assert once the mind is wired:
      - every move is clamped (vx/vy +/-0.6, wz +/-1.2) and deadman-guarded;
        /state shows the deadman zeroing between nudges.
      - POST /stop aborts the in-flight step immediately (no waiting out the
        command pair) and zeroes motion.
      - a slow / unreachable mind never drives the dog open-loop: it holds/scans
        and the deadman keeps it safe; no stale/guessed commands are executed.
      - exit(find) (a mode switch) cancels the loop with no residual motion.
    """
    raise AssertionError("unreachable: skipped — see docstring for the wired-mind contract")
