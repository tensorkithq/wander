# Architecture — The Mind (cloud intelligence)

**Date:** 2026-05-29 · **Status:** canonical · **Pairs with:** `architecture-body.md`

## One line
The **mind** is all of Yugo's intelligence, delegated by the body over the network. The body has the
senses and limbs; the mind decides, perceives, and speaks. The mind holds **no robot connection** and
is **not on the dog's LAN** — it's a set of cloud services the body calls.

## Components
### 1. Reasoning — the agent (OpenAI)
- Turns an utterance + context (recent detections, mood, state) → **behavior intent** (move / trick /
  LED / mode) **+ a reply line** for Yugo to speak.
- Invoked by the body's `/agent/say`. Use a **fast model** (e.g., gpt-4o-mini) and **stream** so the
  first words come back quickly. Personality: short, third-person Yugo lines.
- May be the DimOS agentic loop (library) or a direct OpenAI call — either way it runs cloud-side,
  keyed by `OPENAI_API_KEY`. (DimOS's bundled perception modules are NOT used here — see §2.)

### 2. Perception — pluggable, latency-tiered
The body samples camera frames (~1–3 fps) and sends them up; the mind returns detections / scene /
mood. **One interface, swappable backends routed by latency budget:**

| Tier | Backend | Latency | Use |
|---|---|---|---|
| Occasional / scene-mood | **OpenAI GPT-4o-vision** | ~1–3 s | "what/who is here," vibe |
| On-demand boxes | **Replicate** (`zsxkib/yolo-world`) / **fal** (`fal-ai/sam-3`) | ~0.5–1 s | structured detections, person centroid |
| Instant / continuous | **self-hosted warm CUDA endpoint** ("our own Replicate") | ~50–150 ms | responsive tracking (scale-up) |

Replaces DimOS's bundled **YOLO-E** (detection/tracking) + **CLIP** (embeddings) — which can't load
from the wheel anyway. Start with GPT-4o-vision; add a hosted detector when you need coordinates.

### 3. Voice — generation, app-side audio
- **Deepgram = STT** (app captures mic → Deepgram → text → body `/agent/say`).
- **ElevenLabs = Yugo's voice (TTS) + Sound Effects + Music** (app plays it; mood-driven music may be
  generated mind-side and streamed). Live wand sonification stays **local Web Audio in the app**.
- Audio bytes never traverse the body; the body carries text.

### 4. Memory (Phase 2) — LanceDB + embedder
- **LanceDB** (embedded, in-process, local to the mind's box) as the vector store; a **local embedder**
  (CLIP/SigLIP on the cloud GPU) produces vectors. Lowest-latency retrieval, co-located with the
  brain. Not demo-critical; add when "Yugo remembers / find where I saw X" is wanted.

## How the body reaches the mind
HTTP/WS over Tailscale (or internet). Body POSTs {utterance, context} / {frame} / {mood cue}; mind
returns {intent, reply} / {detections, scene} / {audio or params}. The mind is stateless per request
(except memory). Backends are swappable without the body changing.

## Deployment
- **Cloud GPU (RunPod A5000)** hosts the warm perception endpoint + (Phase 2) the embedder + LanceDB.
- **Managed APIs:** OpenAI (reason + vision), Deepgram (STT), ElevenLabs (voice/SFX/music).
- Keep the GPU **warm during sessions** (no cold starts on the latency path); stop it otherwise.

## Latency levers (ranked)
1. **Region** — the dominant factor. From Asia/China, US-hosted OpenAI/Deepgram/ElevenLabs add
   200–400 ms and may be GFW-blocked/throttled. Put the GPU in an Asia region, prefer Asia-reachable
   providers, and self-host the latency-critical AI piece there if access bites.
2. **Warm models** — never serverless the latency-critical path.
3. **Stream voice** end-to-end (Deepgram interim → LLM token-stream → ElevenLabs websocket TTS).
4. **Co-locate** reason + perception + memory + embedder on one box; LanceDB embedded, not remote.

## Degradation contract
If the mind is unreachable, the body falls back to reflex + a safe local command set. The mind makes
Yugo *smart*; it is never what keeps Yugo *safe*.
