# PRD — Workstream 2: Yugo App (React Native / Expo)

**Date:** 2026-05-28 · **Status:** draft · **Client of:** `01-laptop-bridge-api.md`

## Objective
Be **the face of Yugo** — the mobile companion you carry, the **porthole** into what Yugo senses,
the **controller**, the **voice** you talk to it through, and the **wand** (the phone's own sensors
become a detector for invisible fields). One Expo codebase → iOS / Android / web.

## Users
- **Operator / demo driver** — full control, mode switching, teleop.
- **Audience member** — handed the phone for the wand + talk-to-Yugo moments; must be usable cold,
  one-handed, in motion.

## Why Expo (not a PWA)
`expo-sensors` gives **full native magnetometer + accel/gyro + light** — the thing iOS Safari blocks.
That native magnetometer is what makes the phone a real **wand**. `expo-av` plays Yugo's voice +
generative audio. `expo-haptics` for tactile feedback.

---

## Style & design

**Vibe:** a *living artifact* — cyber-organic, dark, glowing; part talisman, part scanner, part pet.
Inherits the original wand spec's "brass + black resin + glow" feel, translated to screen.

- **Mood-reactive surface.** The whole UI tints and pulses with **Yugo's current mood** (read from
  `/ws/state`): calm = warm amber, slow pulse; nervous = cool cyan, fast jitter; excited = bright
  magenta, energetic; meditation = deep indigo, slow breath. The app *feels* what Yugo feels.
- **Yugo has a face.** A central **avatar/orb** (not a literal dog render) that breathes, reacts,
  and changes color with mood + the dog's real LED — the emotional anchor on every screen.
- **Tactile + legible.** Large touch targets, generous spacing, minimal text, iconographic controls
  (used one-handed, in motion, by strangers). Haptics on key actions (wand spikes, mode changes,
  Yugo speaking).
- **Dark, atmospheric, motion-rich** — glow, particles, and the "aura" field as ambient visuals.
  Avoid generic app-chrome; this should feel like an instrument, not a settings panel.
- **Accessibility/demo:** high contrast, big STOP always visible, captions for Yugo's speech.

---

## Features (objectives)

### Porthole (observe)
- **Live camera** (MJPEG from `/video_feed/color_image`).
- **Aura overlay** — Yugo's sensed field rendered from `/ws/state`: detections/person-count, wand
  magnetometer intensity, mood. The "Scanner / room aura" surface.
- **Mood + state readout** — the avatar + a minimal vitals strip (battery, mode).

### Controller (drive)
- **Virtual joystick** → `POST /cmd_vel`; **big STOP** → `POST /stop` (deadman makes it safe).
- **Trick buttons** — Hello / WiggleHips / Stretch / FingerHeart → `POST /trick`.
- **Mode switcher** — Creature / Ghost / Hunt / Scanner / Music / Meditation → `POST /mode`.

### Talk to Yugo (voice)
- **Push-to-talk** → capture mic → **Deepgram STT** → text → bridge/agent.
- **Yugo replies** — text → **Deepgram Aura TTS** → playback (`expo-av`) + on-screen **caption**.
- Signature lines surfaced as the avatar "speaks." Example flow: *"Yugo, you're safe"* → Yugo calms,
  *"Yugo feels calm now."*

### Wand mode (the phone as a sixth sense) — the differentiator
- Read **magnetometer + accel/gyro + light** (`expo-sensors`).
- **Sonify live**: field intensity → rising/eerie synth (Web Audio / `expo-av`), with **haptics**.
- **POST `/sensor`** to the bridge so **Yugo reacts** (turns/flares toward the field).
- **Wave gesture** (accel pattern) → trigger / change **music** (`POST /audio/play` + `/dance`).

### Yugo dances
- When music plays, show it and let Yugo move: app sends `POST /dance {bpm, style}`; the bridge
  choreographs Yugo. App visualizes the beat + Yugo's mood rising.

### Yugo meditation
- Guided **breathing visual** (expanding/contracting orb) synced to Yugo's real "breathing" motion
  (`POST /breathe`), calming soundscape, soft spoken prompts (*"Breathe with Yugo… in… out"*),
  indigo slow-pulse theme.

## Tech
- Expo (React Native) — iOS / Android / web. `expo-sensors`, `expo-av`, `expo-haptics`.
- WebSocket client for `/ws/state`; REST for commands. Connects to the laptop bridge over LAN /
  Tailscale. Deepgram via app-side SDK or through the bridge (see ws1 open question).

## Non-goals
- No perception/compute on the phone (it's a client + a sensor node).
- No app-store release for v1 (Expo Go / dev build / web is fine for demos).
- Not a general robot console — it's Yugo-specific and experience-led.

## Success criteria
- A stranger can pick up the phone and, with no instructions: see Yugo's view, **talk to it**,
  **sweep for a hidden magnet and hear it**, **wave to summon music and watch Yugo dance**, and be
  **guided into a calm meditation** — the whole demo arc, from the app.
- UI visibly **feels** Yugo's mood; STOP is always one tap away.

## Open questions
- Deepgram from app vs via bridge (mirror of ws1 open question).
- Avatar art direction — abstract orb vs stylized creature. (Lean: abstract, mood-driven orb; faster
  to build, less uncanny.)
