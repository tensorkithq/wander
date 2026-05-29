"""Acceptance test for the Yugo body **realtime-session** module over real HTTP.

This is the body-hosted voice + tool brain (an OpenAI Realtime session living IN
the body process, with in-process tool calls against the existing controllers).
The primary path is voice in -> voice out + tool execution; `POST /agent/say
{text}` is the **text-only fallback** into that same persona + tool layer,
returning an `AgentReply` (`reply_text` + optional `behavior`).

TDD: this module is NOT built yet. The suite encodes the CONTRACT (from
`prd/module-realtime-session.md` and the `agent` tag / `/agent/say` operation /
`AgentReply` schema in `yugo/openapi.yaml`) and stays GREEN by SKIPPING the whole
module until the `/agent/say` route exists on the app.

Harness: same as `tests/test_mood_http.py` — the real app under uvicorn,
`YUGO_NO_ROBOT=1`, NO mocks. Offline the cloud mind is unreachable, so the
degradation contract (graceful 502/503, body stays safe) is a first-class,
asserted outcome here — not an error.
"""

from __future__ import annotations

import pytest

from yugo.main import app

# --- Skip-guard: keep the suite green until realtime-session is implemented ---
_PATHS = {getattr(r, "path", None) for r in app.routes}
pytestmark = pytest.mark.skipif(
    "/agent/say" not in _PATHS,
    reason="realtime-session not implemented yet",
)

# The behavior.type enum from the AgentReply schema in yugo/openapi.yaml.
_BEHAVIOR_TYPES = {"move", "trick", "led", "mode", "none"}

# Degrade contract: PRD R5 mandates 502 (MindUnreachable) when OpenAI is
# unreachable; the openapi surface also allows 503 for dog-offline tool paths.
# Offline (YUGO_NO_ROBOT=1) either is the correct graceful failure.
_DEGRADE_CODES = {502, 503}


def test_agent_say_returns_reply_or_degrades_gracefully(client):
    """`POST /agent/say {text}` -> a 200 `AgentReply` with non-empty `reply_text`
    (and an optional, well-formed `behavior`), OR a graceful 502/503 when the
    mind is unreachable / the dog is offline (per the degrade contract).

    Offline in CI the cloud Realtime session is unreachable, so a 502/503 is the
    expected, asserted path; the 200 branch encodes the contract for when the
    mind is live. Either way the call must NOT 5xx-crash or hang.
    """
    r = client.post("/agent/say", json={"text": "say hi to everyone"})
    assert r.status_code in ({200} | _DEGRADE_CODES), r.text

    if r.status_code == 200:
        body = r.json()
        # AgentReply requires a non-empty third-person reply_text.
        assert isinstance(body.get("reply_text"), str)
        assert body["reply_text"].strip(), body

        # behavior is optional; when present it must match the schema shape.
        behavior = body.get("behavior")
        if behavior is not None:
            assert isinstance(behavior, dict), body
            if "type" in behavior:
                assert behavior["type"] in _BEHAVIOR_TYPES, behavior
            if "params" in behavior:
                assert isinstance(behavior["params"], dict), behavior
    else:
        # Graceful degradation: a structured error envelope, body stays safe.
        # The reflex layer is independent (asserted separately below); here we
        # only require the failure be clean and not a fabricated reply.
        body = r.json()
        assert isinstance(body, dict), r.text


def test_agent_say_missing_text_is_422(client):
    """`POST /agent/say` with no `text` field -> 422 (request validation).

    `text` is `required` in the operation's requestBody schema.
    """
    r = client.post("/agent/say", json={})
    assert r.status_code == 422, r.text


def test_agent_say_empty_text_is_422(client):
    """`POST /agent/say {"text": ""}` -> 422.

    An empty utterance carries no intent; the brain must reject it rather than
    invent a reply or fire a behavior.
    """
    r = client.post("/agent/say", json={"text": ""})
    assert r.status_code == 422, r.text


def test_agent_say_degrade_keeps_reflex_layer_safe(client):
    """Degradation contract (PRD "Safety"): the cloud session being down must
    NOT touch the reflex layer. After a `/agent/say` call, `/state` and `/stop`
    stay live and observable regardless of session state.
    """
    client.post("/agent/say", json={"text": "say hi to everyone"})

    # Reflex telemetry stays available.
    s = client.get("/state")
    assert s.status_code == 200, s.text
    assert "deadman_window" in s.json(), s.text

    # /stop is supreme — works with the session/mind/link all down.
    stop = client.post("/stop")
    assert stop.status_code == 200, stop.text


@pytest.mark.skip(
    reason="needs the OpenAI Realtime session / mind: full voice-session + "
    "in-process tool-call behavior (voice in -> voice out + a tool executed "
    "in-process against the live controllers) is not exercisable over plain "
    "HTTP and not built yet"
)
def test_realtime_voice_session_executes_inprocess_tool_call():
    """KEYSTONE behavior placeholder (PRD success criteria).

    When wired to an OpenAI Realtime session inside the body:
      - audio in -> Yugo replies in VOICE, in one session, AND
      - when the model decides to act (trick / LED / mode / move), the tool call
        executes IN-PROCESS as a direct call against `RobotController` /
        `MotionController` -- NO HTTP round-trip to the mind -- using the same
        code paths and safety gating (clamps, deadman, BalanceStand suspend) as
        the HTTP routes.
      - `ok` != executed: a tool returns a PUBLISH ack; telemetry is truth.
      - on WS drop the deadman zeroes motion and the session reconnects in the
        background; `/healthz` (or a session-status field) reflects it live.

    This requires real audio transport + OPENAI_API_KEY and a live (or
    simulated) Realtime WS, so it cannot run under the offline HTTP harness.
    Encoded here as an explicit placeholder for the keystone path.
    """
    raise AssertionError("not implemented")
