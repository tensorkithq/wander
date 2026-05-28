# PRD — Body Module: Friend Mode (conversational step-nav)

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `module-realtime-session.md` (body-hosted Realtime), `module-find-mode.md` / `module-personal-mode.md` (shared mode machinery), `../yugo/openapi.yaml` (`/cmd_vel`, `/mode`, `/stop`)

## Objective
Friend mode is **conversational navigation to a companion**. Yugo's body-hosted Realtime session
takes on a "looking for [person]" persona, asks the user where the companion is, and the user
answers with **step-based directions** ("2 steps forward, 3 steps left"). The Realtime session
parses each instruction into nav tool calls; the body translates those steps into clamped,
deadman-guarded `/cmd_vel` sequences, executes the nudge, then **waits for the next instruction**.
The mind's vision wrapper optionally confirms the target person is in view.

This is the **deliberate low-tech navigation approach**: UWB/GPS need a dev build and aren't precise
enough indoors, so spoken step-based directions are the substitute. The human is the localizer; the
body is the actuator.

Authoritative motion contract: `../yugo/openapi.yaml` — `/cmd_vel` (clamps ±0.6 m/s linear, ±1.2
rad/s yaw; deadman `command_timeout` default 0.5 s), `/stop`, `/mode`.

## Scope
- A `friend` branch of the **shared mode state machine** (same machinery as Find and Personal;
  selected via `POST /mode`). On entry the body configures the Realtime session with the Friend
  prompt; on exit it tears that down and zeroes motion.
- **Realtime prompt config:** inject "You are looking for [person]. Ask the user for directions,
  one step at a time." plus the step-nav tool schema. The target name is a parameter of mode entry.
- **Step-nav tool calls:** the Realtime session calls an in-process tool (e.g. `nav_steps`) with a
  parsed direction + count (forward/back/left/right/turn, N steps). No HTTP hop to the mind for
  parsing — voice→intent is the Realtime session's job; the body executes the resulting tool call.
- **Step → `/cmd_vel` translation:** map one "step" to a bounded nudge and sequence N of them, then
  return control to the conversation (await next instruction).
- **Optional vision confirmation:** sample a frame to the mind vision wrapper ("is [person] in
  view / centered?") to confirm arrival or correct heading. Same `stream frame → ask mind → act`
  pattern as Personal/Find, but here it is a **check on voice-driven motion**, not the primary
  driver.

## Non-goals
- **Autonomous visual servoing** — that is Find mode (`module-find-mode.md`). Friend does not drive
  itself toward a target from vision; the human gives every move via voice.
- **Mapping / odometry / SLAM / UWB / GPS** — explicitly out. No metric world model; "steps" are
  open-loop nudges, not closed-loop pose targets. (This is the whole reason Friend exists.)
- **The Realtime session itself** — voice I/O, session lifecycle, tool dispatch, and degradation
  live in `module-realtime-session.md`. This PRD defines only the Friend prompt + Friend tools +
  step translation.
- **The mind vision wrapper internals** — defined in the mind/vision work; consumed here.
- New low-level motion primitives — Friend reuses the existing clamped `/cmd_vel` reflex path.
- Auth — LAN/Tailscale tool, no auth by design (OpenAPI document-level `security: [{}]`).

## Requirements

### Mode entry / exit (shared mode machine)
- Selected via `POST /mode` (the shared switch used by Personal/Find). Entry takes a target
  person (name/description). Friend, Personal, and Find share the **same `stream frame → ask mind →
  act` scaffolding and one mode-state source of truth**; Friend's difference is that the *act* step
  is driven by **voice-parsed steps**, not by a vision verdict.
- On entry: switch the Realtime session to the Friend prompt + register the step-nav tool(s).
- On exit (mode change or `/stop`-initiated abort): zero motion, deregister Friend tools, restore
  the prior Realtime prompt. Leaving Friend never leaves the body moving.

### Realtime prompt config
- Persona: "You are looking for **[person]**. Ask the user, one instruction at a time, where they
  are. Take step-based directions and call `nav_steps` for each. After moving, confirm and ask for
  the next step until you reach them."
- The session asks → listens → emits a tool call → the body executes → the session acknowledges and
  asks again. The conversation is the loop; the body is stateless between instructions beyond
  "which mode + which target."

### Step → `/cmd_vel` translation
- Tool call carries a **direction** (`forward` | `back` | `left` | `right` | `turn_left` |
  `turn_right`) and a **count** N.
- A **step** = one bounded nudge: a defined velocity held for a defined duration (see "step unit").
  N steps = N sequenced nudges in that direction.
- Translate to `/cmd_vel`: linear directions set `vx`/`vy` (clamped ±0.6 m/s); turns set `wz`
  (clamped ±1.2 rad/s). Each nudge is re-sent at the publish cadence for its duration so the deadman
  never zeroes it mid-step, then explicitly zeroed between steps.
- Sequencing is bounded and abortable: a long "10 steps forward" is N discrete deadman-guarded
  nudges, not one long open command. `/stop` cuts the sequence at the current nudge.

### The "step" unit
- A step is a **single tunable constant**: `(step_speed, step_duration)` for linear steps and
  `(step_yaw, step_turn_duration)` for turns (one source of truth, configurable). Distance per step
  is `step_speed × step_duration` (open-loop, un-verified — see open questions).
- Defaults must sit inside the clamp envelope (e.g. `step_speed ≤ 0.6 m/s`, `step_yaw ≤ 1.2 rad/s`).
- Reusing the existing nav-nudge constants (`linear_step` / `angular_step`, the `/up`–`/right`
  feel) is the natural baseline so a "step" matches the manual nudge clients already know.

### Waiting for the next instruction
- After executing N steps the body **returns to rest** (velocity zeroed, deadman idle) and yields to
  the Realtime session for the next utterance. Friend's default state is **stopped, listening**.
- No instruction → no motion. The body does not drift, repeat the last step, or self-navigate while
  waiting.

### Optional vision confirmation of target
- On request (e.g. user says "do you see her?" or after a step sequence), sample a frame to the
  **mind vision wrapper** with the target description; the result feeds back into the Realtime
  session as context ("[person] is centered / to your left / not visible").
- This is advisory: it informs the conversation and can suggest a corrective step, but **it does not
  command motion on its own** — the user (via the session) still issues the nudge. Same wrapper and
  frame-sampling path Personal/Find use.

## Safety
- **All motion is clamped and deadman-guarded.** Every step goes through `/cmd_vel`'s existing
  clamps (±0.6 m/s linear, ±1.2 rad/s yaw) and the deadman window (`command_timeout`, default
  0.5 s). Friend introduces no unclamped path.
- **`/stop` overrides everything.** A panic `/stop` (or a spoken "stop" routed to it) immediately
  zeroes velocity and aborts any in-flight step sequence — highest priority, works even if the
  Realtime session or mind is down.
- **Step nudges are bounded.** `step_speed`/`step_yaw` sit inside the clamp envelope and
  `step_duration` is short; "N steps" is N discrete bounded nudges with re-zeroing between them, so
  a mis-parsed large count cannot become one long runaway command.
- **Degradation.** If the Realtime session drops, Friend stops issuing steps and the body stays safe
  (reflex/deadman + `/stop` remain live, per the OpenAPI degradation contract). If the mind is
  unreachable, vision confirmation is skipped (`502`) but voice-driven stepping still works — vision
  is optional.
- **Clear-space expectation.** Like other motion, the user should keep the path clear; the body has
  no obstacle sensing on the Air (see open questions).

## Dependencies
- **`module-realtime-session.md`** — the body-hosted Realtime session: voice I/O, prompt swapping,
  in-process tool dispatch, and session degradation. Friend registers its prompt + `nav_steps` tool
  here.
- **Shared mode state machine** — the `POST /mode` switch and the `stream frame → ask mind → act`
  scaffolding shared with `module-find-mode.md` and `module-personal-mode.md` (one mode source of
  truth, reflected in `/ws/state`).
- **Mind vision wrapper** — frame in + target description → "is [person] in view / where" (Phase 1
  GPT-4o vision endpoint), reached over the existing frame-sampling path. Optional.
- The hub's clamped, deadman-guarded `/cmd_vel` reflex path and `/stop` (M0, done).
- Phase 3 / M3; depends on Phase 2 (Realtime session + mode system).

## Success criteria
- In Friend mode with a named target, the user gives step-based directions ("2 steps forward,
  3 steps left") and **Yugo follows them** — each instruction becomes a bounded `/cmd_vel` step
  sequence, executed, then the body waits for the next.
- Steps are direction-correct and roughly proportional (N steps ≈ N × one-step distance, open-loop).
- Between instructions the body is stopped and listening — no drift, no self-navigation.
- `/stop` aborts an in-flight sequence immediately; all motion stayed within the clamp/deadman
  envelope throughout.
- Optional vision confirmation reports whether the target is in view and feeds the conversation,
  without commanding motion by itself.
- Realtime-down / mind-down leave the body safe and `/stop`-controllable.

## Open questions
- **Step → distance mapping.** What `(step_speed, step_duration)` makes a "step" feel like a human
  step (~0.5–0.7 m) on the Air, given open-loop drift and no odometry? Calibrate empirically; expose
  as the single tunable constant. Do turns use degrees-per-step or a fixed yaw nudge?
- **Obstacle handling.** The Air has no LiDAR and Friend has no obstacle sensing — does the body
  rely entirely on the human keeping the path clear, or can the optional vision check flag an
  obstruction before/within a step sequence? What stops a "forward" into a wall?
- **What happens at the target.** When the user (or vision) says Yugo has reached the companion,
  what is the arrival behavior — `Sit`, `Hello`/`FingerHeart`, exit Friend mode, hand off to a
  greeting? (Find sits on arrival; should Friend mirror that, or greet?)
- **Step granularity vs latency.** N discrete re-zeroed nudges add inter-step gaps; is a smoothly
  re-published single direction for the whole N-step span (still clamped, still deadman-fed,
  `/stop`-abortable) better UX, or does discrete stepping stay safer and more predictable?
- **Ambiguous / compound instructions.** How does the prompt handle "go around the couch" or
  "a little to the left" — does the Realtime session refuse non-step phrasing and re-ask for steps,
  or estimate a step count?
- **Diagonal / combined steps.** Is "forward-left" one tool call setting both `vx` and `vy`, or must
  the session decompose into sequential single-axis steps?
