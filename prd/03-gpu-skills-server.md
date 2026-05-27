# PRD — Workstream 3: GPU Skills FastAPI (optional / additive)

**Date:** 2026-05-28 · **Status:** draft (deferred until needed) · **Serves:** the laptop bridge (ws1)

## Objective
A **second FastAPI**, running on the CUDA server (RunPod A5000), that exposes **heavier "skills"**
the laptop bridge can call when the **M2 Pro isn't enough to do it live** — and **stream results
back down** to the laptop FastAPI. It is an **augmentation**, not a dependency: Phase 1 runs entirely
without it (laptop/MPS).

## When we actually need it
Reach for this only when a capability is too heavy for the laptop to run at interactive rates:
- Real-time **VLM scene understanding** richer than local YOLO (what's happening, not just boxes).
- Larger / faster **object detection** at full frame rate.
- Heavier **mood reasoning** / the full agentic loop with memory.
- **Generative music** models (if we go beyond procedural synth).

Until one of those bites, **don't build this** (YAGNI — design §11).

## Architecture / relationship
- The brain runs its **own DimOS graph** + this FastAPI. The **laptop bridge is the client**; this
  is the **skills server**. Link = HTTP/WS over **Tailscale** (userspace mode is fine — TCP). **No
  DDS.**
- Laptop **pushes** frames + sensor scalars **up**; brain **streams** mood/detections/behavior
  **down** so the laptop acts locally with low latency. The tight robot loop stays on the laptop.

## Skills (objectives → endpoints, build as needed)
- `POST /perceive {frame}` → rich scene: detections + VLM description + scene "mood" cues.
- `GET /ws/perceive` → continuous perception stream from pushed frames (preferred for live use).
- `POST /mood {signals}` / `GET /ws/mood` → fused signals (vision + wand + audio) → mood state +
  behavior intent the laptop maps to gait/LED/audio.
- `POST /converse {text, context}` → Yugo's spoken reply text (agentic loop; pairs with Deepgram
  TTS on the laptop/app side).
- `POST /music {style, seed}` / `GET /ws/music` → **ElevenLabs Music** generation (mood-driven),
  streamed down to the app/laptop speaker. (Yugo's voice + SFX are ElevenLabs too, but app-side;
  the server only generates the mood-tied music/ambient.)

## Hard rules (from the brain runbook + setup report)
- **Never change torch** (pinned `2.4.1+cu124`); avoid `cuda`/`all` extras (xformers).
- Installs land on the **ephemeral overlay** → keep a **`/workspace/bootstrap.sh`** to re-install
  fast on each fresh container; repo + caches persist on `/workspace`.
- **Watch the 50 GB volume** (≈40 GB git-LFS + caches already) — models may have no room; prune LFS.

## Non-goals
- **Never holds the WebRTC link** to Yugo (laptop-only — `LocalSTA` needs the dog's LAN).
- Not on the critical path: the laptop must **degrade gracefully** to local/MPS skills if the GPU
  server is absent or unreachable.

## Success criteria
- Laptop can offload a heavy skill and receive streamed results over Tailscale at usable latency,
  and **falls back cleanly** to local behavior when the server is down.

## Open questions
- Which single skill justifies standing this up first? (Likely **live VLM scene-mood**, since
  it's the one thing the M2 Pro struggles to do at frame rate while also holding the robot link.)
- Container TUN flags vs full VM — only matters if we ever *do* want DDS; HTTP/WS sidesteps it.
