# Yugo — "Spirit Animal" Demo Reel (draft)

> **Status:** Draft / parked. Robot functionality (the dimos teleop bridge in `fastapi/web_bridge.py`) is the execution layer; revert to this doc when it's back up to produce the run sheet.
> **Working concept codename:** Moodhound. **Public name:** Yugo.

---

## ONE-LINE PITCH

Yugo is a robot dog that turns invisible atmosphere into instinct.

---

## v0 OPERATING MODEL (how the demo actually runs)

This is the reality layer the reel sits on top of. Everything the viewer reads as "sensing" is, in v0, **interpreted intent — not hardware sensors.**

- **No physical sensors for mood in v0.** The Go2 Air has no EMF / signal / air-quality / thermal sensors, and the perception roadmap (radio scan, thermal vision) is v1+.
- **Mood is triggered via the mobile app → API.** The operator sends a command (or natural-language cue) from the mobile app; the API **interprets** it into a mood state (`charged` / `safe` / `curious`) and drives the corresponding behavior on the robot. This is a Wizard-of-Oz layer: the *intelligence* is real software interpretation, the *stimulus* is human-supplied.
- **Behavior execution is real.** Movement (pacing, cautious step-back, settling, approaching) runs through the existing teleop bridge (`cmd_vel`: vx/vy/wz, clamped at 0.6 m/s, deadman auto-stop). The slow, deliberate register the concept wants is exactly what the clamps enforce.
- **Owner identity is part of the robot's memory configuration.** Yugo knows its owner via a **voice signature OR image signature** stored in the system's memory config. The `curious` / `trust` beat ("when I enter, it chooses whether to come closer") is grounded in this: the robot recognizes the owner and changes behavior toward a known identity, rather than reacting to any person. This is the seed of the "memory" capability promised in the v1 CTA.

**Editing implication:** the reel's own rule — `stimulus → behavior → feeling` — is exactly how app-triggered moods read as genuine sensing on screen. The viewer infers the cause. Do not claim real environmental sensing on camera in v0.

### v0 → v1 capability map

| Reel beat | v0 (now) | v1 (roadmap) |
|---|---|---|
| Senses "the room" | App command → API interprets mood | Real sensors: radio scan, thermal |
| Recognizes owner | Voice/image signature in memory config | Richer multi-person memory |
| Mood behaviors | Teleop-driven, app-triggered | Autonomous from sensor fusion |
| LED "breathing" | TBD — verify Air face-LED / sport API exposes it; else stage lighting | Programmatic LED moods |

---

## FORMAT

- **Format:** vertical short
- **Length:** 50–65 seconds
- **Tone:** mystical, intimate, slightly eerie, warm by end
- **Core idea:** a robot dog that senses invisible moods and behaves like a spirit animal

---

## STORY

### 0–5s — The Room Has a Feeling
**Visual:** Dark room. Stillness. Desk LEDs. Laptop asleep. Window reflection. Robot dog sits motionless in shadow.
**Text on screen:** Some rooms have moods.
**Voiceover:** Some rooms feel safe. / Some feel heavy. / Some feel like they're watching you back.
**Director notes:** Start quiet. No tech yet. Room as character. Slow camera, like entering a sacred space. Low ambient tone, barely audible.
**v0 note:** robot is parked/still — no command sent yet.

### 5–12s — The Spirit Animal Wakes
**Visual:** LED slowly pulses like breath. Head rises. Small servo movement. Not "booting" — waking.
**Text on screen:** So I built mine a body.
**Voiceover:** I didn't want a robot pet. / I wanted a spirit animal.
**Director notes:** No startup beeps. Soft mechanical sound, breath-like synth, low hum. Keep robot partly in silhouette — reveal fragments: paw, eye light, neck.
**v0 note:** operator sends "wake" cue from app; behavior = small head/neck servo move. Verify LED breathing is controllable; if not, stage with practical lighting.

### 12–22s — It Reads What I Can't See
**Visual:** Robot walks near laptop, router, speaker, outlet. Pauses. Head tilts. LEDs flicker. One cautious step back.
**Text on screen:** Invisible signals → instinct
**Voiceover:** It reads things I usually ignore. / Air. Sound. Light. Motion. Signal noise. / Then it turns them into instinct.
**Director notes:** Functionality appears but stays poetic. No sensor names. Cause and reaction. Cut between object and behavior. Dog senses before viewer understands.
**v0 note:** operator triggers `charged` interpretation as robot nears the router; behavior = pause, head tilt, step back (teleop). The "reading" is app→API interpretation, not a sensor.

### 22–32s — Uneasy Mood (Charged)
**Visual:** Near electronics. Restless. Small pacing. Flickering light. Low whine. Quick head turns.
**Text on screen:** Charged.
**Voiceover:** When the room feels charged, it gets uneasy.
**Director notes:** Tighter cuts. Slight camera shake. Subtle glitch sound. Faster LED flicker. Colder light. Tension beat.
**v0 note:** `charged` state held; behavior = small pacing loop + head turns via cmd_vel.

### 32–42s — Safe Mood
**Visual:** Quieter corner near plant/window/soft lamp. Robot slows. Sits. LEDs breathe gently. Looks up at you.
**Text on screen:** Safe.
**Voiceover:** When the space softens, it settles.
**Director notes:** Pace drops. Warmer light. Let one shot breathe 3–4s. Viewer feels nervous-system shift from tension to calm.
**v0 note:** `safe` state; behavior = slow to stop, settle/sit (verify sit posture is exposed via sport API or stage via Unitree app).

### 42–53s — Bond (Curious / Trust)
**Visual:** You enter frame. Robot turns toward you, approaches slowly, stops beside your foot/hand. No command. It chooses proximity.
**Text on screen:** Presence → trust
**Voiceover:** It doesn't obey me. / It follows the feeling. / And somehow, that feels more alive.
**Director notes:** No remote/controller visible. No "sit" command. Interaction feels chosen. Face partly obscured / softly lit. Focus on dog choosing closeness.
**v0 note:** this beat is grounded in **owner identity** — Yugo recognizes the owner by voice/image signature in its memory config and approaches a *known* person. Operator triggers `curious` on owner entry; behavior = turn + slow approach.

### 53–62s — Reveal
**Visual:** Beauty shot. Robot beside you, facing dark room/window. LED breathing. Room reflected in its body.
**Text on screen:** Yugo v0 — A robot dog for invisible moods.
**Voiceover:** This is Yugo. / My robot spirit animal for sensing what the room won't say out loud.
**Director notes:** End on myth, not specs. Let final frame linger. Faint heartbeat/breathing sound. Logo/name small.

---

## CTA OPTIONS

- **Soft:** Should I teach it more moods?
- **Mystic:** What mood should it learn next?
- **Builder:** v1 gets radio scan, thermal vision, and memory.
- **Best:** What should its next instinct be?

---

## MOOD STATES (use only 3 in first video)

1. **Charged** — near electronics / signal noise
2. **Safe** — calm corner / warm light
3. **Curious** — when owner enters

Do not overload first reel. Make people feel the concept before explaining the system.

---

## SHOT LIST

1. Dark room wide shot
2. Robot dog still in shadow
3. LED "breath" close-up
4. Paw movement close-up
5. Head rising
6. Laptop/router close-up
7. Robot pausing near electronics
8. LED flicker / uneasy behavior
9. Robot backing away
10. Warm corner / plant / window
11. Robot settling
12. Owner's hand entering frame
13. Robot turning toward owner
14. Robot approaching
15. Final silhouette: owner + Yugo facing room

---

## AUDIO DIRECTION

- **Opening:** low room tone, distant hum
- **Wake:** soft synthetic breath
- **Charged:** glitch texture, tiny mechanical whine
- **Safe:** warm pad, slower pulse
- **Bond:** near silence + soft heartbeat
- **End:** one clean synth note

Avoid energetic tech music. Sound design like the room is alive.

---

## COLOR DIRECTION

- **Charged:** blue/green/cold white
- **Safe:** amber/warm white
- **Curious:** soft mixed light
- **Final:** dark with one warm edge light

---

## EDITING RULE

Cut like emotion, not logic. Show: **stimulus → behavior → feeling.**

- router → flicker/head tilt → "Charged"
- plant/window → slow breathing → "Safe"
- owner enters → approach → "Trust"

---

## SHORTER VOICEOVER VERSION

Some rooms feel safe. / Some feel heavy. / Some feel like they're watching you back.
I didn't want a robot pet. / I wanted a spirit animal. / So I built Yugo.
It reads air, sound, light, motion, and signal noise. / Then it turns them into instinct.
When the room feels charged, it gets uneasy. / When the space softens, it settles. / When I enter, it chooses whether to come closer.
It doesn't obey me. / It follows the feeling.
Yugo v0. / A robot dog for invisible moods.

---

## OPEN ITEMS BEFORE SHOOT (revisit when bridge is back up)

- [ ] Confirm Air face-LED breathing is programmatically controllable; else stage with practical lighting.
- [ ] Confirm sit/settle posture is exposed (sport API) or plan to stage via Unitree app.
- [ ] Build the app→API mood-trigger path (`charged` / `safe` / `curious` → teleop behavior macros).
- [ ] Wire owner identity (voice OR image signature) into memory config; verify `curious` beat keys off owner recognition.
- [ ] Produce per-shot teleop run sheet (direction, duration, off-camera operator action) from the shot list above.
