"""`POST /agent/say` — talk to Yugo (text).

The text-only front door to Yugo's brain (the realtime-session keystone's
fallback). The utterance runs through OpenAI function-calling with the in-process
tool registry; any tool executes via the existing controllers (same clamps /
deadman / BalanceStand gating as the HTTP routes). Returns `AgentReply`.

Degradation (PRD R5): OpenAI unconfigured/unreachable → 502, reflex layer
untouched. The full audio Realtime session is a follow-up (audio transport is
the PRD's open question); this path + app-side STT/TTS already delivers "talk
to Yugo."
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from yugo.controllers import AgentController
from yugo.controllers.AgentController import AgentUnavailable
from yugo.schemas.AgentSchema import AgentReply, AgentSay

router = APIRouter(tags=["agent"])


@router.post("/agent/say", response_model=AgentReply)
def agent_say(body: AgentSay, request: Request) -> AgentReply:
    try:
        return AgentController.say(request.app, body.text)
    except AgentUnavailable as e:
        # Mind/OpenAI unreachable — never fabricate a reply; the body stays safe.
        raise HTTPException(502, f"agent unavailable (OpenAI unreachable): {e}")
