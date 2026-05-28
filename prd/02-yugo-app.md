# PRD — Yugo Mobile App (the face of Yugo)

**Date:** 2026-05-29 · **Status:** draft for the mobile app design + frontend team · **Platform:** Expo (React Native) → iOS / Android / web

## What we're building
**Yugo** is a fun-first *reality-instrument companion* — a Unitree Go2 **Air** you drive, play with, and
hand a phone "wand." The phone is the face: **controller**, **wand**, and **voice** — its surface
**tinted by Yugo's mood**. The app is a **client of the body** — a local FastAPI hub on the dog's LAN
(default `http://<laptop>:8080`) that holds the robot link and runs the safety/reflex loop. The app
talks to it over the LAN: **REST** for commands and **polling** for state (incl. mood). The app owns
all audio (the dog has no mic/speaker). **The app is not a video viewer — there is no camera feed in it.**

## Priority (design + build top-to-bottom)
1. **Navigation & control** — drive Yugo. *(backend live today)*
2. **Bot mode** — the mode switcher and what each mode needs from the app.
3. **★ Wand / spell-casting** — the headline differentiator.
4. **Mood tint** — poll Yugo's mood, color the UI to match (no camera).
5. **Talk (voice)** — *intentionally last.*

> **This PRD focuses on the three core interactions (navigation & control, bot mode, wand) and the
> exact request payloads the mobile must produce.** See **"Required mobile output"** at the end for the
> consolidated contract.

---

## 1 · Navigation & control
How the app drives Yugo. All motion is **clamped and deadman-guarded server-side**: Yugo auto-stops
~**0.5 s** after the last command, so the app must **re-send held controls at a steady cadence**
(≈10–20 Hz for the joystick; ≈3–5 Hz / every 200–300 ms for held D-pad). Beyond-range values are
**clamped, not rejected**.

**Inputs the mobile sends:**
- **Joystick (continuous):** `POST /cmd_vel` with `{vx, vy, wz}` (see units below). Map stick → velocity;
  send while held; send `{0,0,0}` or `POST /stop` on release.
- **D-pad (discrete nudge):** `POST /up` · `POST /down` · `POST /left` · `POST /right` — **no body**.
  Each drives for the deadman window then auto-stops; repeat while held to keep moving.
- **STOP (always on screen):** `POST /stop` — **no body**. Highest-priority; one tap.
- **Actions / tricks (one tap each):** `POST /hello` · `/wiggle` · `/heart` · `/sit` · `/standup` ·
  `/standdown` · `/stretch` · `/dance` (full list from `GET /actions`), or `POST /trick/{name}`.

**Velocity units / convention** (clamped server-side):
- `vx` — forward (+) / back (−), m/s, **±0.6**
- `vy` — strafe left (+) / right (−), m/s, **±0.6**
- `wz` — yaw, CCW (+) / CW (−), rad/s, **±1.2**

**Responses (for UI feedback):**
- Motion routes → `MoveResult`: `{ok, action, vx, vy, wz, duration_s, connected}` — the echoed values
  are post-clamp; `connected` tells the app whether the dog is actually linked (else the command was
  accepted locally but didn't reach the dog).
- Action/trick routes → `TrickResult`: `{ok, move, api_id}` — **`ok` = published, not necessarily
  executed** (no execution ack; confirm via state, not this response).

**API status:** **all of section 1 is implemented now** — build and test against the live hub today.

---

## 2 · Bot mode
One active **mode** at a time, set by the app and reflected on the live state stream. A mode switch by
itself never moves the dog; it conditions how Yugo perceives/reacts and which inputs the app sends.

**Input the mobile sends:** `POST /mode` with `{ "mode": "<mode>" }`.
**Modes:** `creature` (default/idle) · `wand` · `personal` · `find` · `friend` · `meditation`.
**Response:** `{ok, mode}` — the app reflects the active mode from this response (mode is persisted
server-side; no WebSocket needed).

**What each mode additionally needs from the app:**

| Mode | App provides | Notes |
|---|---|---|
| `creature` | nothing | ambient idle |
| **`wand`** | spell casts (`/sensor/spell`) + continuous readings (`/sensor`) | see §3 |
| `personal` | nothing (vision auto) | Yugo mirrors the user's facial mood |
| `find` | a **target** (`{mode:"find", target:"Sarah"}` or via voice) | Yugo visually seeks the person |
| `friend` | spoken step directions (voice) | "2 steps forward, 3 left" |
| `meditation` | nothing (auto-guided) | breathing + soundscape |

**API status:** `POST /mode` is **planned**; build the switcher against this enum + payload now.

---

## 3 · ★ Wand specification (spell-casting)
The signature mechanic: a phone gesture → a robot trick, **deterministically** (same sweep ⇒ same
spell). The wand is the phone's **magnetometer**. Two distinct channels:

### 3a · Spell cast (discrete, the headline) — `POST /sensor/spell`
**Capture spec (mobile):**
- On **press-and-hold**, start sampling the **magnetometer** at a fixed rate — target **50 Hz**
  (`expo-sensors` `setUpdateInterval(20)`); optionally accelerometer too.
- Buffer each sample as `[t_ms, x, y, z]` — `t_ms` = ms since hold start; `x,y,z` magnetometer in **µT**.
- On **release**, stop sampling and `POST` the full trace. Typical hold ~0.5–2 s ⇒ ~25–100 samples.
- During the hold, give **immediate on-device feedback** (rising tone via local Web Audio + haptics +
  glowing sweep trail) — do **not** wait on the network for the live feel.

**Required request payload (mobile → body):**
```json
POST /sensor/spell
{
  "source": "phone-wand",
  "sample_hz": 50,
  "magnetometer": [[0, 12.3, -4.1, 40.2], [20, 12.6, -3.9, 40.5], "…"],
  "accel":        [[0, 0.10, 0.02, 9.79], "…"]
}
```
- `magnetometer` **required** (array of `[t_ms, x, y, z]`, µT); `accel` optional (m/s²); `sample_hz` the
  rate used.

**Response (what the app reflects):**
```json
{ "ok": true, "matched": { "bucket": 7, "move": "WiggleHips", "api_id": 1033 }, "fired": true }
```
- The body normalizes → features → hash → bucket → trick and fires it. The app shows the **cast flash**
  and reveals `matched.move`. Determinism is the point: the same trace always returns the same trick.

### 3b · Continuous wand (ambient) — `POST /sensor`
While the wand is live, **stream** readings so Yugo reacts (turns/flares toward fields). The
**live tone is local** (Web Audio) and does **not** depend on this call.

**Required request payload (mobile → body), ~10–30 Hz:**
```json
POST /sensor
{
  "source": "phone-wand",
  "magnetometer": { "x": 12.3, "y": -4.1, "z": 40.2 },
  "accel":        { "x": 0.1,  "y": 0.0,  "z": 9.8 },
  "light": 320,
  "gesture": "wave",
  "ts": 1716960000.123
}
```
- `gesture` optional (discrete, e.g. `"wave"`); `light` lux; `ts` epoch seconds (float).

**API status:** both `/sensor/spell` and `/sensor` are **planned** — these payloads are the contract to
design + build against (frontend captures, backend consumes).

---

## 4 · Mood & aura (poll → color)
Yugo has a **mood**; the app reflects it by **tinting its surface** to match — the "aura." **No camera
in the app** — mood is read from the body by polling.

- **The app:** polls the current mood (`GET /api/moods/current` → `{label, color, scalar}`) and sets the
  UI tint/pulse to `color` (calm = amber, nervous = cyan, excited = magenta, meditation = indigo, …).
- **The body (dependency):** a **mood loop** on the hub picks a mood on an interval, writes it to
  **SQLite** (`mood_events`), exposes it for polling, and makes **Yugo perform a gesture for that mood**
  (happy → dance, calm → sit, curious → wiggle). **Demo:** the source is a **random mood every N
  seconds**. **Future:** swap the source for a camera frame → vision API every 5–60 s that returns the
  mood — no app change, same poll contract.
- **Config:** the mood **update interval** and the recommended **poll cadence** live in **`robot.yaml`**
  (e.g. `mood: { update_seconds: 90, poll_seconds: 15 }`), read by the body — not hard-coded.

**API status:** the mood loop + `GET /api/moods/current` are **planned/demo** (mood persistence already
exists in SQLite). Build poll-and-tint against `{label, color}` now.

---

## Required mobile output (consolidated request contract)
Everything the app must produce, in one place. Base `http://<laptop>:8080`, no auth (LAN only).

| Interaction | Method · Route | Mobile sends (body) | Cadence | Status |
|---|---|---|---|---|
| Drive (joystick) | `POST /cmd_vel` | `{vx, vy, wz}` (m/s, m/s, rad/s; clamp ±0.6/±0.6/±1.2) | 10–20 Hz while held | **live** |
| Drive (D-pad) | `POST /up`·`/down`·`/left`·`/right` | *(none)* | repeat while held (~3–5 Hz) | **live** |
| Stop | `POST /stop` | *(none)* | on demand | **live** |
| Action | `POST /hello`·`/wiggle`·`/heart`·`/sit`·`/standup`·`/standdown`·`/stretch`·`/dance` | *(none)* | one-shot | **live** |
| Any trick | `POST /trick/{name}` | *(name in path; see `GET /tricks`)* | one-shot | **live** |
| Set mode | `POST /mode` | `{mode}` (+ `{target}` for find) | on switch | planned |
| Cast spell | `POST /sensor/spell` | `{source, sample_hz, magnetometer:[[t,x,y,z]], accel?}` | per cast (on release) | planned |
| Wand stream | `POST /sensor` | `{source, magnetometer{xyz}, accel{xyz}, light, gesture?, ts}` | 10–30 Hz | planned |
| Talk (text) | `POST /agent/say` | `{text}` | per utterance | planned |
| Poll mood | `GET /api/moods/current` | *(none)* | per `robot.yaml` (`~10–30 s`) | planned |

**Read (body → mobile), by polling:** `GET /api/moods/current` — current mood `{label, color}` (tints
the UI). `GET /actions` / `GET /tricks` — capability discovery. `GET /state` — motion/deadman.
`GET /healthz` — connection. (No camera feed, no WebSocket — the app is a controller/wand, not a viewer.)

---

## Secondary (lower priority)
- **Talk to Yugo (voice) — last.** Push-to-talk: Yugo hears you, replies in its character voice, may act.
  The voice brain runs on the body; the app needs the push-to-talk affordance, listening/thinking/
  speaking states, captions, and playback. Text fallback: `POST /agent/say {text}`.
- **Calm / meditation.** Breathing orb synced to Yugo's real motion + soundscape + soft prompts; rides
  on the voice session.



## Platform & tech
- **Expo (RN)** — one codebase, iOS/Android/web. Chosen for **`expo-sensors`** (native magnetometer +
  accel/gyro + light — the wand; iOS Safari blocks this), **`expo-av`** (voice + audio), **`expo-haptics`**.
- REST for commands + **polling** for mood/state (`GET /api/moods/current`, `GET /state`); connects over
  the LAN. No camera/video client, no WebSocket.
- **Audio (all app-side):** live wand tone = **local Web Audio** (sub-100 ms, never an API);
- STT via [tensorkit.net] service api
 
## Constraints that shape UX
- Dog has **no mic/speaker** → all sound on the phone.
- Live wand tone must be **local** (latency).
- App must be on the **dog's LAN**.
- Safety is server-side (clamps + deadman + supreme `/stop`) — but **STOP must always be one tap**, and
  held controls must be re-sent at cadence.

## Non-goals
- No perception/compute on the phone (client + sensor node only).
- No app-store release for v1 (Expo Go / dev build / web is fine for demos).
- Not a general robot console — Yugo-specific, experience-led.

## Success criteria
- A stranger, no instructions, can **drive Yugo**, **switch modes**, and **cast a spell** by sweeping the
  phone (and find that the same gesture repeats it); the UI **tints to Yugo's mood**; later, talk to it
  and be guided to relax. STOP always one tap.

## Open questions (design)
- Joystick vs D-pad as the primary control (ideally current implementation is ok)?
- Spell capture affordance + **spellbook** discoverability (reveal vs discover).
- Magnetometer sample rate / min-hold that feels good *and* hashes reliably (50 Hz is the starting point).
- `find` target entry — voice only, or a text field too?
- Avatar art direction — abstract mood-orb vs stylized creature (lean: orb).
