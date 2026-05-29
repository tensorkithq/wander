"""Body-hosted OpenAI Realtime session — a secure WS bridge with in-process tools.

The keystone voice path (`prd/module-realtime-session.md`). A client connects to
`/agent/realtime`; the body opens a WS to the OpenAI Realtime API (adding
`OPENAI_API_KEY`, which the client never sees) and **relays the event stream both
ways** — audio in/out, transcripts, etc. The SAME tool registry as `/agent/say`
(`AgentController`) is configured on the session, so when the model emits a
function call from a spoken intent, the body runs it **in-process** against the
real controllers (tricks/actions, mode, clamped+deadman nav) and returns the
result to the model. One brain, two front doors: text (`/agent/say`) and voice.

Safety/degradation: no `OPENAI_API_KEY` → the client WS is closed with a status;
a transport failure ends the bridge cleanly. The reflex layer is never touched,
and the blocking tool path runs off the event loop (`asyncio.to_thread`).
"""

from __future__ import annotations

import asyncio
import json
import os

from fastapi import WebSocket, WebSocketDisconnect

from yugo.controllers import AgentController

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime"
REALTIME_MODEL = os.environ.get("YUGO_REALTIME_MODEL", "gpt-4o-realtime-preview")


def _realtime_tools() -> list[dict]:
    """Flatten the chat-style tool schemas into Realtime's flat function shape."""
    out = []
    for t in AgentController._tool_schemas():
        fn = t["function"]
        out.append({
            "type": "function",
            "name": fn["name"],
            "description": fn["description"],
            "parameters": fn["parameters"],
        })
    return out


async def bridge(client_ws: WebSocket, app) -> None:
    await client_ws.accept()
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        await client_ws.send_json({"type": "error", "error": "OPENAI_API_KEY not set"})
        await client_ws.close(code=1011)
        return

    import websockets  # core dep (uvicorn); lazy so import of this module stays cheap

    url = f"{OPENAI_REALTIME_URL}?model={REALTIME_MODEL}"
    headers = {"Authorization": f"Bearer {key}", "OpenAI-Beta": "realtime=v1"}
    try:
        async with websockets.connect(url, additional_headers=headers, max_size=None) as oai:
            # Configure the session with Yugo's persona + the in-process tools.
            await oai.send(json.dumps({
                "type": "session.update",
                "session": {
                    "instructions": AgentController.SYSTEM_PROMPT,
                    "tools": _realtime_tools(),
                    "tool_choice": "auto",
                    "modalities": ["text", "audio"],
                },
            }))
            up = asyncio.create_task(_client_to_oai(client_ws, oai))
            down = asyncio.create_task(_oai_to_client(oai, client_ws, app))
            _, pending = await asyncio.wait({up, down}, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
    except Exception as e:  # transport/handshake — never crash the server
        try:
            await client_ws.send_json({"type": "error", "error": f"realtime bridge failed: {e}"})
        except Exception:
            pass
    finally:
        try:
            await client_ws.close()
        except Exception:
            pass


async def _client_to_oai(client_ws: WebSocket, oai) -> None:
    """Relay client → OpenAI verbatim (audio appends, commits, response.create…)."""
    try:
        while True:
            await oai.send(await client_ws.receive_text())
    except (WebSocketDisconnect, Exception):
        return


async def _oai_to_client(oai, client_ws: WebSocket, app) -> None:
    """Relay OpenAI → client; intercept function calls and run them in-process."""
    async for raw in oai:
        try:
            evt = json.loads(raw)
        except Exception:
            evt = {}
        if evt.get("type") == "response.function_call_arguments.done":
            await _handle_tool_call(oai, client_ws, app, evt)
        try:
            await client_ws.send_text(raw)  # forward audio deltas/transcripts/etc.
        except Exception:
            return


async def _handle_tool_call(oai, client_ws: WebSocket, app, evt: dict) -> None:
    name = evt.get("name", "")
    call_id = evt.get("call_id", "")
    try:
        args = json.loads(evt.get("arguments") or "{}")
    except Exception:
        args = {}
    # _exec_tool is sync and may block (BalanceStand settle) → run off the loop.
    behavior, result = await asyncio.to_thread(AgentController._exec_tool, app, name, args)
    await oai.send(json.dumps({
        "type": "conversation.item.create",
        "item": {
            "type": "function_call_output",
            "call_id": call_id,
            "output": json.dumps({"result": result, "behavior": behavior.model_dump()}),
        },
    }))
    await oai.send(json.dumps({"type": "response.create"}))  # let Yugo narrate it
    try:
        await client_ws.send_json(
            {"type": "yugo.behavior", "behavior": behavior.model_dump(), "result": result}
        )
    except Exception:
        pass
