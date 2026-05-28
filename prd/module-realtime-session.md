# PRD — Realtime Session (the body's voice + tool brain)

**Date:** 2026-05-28 · **Status:** draft · **Phase:** 2 — Talk to Yugo (keystone) · **Lives in:** `wander/yugo/`

## Objective
Host the **OpenAI Realtime API** WebSocket session **inside the body process** so Yugo can be
talked to: voice in → voice out **plus** tool calls, all in one session. When the model decides to
act (trick, LED, mode, movement), the tool call executes **in-process** as a direct function call
against the existing controllers — **no HTTP round-trip to the mind**. This is the central design
point: the body is the orchestrator, the Realtime session is its brain, and the mind stays a thin
stateless perception/STT wrapper that only *feeds* context in.

This is the keystone of the demo arc. Everything in Phase 3/4 (Friend, Find, Meditation) leans on
the session and tool registry built here.

## Scope
- A single Realtime session manager living in the body process, owning the WS link to OpenAI.
- A **tool registry** mapping Realtime function-call tools onto existing body actions: the friendly
  expressive actions (`hello`/`wiggle`/`heart`/`sit`/`standup`/`standdown`/`stretch`/`dance`), the
  generic `/trick/{name}` escape hatch, `/led`, `/mode`, and clamped/deadman-guarded `/cmd_vel` nav.
- **Context injection** into the session: live robot state (`MotionController.state()` + WebRTC
  health), the mind's GPT-4o vision results (scene/detections/mood), and the current behavior mode.
- **Yugo personality** in the system prompt: short, third-person, characterful lines.
- `POST /agent/say {text}` as a **text-only fallback** path (returns `AgentReply`) for clients
  without audio — same tool execution, no voice.
- A **degradation contract**: if the session drops or OpenAI is unreachable, the body stays safe.

## Non-goals
- **Audio transport to/from clients.** The Realtime audio in/out is wired to a client; *how* those
  audio streams reach the phone/test harness (relay vs. direct, codec, framing) is out of scope here
  and tracked as an open question. This module owns the *session and tools*, not the audio pipe.
- **STT/TTS in the body.** Realtime does its own speech; the mind's Deepgram/Whisper wrappers remain
  the fallback STT for the `/agent/say` text path only. The body never holds audio bytes for storage.
- **Vision.** Frames are sampled and sent to the mind elsewhere (Phase 1); this module only *consumes*
  the structured result the mind returns.
- **Mode state machines** (Find servoing, wand hash) — Phase 3. This module only switches the active
  mode and lets it color the session prompt/toolset.

## Requirements

### R1 — Session lifecycle
- A `RealtimeSession` manager (one per body process) connects to OpenAI Realtime over WS, keyed by
  `OPENAI_API_KEY`, configured with the system prompt, voice, and the tool schemas from the registry.
- The session is created lazily / on demand (see open question on initiation), not at body startup —
  body startup must not depend on OpenAI reachability.
- The session runs as an asyncio task alongside the existing `MotionController` loop; it never blocks
  the reflex layer or the `uvicorn` event loop.
- **Reconnect on drop**, mirroring the WebRTC link's posture (hard constraint #2): a dropped Realtime
  WS does not self-heal silently — the manager detects close, backs off, and reconnects, surfacing
  live status on `/healthz` (or a session-status field) so clients can reflect it.
- Clean teardown on lifespan shutdown: cancel the task, close the WS, leave the robot in a safe stance.

### R2 — Tool registry (in-process execution)
- Define Realtime **function tools** whose handlers call the existing controllers directly:
  | Tool | In-process target | Notes |
  |---|---|---|
  | `do_action(name)` | `RobotController.fire(conn, ACTIONS[name])` | hello/wiggle/heart/sit/standup/standdown/stretch/dance |
  | `do_trick(name)` | `RobotController.fire(conn, name)` | generic SPORT_CMD escape hatch; 404-equivalent → tool error |
  | `set_led(color?, effect?)` | LED/VUI publish | mood color or named effect |
  | `set_mode(mode)` | body mode switch | `creature\|ghost\|hunt\|scanner\|music\|meditation` |
  | `move(vx, vy, wz, [duration])` | `MotionController.set_velocity(...)` | clamped + deadman-guarded; a timed nudge, re-issued for sustained motion |
  | `stop()` | `MotionController.stop()` | always available |
- Tool handlers reuse the **same code paths and safety gating** as the HTTP routes — no parallel
  control logic. One source of truth (`RobotController`, `MotionController`).
- Expressive moves keep the **BalanceStand precondition** (`NEEDS_BALANCE`) and the body must
  `motion.suspend()` around a fired trick exactly as `ControlRouter` does, so the velocity loop can't
  clobber the SPORT_MOD action.
- **`ok` ≠ executed** (hard constraint #3): a tool returns a PUBLISH ack, not an execution ack. Tool
  results sent back to the model say "published," and telemetry — not the tool result — is truth.
- A tool that requires the robot while the WebRTC link is down returns a **structured tool error**
  (the model can narrate "Yugo can't reach its body right now"), it does **not** raise to the client.
- The registry is the single declarative source for both the Realtime tool schemas and the handlers.

### R3 — Context injection
- Before/within the session, inject a compact context blob the model can reason over:
  - **Robot state:** `MotionController.state()` (moving/effective velocity, deadman), connection
    health, current stance if known.
  - **Vision:** the latest structured result from the mind's GPT-4o vision wrapper
    (scene description, detections, person_count, face expression / mood).
  - **Mode:** the current active behavior mode, which also conditions personality and available tools.
- Injected as session/context updates (e.g. a refreshed system or context item), not by reopening the
  session, and rate-limited so it does not spam the model. Vision is best-effort: stale or missing
  vision must not stall the session.

### R4 — Personality
- System prompt establishes Yugo as a **creature**, not an assistant: replies are **short**, in the
  **third person** ("Yugo tilts its head and waves"), characterful, never verbose or list-like.
- The prompt names the available tools/behaviors and the safety rule that Yugo only moves in clear
  space. Mode switches may layer mode-specific personality (e.g. calmer pacing in meditation).
- The same persona governs both the voice replies and the `AgentReply.reply_text` of `/agent/say`.

### R5 — `POST /agent/say` text fallback
- For clients without audio. Body: `{text}`. Forwards the utterance + injected context (R3) through
  the model with the **same tool registry**, executes any tool in-process, and returns **`AgentReply`**
  (`reply_text` + the applied `behavior` `{type, name, params}`), matching the existing schema.
- May drive the model through the existing Realtime session (text turn) or a parallel
  fast-model/Realtime text path — implementer's choice, but tool execution and persona MUST be
  identical to the voice path (one brain, two front doors).
- Degradation: if OpenAI is unreachable, return **`502`** (`MindUnreachable` envelope) and leave the
  body in its safe local state; do not fabricate a reply or a behavior.

## Safety — degradation contract (critical)
The Realtime session makes Yugo *smart*; it is **never** what keeps Yugo *safe*. The reflex layer is
independent and authoritative.

- **Session/OpenAI down does not touch the reflex layer.** The `MotionController` deadman loop,
  velocity clamps, `/cmd_vel`, the nav nudges, and `POST /stop` keep running and stay observable on
  `GET /state` regardless of session state — exactly as they do offline today.
- **No tool call can bypass the clamps or the deadman.** `move`/`stop` go through `MotionController`;
  every commanded velocity is clamped (±0.6 m/s, ±1.2 rad/s) and expires at the deadman window. A
  hung or runaway session cannot produce sustained or out-of-envelope motion.
- **`POST /stop` is supreme.** It overrides any in-flight tool-driven motion and any trick suspend,
  and works with the session, the mind, and the link all down.
- **Session drop → safe.** On WS close the body does not freeze a held velocity; the deadman zeroes
  motion within its window. The reconnect is background and best-effort.
- **OpenAI unreachable → safe local command set.** A cloud blip never strands Yugo mid-demo: the body
  retains reflex/deadman + the safe local set (stand/sit/stop). `/agent/say` returns `502`; voice
  clients see a degraded-session status, not a stuck robot.
- **Robot link down during a tool call.** Robot-bound tools return a structured tool error to the
  model (not an exception to the client); reflex routes still respond `200` and publish once the link
  returns (hard constraint #2). The session does not crash on a transport hiccup.

## Dependencies
- **OpenAI Realtime SDK** + `OPENAI_API_KEY` (env; same key family as the mind's reasoning/vision).
  Body remains light — no torch, no local models (architecture-body constraint).
- **Body controllers:** `MotionController` (clamps, deadman, `set_velocity`/`stop`/`suspend`/`state`),
  `RobotController` (`fire`, `ACTIONS`, `NEEDS_BALANCE`, `action_catalog`), the WebRTC connection on
  `app.state.robot`, and the planned LED/VUI + mode switch.
- **Mind vision endpoint** (Phase 1) for context injection — best-effort, never on the safety path.
- **FastAPI app lifespan** (`yugo/main.py`) to own the session task; new `AgentRouter` for `/agent/say`.
- Existing schemas: `AgentReply`, `MotionState`, the `/mode` enum, the `SPORT_CMD` / `/tricks` table.

## Success criteria
- Audio in → Yugo replies in voice **and** triggers a body action via a tool call, in one session.
- Tool calls (trick / LED / mode / movement) execute **in-process** with **no mind round-trip**, using
  the same controller code paths and safety gating as the HTTP routes.
- Vision context from the mind is fed into the session and demonstrably influences replies/behavior.
- Mode switching works and changes the session's personality / available behavior.
- `POST /agent/say {text}` returns a correct `AgentReply` and fires the same behavior as voice.
- **Realtime/OpenAI down → body stays safe:** deadman, clamps, `/cmd_vel`, `/stop` keep running;
  `/agent/say` returns `502`; no held velocity, no stuck robot.
- Session survives a WS drop via background reconnect; `/healthz` (or session status) reflects it live.

## Open questions
- **Audio transport to/from clients.** How does Realtime audio reach the phone / test harness — does
  the body relay the audio streams over its own WS to the client, or is the model's audio bridged
  some other way? Codec/framing and who terminates the audio are unresolved (the dog has no mic/
  speaker; voice I/O is client-side per the hard constraints).
- **How the session is initiated.** Per-client connect, a single shared always-on session, or
  on-first-utterance? Who "owns" the mic, and what happens with multiple clients?
- **Barge-in / interruption.** How is user interruption while Yugo is speaking handled — rely on
  Realtime's server-side VAD + response cancellation, and how does that interact with an in-flight
  tool call (cancel the spoken response but let a fired trick finish, or `stop()` on barge-in)?
- **Mode enum reconciliation.** The roadmap modes (personal/friend/find/wand/meditation) and the
  openapi `/mode` enum (creature/ghost/hunt/scanner/music/meditation) differ — confirm the canonical
  set the `set_mode` tool exposes.
- **Vision injection cadence.** Push every vision result, or only on change / on demand from the model
  via a `look()` tool? Trade freshness against token cost and latency.
