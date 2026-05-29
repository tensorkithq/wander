"""Schemas for the body's text brain (`POST /agent/say`).

The text-only front door of the realtime-session keystone: an utterance in, a
short in-character `reply_text` out, plus the single `behavior` Yugo applied
(the tool the brain called). Same shapes as the `agent` tag in `openapi.yaml`.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class AgentSay(BaseModel):
    text: str = Field(..., min_length=1, description="What the human says to Yugo.")


class Behavior(BaseModel):
    """The behavior Yugo applied in response — the tool its brain called."""

    type: Literal["move", "trick", "led", "mode", "none"] = "none"
    name: Optional[str] = None
    params: dict[str, Any] = Field(default_factory=dict)


class AgentReply(BaseModel):
    """Yugo's short, third-person reply + the behavior it applied (if any)."""

    reply_text: str = Field(..., description="Short, in-character, third-person line.")
    behavior: Behavior = Field(default_factory=Behavior)
