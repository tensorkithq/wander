# PRD Variant — Laptop-only (no GPU server)

**Date:** 2026-05-28 · **Status:** draft · **Relation:** a 2-tier collapse of the canonical 3-tier
PRD (`README.md`). Use this for Phase-1 / demo; the 3-tier is the scale-up path.

## Premise
Drop Tier 3 (the GPU server brain). **Everything runs on the laptop + the Yugo app.** The laptop
hosts *both* the robot I/O *and* the DimOS-library brain (agentic OpenAI + camera detection on MPS).
No cloud GPU, no Tailscale-for-brain, no laptop↔server link.

```
┌──────────────────────────┐
│ Yugo app (Expo)           │  porthole · controller · Deepgram STT ·
│                           │  ElevenLabs voice/SFX/music · phone-wand
└─────────────┬─────────────┘
              │ HTTP/WS (LAN; Tailscale only if remote)
              ▼
┌──────────────────────────────────────────┐
│ LAPTOP (M2 Pro) — bridge + brain, fused    │
│  • WebRTC LocalSTA to Yugo (dog)           │
│  • reflex/safety (deadman, clamps, STOP)   │
│  • DimOS-library FastAPI: agentic (OpenAI),│
│    camera detection (YOLO/MPS), modes      │
│  • serves the app's API contract           │
└──────────────────────┬─────────────────────┘
                        │ WebRTC
                        ▼
                    Yugo (Go2 Air)
```

## Why this variant
- **Fewest moving parts.** One operator, one machine, one network. Nothing to provision/pay hourly.
- **Demo-robust.** No internet-hosted brain = no venue-wifi single point of failure. The only cloud
  deps are the app's API calls (Deepgram STT, ElevenLabs, OpenAI) — and those degrade to scripted
  behavior if the network blips.
- **It's already Phase 1.** Matches "run the brain on the laptop; structure decoupled so it can move
  to the server later" (canonical recommendation). Choosing this now costs nothing later.

## Components (two)
### 1. Yugo app (Expo) — unchanged from `02-yugo-app.md`
Same client: porthole, controller, talk-to-Yugo, wand, dance, meditation. Same audio stack —
**Deepgram STT only** + **ElevenLabs voice/SFX/music** + **local Web Audio wand**, all app-side.
Talks only to the laptop.

### 2. Laptop (fused bridge + brain) — = `01-laptop-bridge-api.md` + the brain on-box
Everything in the ws1 bridge API, **plus** the DimOS-library brain in the same process/host:
- WebRTC `LocalSTA` to Yugo; reflex/safety; the full HTTP/WS contract the app codes against.
- **DimOS agentic mode (`OPENAI_API_KEY`)** in-process via the library pattern (not `dimos run` CLI)
  → `POST /agent/say` calls the agent directly.
- **Perception = external APIs** (OpenAI GPT-4o-vision + **Replicate**), **sampled ~1–3 fps** from
  the WebRTC camera. **No torch / no local YOLO / no MPS models on the laptop.** We compose our own
  light DimOS graph (connection + control) and **skip DimOS's bundled perception modules**, so the
  missing git-LFS model tarballs are a non-issue.
- Triggers ElevenLabs music/SFX (or relays the app's), drives gait/LED/dance/breathe.

## What you give up vs the 3-tier (and why it's fine for Phase 1)
- **Perception is sampled (~1–3 fps) via external APIs, not continuous local inference.** Fine for a
  creature that "notices" you after a beat; *not* for smooth, high-fps person-following. Trade: per-
  call cost + network dependency (you already depend on OpenAI/ElevenLabs/Deepgram, so not a new
  category of risk).
- **No "run while away from the dog"** → laptop must be on the dog's LAN (it always had to be anyway).

## Disk/RAM win (vs the earlier local-YOLO idea)
Because perception is external, **the laptop needs no torch / no vision models** — the install stays
genuinely light (robot connection + FastAPI + HTTP clients for OpenAI/Replicate/agent). This clears
the 16 GB / ~38 GB pressure that local YOLO would have caused.

## Hard constraints (unchanged)
- Air: **no LiDAR** (camera-first), **no onboard mic/speaker** (audio on app/laptop).
- WebRTC `LocalSTA` → laptop on the dog's LAN.
- Transport to the app = HTTP/WS (LAN; Tailscale only if the phone is remote).

## Decoupling rule (so 3-tier stays a move, not a rewrite)
Even fused on one box, **keep the brain a separable HTTP/WS client of the bridge** — same
`/agent/say`, `/ws/state`, `/sensor` contract. Then "go 3-tier" = relocate the brain process to the
A5000 and point it at the laptop's tailnet IP. No app changes, no contract changes.

## Success criteria (Phase-1 demo, laptop-only)
A person uses the Yugo app to: see Yugo's camera, **talk to Yugo** (Deepgram STT → OpenAI agent →
ElevenLabs voice), **sweep the phone-wand and hear hidden fields** (local synth), **wave to summon
music** (ElevenLabs) **and watch Yugo dance**, and be **guided into meditation** — all driven by the
laptop, on the dog's LAN, with no cloud GPU and the deadman keeping Yugo safe.

## When to graduate to 3-tier (`03-gpu-skills-server.md`)
Add the GPU server only when one capability outgrows the M2 Pro at interactive rates — most likely
**live VLM scene-mood**. Until then, this variant is the product.
