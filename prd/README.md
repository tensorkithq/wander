# Yugo — PRD index & roadmap

Yugo: a fun-first reality-instrument companion — a Unitree Go2 **Air** you talk to, play with, and
hand a phone "wand" to. **Body** (local FastAPI, `yugo/`) holds the robot + reflexes + tools; **Mind**
(cloud) supplies intelligence the body delegates to. See `architecture-body.md` / `architecture-mind.md`.

Demo arc: **see → talk → cast spells → find → relax.**

## Milestone status

### ✅ Current milestone — COMPLETE (2026-05-29)
The body delivers **see → talk → spell → find**:
- **M0 Foundation** — safe control, reflex/deadman, expressive actions, `/state`, owners/moods, tests.
- **Spell** — `POST /sensor/spell` deterministic gesture→trick (`module-wand-hash.md`).
- **See & sense** — `/feed` WebRTC camera relay + `/ws/state` aura (`module-camera-feed.md`,
  `module-state-stream.md`).
- **Vision modes** — mode state machine (`POST /mode`) + `personal` + `find`
  (`module-mode-state-machine.md`, `module-personal-mode.md`, `module-find-mode.md`).
- **Talk (Realtime voice)** — the keystone (`module-realtime-session.md`): in-process **tool registry**
  (`do_action`/`do_trick`/`set_mode`/`move`/`stop`/`nav_steps`), **`POST /agent/say`** text brain
  (OpenAI function-calling, degrades to 502), and **`WS /agent/realtime`** voice session bridge.
- **Friend** (`module-friend-mode.md`) — autonomous vision-servo approach + conversational
  **step-nav** (`nav_steps` → clamped/deadman `/cmd_vel`; Friend-aware Realtime prompt).

> **Needs live validation** (offline tests cover the contracts/degradation/mappings only): the
> `/agent/say` 200-path + `/agent/realtime` audio session against a real `OPENAI_API_KEY` + the app
> for audio, and the end-to-end Friend voice loop.

### ⏭ Next milestone — "Relax" + polish + cleanup
- **Calm / meditation** — `POST /breathe` (slow body-height oscillation) + voice-guided relaxation
  (`module-breathe-led.md`); needs `/led`.
- **`/led`** — front-lamp VUI color/effect (also unblocks personal-mode mood color).
- **Audio cues** — `/say` (caption broadcast on `/ws/state`) + `/audio/play` · `/audio/stop`
  (ElevenLabs mind-gen music/SFX; playback stays app-side).
- **Cleanup** — retire the deprecated `yugo/bridge/` (WebBridge :5555) now `/feed` supersedes its MJPEG.
- **Live-validate** the Realtime voice + Friend voice paths on the dog with a real key.

## Index
- **Architecture:** `architecture-body.md` (local hub), `architecture-mind.md` (cloud intelligence).
- **App:** `02-yugo-app.md` (Expo companion — porthole, controller, voice, phone-wand).
- **Modules:** `module-realtime-session.md`, `module-friend-mode.md`, `module-find-mode.md`,
  `module-personal-mode.md`, `module-mode-state-machine.md`, `module-camera-feed.md`,
  `module-state-stream.md`, `module-wand-hash.md`, `module-breathe-led.md`.
- **Deferred / scale-up:** `03-gpu-skills-server.md` (self-hosted "our own Replicate" inference,
  instant-feedback tier), `variant-laptop-only.md`.
- **Surface contract:** `../yugo/openapi.yaml` (implemented vs planned per route).
