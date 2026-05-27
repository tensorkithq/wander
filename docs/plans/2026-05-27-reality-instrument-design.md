# Reality Instrument — Design

**Date:** 2026-05-27
**Status:** Design approved (brainstorming), pre-implementation
**Codename idea:** "Signal Hound" (Signal Wand × robot dog)

## 1. Concept

A personal **reality instrument**: turn the invisible forces in a space (RF/signal density,
magnetic fields, light flicker, vibration, spatial "pressure," air, etc.) into **sound, light,
movement, and visuals**. Fun-first, not useful-first — an instrument / toy / field-recorder /
art object.

Originally specced as a handheld "Signal Wand." This design **ports that concept onto a Unitree
Go2 Air driven by DimOS**, where the dog *becomes* the instrument.

## 2. Embodiment decision

The **dog is the primary embodiment** (an autonomous sensing *creature* that roams, senses, and
expresses invisible forces through movement + light + sound + "mood"), **and** a sensor mule
(carries an exotic-sensor payload in Phase 2), **with** a companion porthole so the human can also
see/hear the dog's-eye field.

Every wand concept re-casts onto the dog:

| Wand concept | On the Go2 + DimOS |
|---|---|
| Point wand at wall → hear wiring | Dog walks the room; body **orients toward** anomalies. Locomotion = pointing. |
| Ghost / Creature mode | Gait + posture + LED + voice become the creature. Nervous near RF noise, calm in clean air. |
| Hunt mode | Dog **homes in** on a source (walk up the gradient). The killer demo. |
| Scanner "room aura" | Companion porthole = the surviving "wand" (your window into the field). |
| Synth / LED / haptics | Companion-speaker audio, Go2 front-lamp LED, expressed motion. |
| Mood interpretation | A **DimOS agentic blueprint** (LLM) maps sensor signatures → mood → behavior. |

## 3. Architecture / deployment topology

Three nodes joined by a mesh VPN (**Tailscale/WireGuard**). The split is *forced* by a hard
constraint: DimOS drives the Go2 over **WebRTC `LocalSTA`**, which requires being on the dog's
WiFi — so the cloud server cannot hold the robot connection; the laptop must.

```
   Go2 Air ──WiFi / WebRTC LocalSTA──┐
                                     ▼
   ┌──────────────────────────────────┐        ┌───────────────────────────┐
   │  LAPTOP (M2 Pro) — controller/IO  │◀─────▶ │  CLOUD GPU — "the brain"    │
   │  • holds WebRTC link to dog       │Tailscale│ • DimOS mood agent (LLM)   │
   │  • reflex/safety layer (low lat)  │  (DDS)  │ • perception (VLM, LiDAR)  │
   │  • generative audio → laptop spkr │        │ • generative-audio params  │
   │  • Rerun browser viewer (porthole)│        │ • heavy models             │
   │  • light install (fits ~38GB free)│        └───────────────────────────┘
   └──────────────────────────────────┘
                     ▲
                     │ Tailscale (WebSocket/REST + Web Audio)
              ┌──────────────┐
              │  EXPO APP     │  mobile companion + "mini-wand"
              │  (web/iOS/And)│  expo-sensors → 2nd sensor node
              └──────────────┘
```

**Latency rule:** reactive/safety behavior stays on the laptop (ms to the dog); cognition / mood /
perception live on the cloud (hundreds of ms is fine for creature behavior). Do **not** put the
tight control loop across the internet. Camera frames stream laptop→cloud for the heavy VLM; the
M2 Pro can also run perception locally via MPS if the hop is costly (A/B test).

**Transport caveat:** LCM is UDP-multicast (LAN-only). Across Tailscale use **CycloneDDS**
(DimOS `--extra dds`) configured for unicast, not LCM.

## 4. Native Go2 **Air** capability inventory

DimOS `dimos/robot/unitree/go2/connection.py` uses `unitree_webrtc_connect` (consumer interface,
**not** EDU-only SDK), so the Air works. Over that link:

**Available natively (via DimOS WebRTC):**

| Channel | Use |
|---|---|
| `lidar_stream()` → PointCloud2 | ⚠️ **Empty on this Air** (no usable LiDAR — see §4a). Spatial sensing falls back to the camera. |
| `lowstate_stream()` → LowStateMsg | IMU (vibration, tremor, tilt, motion energy) + battery (metabolism/energy mood) |
| `video_stream()` → RGB | **Primary spatial + scene sensor** (LiDAR is dark). Light flicker (mains/PWM via rolling-shutter banding), color temp, screen glow, motion, people, **object detection (YOLO)**, VLM scene-mood |
| `odom_stream()` → Pose | Position/motion for Music mode + Hunt gradient-walking |
| `move()` Twist, `standup/balance_stand/free_walk/liedown`, `enable_rage_mode()` | **Primary expression**: creep, skitter, cower, alert-stance, point, walk up-gradient |
| LED color (VUI topic) | Ghost-mode strobe, Creature color-mood |

**NOT available on the Air (moves off-dog or to Phase 2):**
- Foot-force sensors (EDU-only hardware)
- Onboard mic (no voice function) and onboard speaker (none) → **audio in/out lives on the companion**
- RF-scan-from-the-dog (can't run a WiFi scan on the Air) → **RF density via companion or Phase-2 puck**
- Low-level joint torque control (WebRTC is high-level; lowstate is read-only)
- **LiDAR point cloud — NOT usable on this Air** (verified empirically 2026-05-28)

### §4a — LiDAR correction (verified 2026-05-28)
The original §4 listed LiDAR as available. **It is not on this Air.** Running the default
LiDAR-robot blueprint (`unitree-go2`, with voxel-grid mapper + costmap + A* planner + frontier
explorer) on the Air: the camera feed and robot pose populate in Rerun, but the **point cloud,
voxel map, costmap, and planned paths stay empty** — no LiDAR is feeding them. The L1 4D LiDAR is
the feature that distinguishes Go2 **Pro/EDU** from the **Air** budget tier; the Air ships without
it. (If a quick physical check ever shows otherwise, revisit — but **design as camera-first, no
LiDAR**.)

**Consequences:**
- Spatial "pressure" / room-shape / crowd-density sensing moves from LiDAR to the **camera**
  (depth-from-vision, motion, scene VLM) and/or the **Phase-2 puck**.
- Use **camera-first blueprints** (`unitree-go2-basic`, `unitree-go2-detection`,
  `unitree-go2-keyboard-teleop`), NOT the mapping/nav stack — most of that dashboard is dark on the Air.
- **Object detection on the live camera (YOLO)** is the most visually rewarding thing the Air can
  do — a strong native input for Creature/Scanner modes.

## 5. The core loop

`sensors → DimOS module (over DDS) → agentic "mood" interpreter → expression (locomotion + LED) +
companion audio + porthole`

- **Sense:** native Air streams (+ phone sensors as a 2nd node, + Phase-2 puck later).
- **Interpret:** DimOS agentic blueprint maps sensor signatures → mood state → behavior intent.
- **Express:** gait/pose/special-moves + LED on the dog; generative audio on laptop/phone; visuals
  in the porthole.

## 6. Modes (native-first)

- **Creature** ✅ rich, native (IMU + LiDAR + camera + battery → mood → gait/LED).
- **Hunt** ✅ for RF sources via companion/phone RSSI (walk up-gradient); magnetic/wire hunt → Phase 2.
- **Ghost** 🟡 spooky native (flicker + vibration + RF); magnetism is the missing soul → Phase 2.
- **Scanner** ✅ porthole fuses native channels into "room aura."
- **Music** ✅ map motion + signal density → sequencer.

## 7. Companion app (Expo + FastAPI)

- DimOS `web` extra = **FastAPI + Uvicorn**. Expose a **WebSocket** of live state (mood, per-sensor
  scalars, mode) + **REST** for commands. Expo app renders its own light gauges/aura/controls.
- **Two complementary portholes:** Rerun browser viewer (rich desktop/debug) + Expo app (polished
  mobile companion + wand). Same streams.
- **Audio on the companion:** `expo-av` / Web Audio for generative sound (laptop is primary speaker).
- **Phone-as-mini-wand (in scope, fast-follow):** `expo-sensors` gives **full native magnetometer**
  + accel/gyro/baro/light — no iOS Safari web-API limits. Phone POSTs its readings back to DimOS as
  a second sensor node, partially resurrecting the handheld wand.

## 8. Phasing

- **Phase 1 — exhaust the native Air** + stand up the loop, the split topology, the companion app.
- **Phase 2 — strap-on sensor puck** (ESP32/Pi publishing over DDS): **magnetometer** first (most
  creature-like), then VOC/air, light-spectrum, RF/SDR, ultrasonic, optional puck speaker. Designed
  for **hot-add** — new sensors = new topics, no re-architecture.

## 9. v1 milestone ("if this works, it's already magic")

**Creature mode + Wi-Fi/BT Hunt:** the dog roams, shifts gait/LED/mood with the room, and visibly
**creeps toward an RF source**, with the porthole + laptop audio live.

## 10. Open questions / risks

- WebRTC `LocalSTA` reliability + LiDAR/LED access on the specific Air firmware → verify early.
- DDS-over-Tailscale unicast config (CycloneDDS) → spike before relying on it.
- Where perception runs (cloud vs M2 Pro/MPS) → measure the frame-stream hop.
- RF density without on-dog scanning → companion-machine scan vs Phase-2 puck (decide in Phase 1).
- Phone magnetometer fusion with a moving dog (reference frames) → Phase-2-ish concern.

## 11. Out of scope (YAGNI for now)

- Native (non-Expo) app.
- Full 5-mode polish before v1 (build Creature+Hunt first).
- The full exotic sensor pack up front (Phase 2, incrementally).
- Any "useful"/productized framing — this is fun-first.

## 12. Phase-1 cloud prototyping setup (RunPod)

Time-boxed GPU rental for prototyping. **Expected cost: a few dollars/day** (per-hour billing;
stop when idle), not the ~$20 ceiling.

**GPU choice — CHOSEN: RTX A5000 (24 GB) @ $0.27/hr on RunPod.** Best $/VRAM on the menu: 24 GB for
$0.27, Ampere GA102 (~28 TFLOPS, 768 GB/s — ~2× the 4000 Ada's bandwidth), 48 GB RAM / 9 vCPU host
(meets the ≥8 vCPU / ≥32 GB bar). 24 GB comfortably fits the Phase-1 perception stack with headroom
for a small local LLM later. Note: the 4090 was **Unavailable** on RunPod at selection time.

Caveat: A5000 is **Low availability / 1 max** — may take a retry to secure; once running, **stop to a
Network Volume rather than terminate** so you don't lose the slot. **Fallback: A40 (48 GB, $0.44/hr,
Medium stock)** if the A5000 can't be obtained.

Reference rates seen (RunPod, May 2026): RTX A5000 24 GB $0.27 (chosen) · RTX 4000 Ada 20 GB $0.26
(Low) · A40 48 GB $0.44 (Medium, fallback) · L4 24 GB $0.39 · RTX 3090 24 GB $0.46 · RTX 4090 24 GB
$0.69 (Unavailable) · RTX PRO 4500 32 GB $0.74 (High stock, guaranteed-launch fallback). Skip
48 GB+ workstation cards and H100/A100/B300 — overkill for perception.

**RunPod recipe:**
1. **Pod** (not Serverless — Serverless has no interactive dev). Community Cloud → **RTX 4090**.
2. **Template: PyTorch 2.8.0 (CUDA 12.8)** — torch + CUDA pre-baked, saves GPU-hours/disk.
   Other templates (ComfyUI, vLLM, Axolotl, AI Toolkit, Diffusion Pipe) are off-target.
3. **Attach a Network Volume** (persistent storage) → can stop the pod to kill GPU billing, and
   survive spot reclaim without losing env/code.
4. Add SSH public key; expose **TCP port 22** for direct SSH (VS Code / Cursor remote).
5. Install **Tailscale in userspace mode** (`tailscaled --tun=userspace-networking`) — containers
   lack `/dev/net/tun`. (A full GPU **VM** avoids this entirely if the container fight annoys.)
6. **SSH over the tailnet IP** — same secure path the DDS traffic uses; sidesteps port-mapping.
7. Scoped **`uv`** install of DimOS (perception/agents/web extras) on top of the base image.

**Caveats:**
- **Torch-version alignment:** the provisioned A5000 pod's image ships **torch 2.4.1+cu124**
  (verified 2026-05-27), not 2.8/cu128. **Do not upgrade torch** — pin `torch==2.4.1` and install
  DimOS scoped extras (`agents,perception,web`), avoiding the `cuda`/`all` extras that drag
  torch-locked `xformers`. See `gpu/runbook.txt` for the exact agent-followable procedure.
- **Spot/interruptible is fine for prototyping** IF work lives on the Network Volume + committed to git.
- **Pre-bake setup** (uv install + Tailscale) as a startup script so you don't pay GPU-hours to install.

**Reminder — you may not need the cloud GPU for Phase 1 at all:** the M2 Pro laptop has MPS and is
already in the loop; the cloud box becomes necessary mainly for real-time VLM/object-detection or
running while away from the dog's network.
