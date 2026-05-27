# Yugo — Product Requirements (overview)

**Date:** 2026-05-28 · **Status:** PRD draft · **Repo:** `tensorkithq/wander`
**Design reference:** `../docs/plans/2026-05-27-reality-instrument-design.md`

## What Yugo is
A **fun-first reality-instrument companion**: a Unitree Go2 **Air** named **Yugo**, driven by DimOS,
that turns invisible forces in a space into sound, light, motion, and personality — and that you can
**talk to, play with, and hand a "wand" (the phone) to**. Not useful-first; an instrument / toy /
creature / performance.

## Workstreams (this PRD set)
| # | Workstream | Doc | Role |
|---|---|---|---|
| 1 | **Laptop FastAPI bridge** | `01-laptop-bridge-api.md` | The always-on local hub. Owns the WebRTC link to Yugo; exposes the HTTP/WS contract everything else codes against. |
| 2 | **Yugo React Native app** | `02-yugo-app.md` | The mobile companion + porthole + voice + phone-as-wand. The face of Yugo. |
| 3 | **GPU skills FastAPI** (optional) | `03-gpu-skills-server.md` | A second FastAPI on the CUDA server for heavy skills, streamed down to the laptop bridge when the M2 Pro isn't enough. |

The **laptop FastAPI is the integration backbone.** The app is its client; the GPU server augments
it. Phase 1 runs with workstreams 1 + 2 only; workstream 3 is additive.

## Architecture
```
  Go2 Air "Yugo" ──WebRTC LocalSTA (LAN)──┐
                                          ▼
   ┌─────────────────────────────────┐  HTTP/WS   ┌──────────────────────────┐
   │ LAPTOP FastAPI bridge (workstream 1)│◀───────▶│ GPU skills FastAPI (ws 3) │
   │ camera · teleop · tricks · LED ·  │ Tailscale │ heavy VLM · mood · music  │
   │ state WS · voice I/O · wand ingest│           │ (optional, streamed down) │
   └─────────────────────────────────┘            └──────────────────────────┘
                     ▲ HTTP/WS (LAN / Tailscale)
                     │
            ┌──────────────────┐
            │ YUGO app (ws 2)   │ porthole · controller · voice · phone-wand
            │ Expo RN (iOS/And/web)
            └──────────────────┘
```

## Shared constraints (apply to all workstreams)
- **Air has no LiDAR** → camera-first perception (YOLO), no mapping/nav stack.
- **Air has no onboard mic or speaker** → all voice I/O lives on the phone/laptop. Yugo "speaks
  through Yugo" (the app/laptop speaker).
- **WebRTC `LocalSTA` requires the laptop on the dog's LAN** → only the laptop holds the robot link.
- **Transport = HTTP/WebSocket over Tailscale** (DDS dropped). Tailscale = secure net + SSH only.
- **Voice = Deepgram** (streaming STT + Aura TTS) for low latency; DimOS also ships whisper/openai
  TTS nodes as fallback.
- **Brain LLM + Deepgram are cloud APIs** → low local load; needs network + API keys.

## Naming
- Robot dog = **Yugo**. App = **Yugo**. Repo = `tensorkithq/wander`.
- Yugo speaks short, characterful, third-person lines: *"Yugo is your friend." "Yugo feels calm
  now." "Yugo wants to dance!"*

## Success (Phase 1 / demo)
A person can **hold the phone, talk to Yugo, sweep for hidden invisible fields and hear them,
trigger music and watch Yugo dance, and be guided into a calm meditation** — all from the app, with
the laptop bridge driving the dog safely. Demo arc: *meet Yugo → talk it calm → wand summons music →
Yugo dances → Yugo guides you to relax.*
