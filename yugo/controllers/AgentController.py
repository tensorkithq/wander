"""Yugo's text brain — `POST /agent/say`: OpenAI function-calling whose tool
handlers execute IN-PROCESS against the existing controllers.

The text fallback of the realtime-session keystone (`prd/module-realtime-session.md`):
same persona + same tool registry the (audio) Realtime session will use, no audio.
Tools reuse the SAME code paths and safety gating as the HTTP routes — clamps,
deadman, BalanceStand precondition, `motion.suspend()` around tricks — so there is
one source of truth (`RobotController`, `MotionController`, `ModeController`).

Degradation (PRD R5 + safety contract): if `OPENAI_API_KEY` is unset or OpenAI is
unreachable, raise `AgentUnavailable` → the router returns 502. The brain is what
makes Yugo *smart*; it never bypasses or stalls the reflex layer.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from yugo.controllers import RobotController
from yugo.schemas.AgentSchema import AgentReply, Behavior

MODEL = os.environ.get("YUGO_AGENT_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = (
    "You are Yugo, a small robot-dog creature — NOT an assistant. Speak in SHORT, "
    "third-person, characterful lines (e.g. 'Yugo tilts its head and waves.'). Never "
    "explain at length, never use lists. One or two playful sentences. You can ACT "
    "using your tools — tricks, a mode switch, or a small clamped nudge — and you only "
    "move in clear space. If your body (the robot link) is unreachable, say so in "
    "character instead of pretending to move."
)


class AgentUnavailable(Exception):
    """OpenAI is unconfigured/unreachable — the router maps this to HTTP 502."""


def _f(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _tool_schemas() -> list[dict]:
    """Realtime/function-call tool schemas. Handlers in `_exec_tool` map 1:1."""
    return [
        {"type": "function", "function": {
            "name": "do_action",
            "description": "Perform one of Yugo's friendly expressive actions.",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "enum": list(RobotController.ACTIONS)}},
                "required": ["name"]}}},
        {"type": "function", "function": {
            "name": "do_trick",
            "description": "Fire any Go2 SPORT_CMD move by exact name (advanced escape hatch).",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string"}}, "required": ["name"]}}},
        {"type": "function", "function": {
            "name": "set_mode",
            "description": "Switch Yugo's active behavior mode.",
            "parameters": {"type": "object", "properties": {
                "mode": {"type": "string"}}, "required": ["mode"]}}},
        {"type": "function", "function": {
            "name": "move",
            "description": ("Nudge Yugo a little: vx forward(+)/back(-), vy left(+)/right(-) "
                            "strafe, wz turn CCW(+). Clamped and auto-stops (deadman) — re-issue "
                            "to keep moving."),
            "parameters": {"type": "object", "properties": {
                "vx": {"type": "number"}, "vy": {"type": "number"}, "wz": {"type": "number"}}}}},
        {"type": "function", "function": {
            "name": "stop",
            "description": "Stop Yugo's movement immediately.",
            "parameters": {"type": "object", "properties": {}}}},
    ]


def _robot_ready(app):
    c = getattr(app.state, "robot", None)
    return c if (c is not None and c.connection_ready.is_set()) else None


def _exec_tool(app, name: str, args: dict) -> tuple[Behavior, str]:
    """Run a tool in-process via the real controllers. Returns (behavior, result
    text for the model). Never raises to the caller — robot-down is a structured
    tool result, not an exception (PRD R2)."""
    motion = getattr(app.state, "motion", None)
    mode_ctrl = getattr(app.state, "mode_ctrl", None)
    conn = _robot_ready(app)

    if name == "do_action":
        a = str(args.get("name", ""))
        move = RobotController.ACTIONS.get(a)
        if move is None:
            return Behavior(), f"unknown action {a!r}"
        if conn is None:
            return Behavior(type="trick", name=a), "robot link down — not sent"
        if motion is not None:
            motion.suspend()  # same gating as ControlRouter: don't clobber the trick
        RobotController.fire(conn, move)
        return Behavior(type="trick", name=a), f"published {move} (publish ack, not execution)"

    if name == "do_trick":
        t = str(args.get("name", ""))
        if conn is None:
            return Behavior(type="trick", name=t), "robot link down — not sent"
        try:
            if motion is not None:
                motion.suspend()
            RobotController.fire(conn, t)
        except Exception as e:  # unknown move etc. -> structured tool error
            return Behavior(), f"trick error: {e}"
        return Behavior(type="trick", name=t), f"published {t} (publish ack)"

    if name == "set_mode":
        m = str(args.get("mode", ""))
        if mode_ctrl is None:
            return Behavior(), "mode controller unavailable"
        try:
            applied = mode_ctrl.set_mode(m)
        except Exception:
            return Behavior(), f"unknown mode {m!r}"
        return Behavior(type="mode", name=applied), f"mode set to {applied}"

    if name == "move":
        if motion is None:
            return Behavior(), "motion unavailable"
        vx, vy, wz = _f(args.get("vx")), _f(args.get("vy")), _f(args.get("wz"))
        cvx, cvy, cwz = motion.set_velocity(vx, vy, wz)  # clamped + deadman-guarded
        return (Behavior(type="move", name="cmd_vel",
                         params={"vx": cvx, "vy": cvy, "wz": cwz}),
                "moving (clamped; auto-stops at the deadman window)")

    if name == "stop":
        if motion is not None:
            motion.stop()
        return Behavior(type="none", name="stop"), "stopped"

    return Behavior(), "no-op"


def _context(app) -> str:
    motion = getattr(app.state, "motion", None)
    mode_ctrl = getattr(app.state, "mode_ctrl", None)
    st = motion.state() if motion is not None else {}
    mode = getattr(mode_ctrl, "mode", "creature") if mode_ctrl is not None else "creature"
    return (
        f"Context: mode={mode}; robot_connected={st.get('connected', False)}; "
        f"moving={st.get('moving')}; vx={st.get('vx')}, wz={st.get('wz')}."
    )


def say(app, text: str) -> AgentReply:
    """One text turn through Yugo's brain. Tools execute in-process; returns the
    reply + the behavior applied. Raises AgentUnavailable (→502) if OpenAI is
    unconfigured/unreachable — the reflex layer is untouched."""
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise AgentUnavailable("OPENAI_API_KEY not set")
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key)
    except Exception as e:  # import/config failure
        raise AgentUnavailable(str(e))

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": _context(app)},
        {"role": "user", "content": text},
    ]
    try:
        first = client.chat.completions.create(
            model=MODEL, messages=messages, tools=_tool_schemas(),
            tool_choice="auto", temperature=0.7,
        )
    except Exception as e:  # transport/auth/rate -> degrade
        raise AgentUnavailable(str(e))

    msg = first.choices[0].message
    behavior = Behavior()
    reply_text = (msg.content or "").strip()

    if msg.tool_calls:
        call = msg.tool_calls[0]
        try:
            args = json.loads(call.function.arguments or "{}")
        except Exception:
            args = {}
        behavior, result = _exec_tool(app, call.function.name, args)
        # Follow-up turn so Yugo narrates the action it just took.
        messages.append(msg.model_dump(exclude_none=True))
        messages.append({"role": "tool", "tool_call_id": call.id, "content": result})
        try:
            second = client.chat.completions.create(
                model=MODEL, messages=messages, temperature=0.7,
            )
            reply_text = (second.choices[0].message.content or "").strip() or reply_text
        except Exception:
            pass  # keep whatever we have; behavior already applied

    if not reply_text:
        reply_text = "Yugo blinks and waits."  # AgentReply requires non-empty text
    return AgentReply(reply_text=reply_text, behavior=behavior)
