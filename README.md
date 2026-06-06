# Yugo 🐾

**A robot dog that turns invisible atmosphere into instinct.**

Yugo is a fun-first **reality-instrument companion** built on a Unitree **Go2 Air**. You talk to it,
play with it, and hand it your phone as a **wand** — it senses the room and answers back with motion,
light, and voice. Less "robot pet," more **spirit animal**.

> Built at a hackathon. Designed to feel alive.

---

## The idea

Some rooms feel safe. Some feel heavy. Some feel like they're watching you back.

Yugo gives that feeling a body. Sweep your phone like a wand and it casts a **spell** — the same
gesture always summons the same trick. Its mood shifts, and your phone's whole surface **tints to
match**. Drive it, play with it, or just let it settle beside you and breathe.

The phone is Yugo's face: **controller**, **wand**, and **voice**, all in one — colored by whatever
mood Yugo is in.

## What it does

- **🪄 Spell-casting (the headline).** Hold the phone, sweep it through the air, release. The
  magnetometer trace is hashed into a **deterministic** trick — the same sweep always casts the same
  spell. Immediate on-device tone, haptics, and a glowing trail make it feel like magic, not a remote.
- **🎨 Mood aura.** Yugo has a mood (charged, safe, curious, …). The app polls it and tints its entire
  UI to match — calm amber, nervous cyan, excited magenta. No screens of telemetry; just a feeling.
- **🎮 Direct control.** Joystick and D-pad drive, plus one-tap expressive actions — *hello, wiggle,
  heart, sit, stretch, dance.* Everything is clamped and **deadman-guarded**: let go and Yugo stops.
- **🧭 Modes.** One creature with many ways to relate: `creature` (idle), `wand`, `personal` (mirrors
  your mood), `find` (visually seeks a person), `friend` (spoken step-by-step nav), and `meditation`.
- **🗣️ Voice & calm.** Talk to Yugo and it answers in character; a guided breathing mode syncs its
  motion and light to help you slow down.

## How it's built — body + mind

Yugo's intelligence is split so the robot stays **fast, safe, and lightweight** while the heavy
thinking happens in the cloud.

- **🤖 Body** — a lightweight **FastAPI** service on the local network. It holds the WebRTC link to the
  dog, runs control and the reflex/deadman safety loop, and exposes the API the app codes against.
  Deliberately **torch-free** so it boots fast and runs anywhere.
- **☁️ Mind** — cloud intelligence the body delegates to: reasoning, perception, and voice. The body
  carries text and commands, not heavy models — keeping the on-robot layer simple and responsive.

The phone app is the third piece: an **Expo / React Native** client that talks to the body over the
LAN. It owns all audio (the dog has no mic or speaker) and reads mood by polling. Safety always lives
server-side — and **STOP is always one tap away.**

## Tech stack

| Layer | Stack |
|---|---|
| **Body** (robot I/O + control) | Python · FastAPI · WebRTC · SQLAlchemy + Alembic · SQLite · built on [DimOS](https://pypi.org/project/dimos/) |
| **App** (controller / wand / voice) | Expo · React Native · NativeWind · `expo-sensors` (magnetometer) |
| **Mind** (cloud intelligence) | LLM reasoning · vision perception · speech-to-text + text-to-speech |
| **Robot** | Unitree Go2 Air |

## Quickstart

The "body" is a FastAPI app that connects to the dog over WebRTC and serves the API the app uses.

```bash
# install deps (uses uv)
uv sync

# apply database migrations
uv run alembic upgrade head

# run the body against your robot (set ROBOT_IP to your dog's address on the LAN)
ROBOT_IP=<your-dog-ip> uv run uvicorn yugo.main:app --host 0.0.0.0 --port 8080

# or run offline — no robot needed; the reflex/safety layer stays live
YUGO_NO_ROBOT=1 uv run uvicorn yugo.main:app --port 8080
```

Try it:

```bash
curl -X POST localhost:8080/hello     # an expressive action
curl localhost:8080/state             # live motion / deadman state
curl localhost:8080/actions           # what Yugo can do
```

Run the tests (no robot required — they boot the real app and exercise it over HTTP):

```bash
uv run pytest
```

## Repo layout

| Path | What |
|---|---|
| `yugo/` | The **body** — FastAPI service: robot I/O, control, deadman safety, persistence. See `yugo/README.md`. |
| `app/` | The **Yugo app** — Expo / React Native controller, wand, and voice. |
| `prd/` | Product specs: architecture (body / mind), the API surface, and per-feature PRDs. |
| `docs/` | Design docs and the demo reel concept. |
| `scripts/`, `utils/` | Test harness and standalone robot utilities. |

## Roadmap

Yugo's demo arc: **see → talk → cast spells → find → relax.**

- [x] **Foundation** — safe control, reflex/deadman, expressive actions, live state, persistence, tests.
- [ ] **Spells** — gesture → deterministic trick (the headline wand mechanic).
- [ ] **See & sense** — live camera feed and a streaming "aura" state.
- [ ] **Vision modes** — `personal` (emotional mirror) and `find` (visual person-seeking).
- [ ] **Talk** — a voice brain for conversation, spoken navigation, and guided calm.

---

Built on [DimOS](https://pypi.org/project/dimos/) and the Unitree Go2 Air. A hackathon project by
[TensorKit](https://tensorkit.net).
