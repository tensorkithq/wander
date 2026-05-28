# Yugo (wander)

A fun-first **reality-instrument companion** on a Unitree **Go2 Air**, driven by DimOS. You talk to
it, play with it, and hand it a phone "wand"; it senses the room and reacts with motion, light, and
voice.

**Architecture — body + mind** (see `prd/architecture-body.md`, `prd/architecture-mind.md`):
- **Body** = a light **local FastAPI** (`yugo/`) on the LAN: holds the WebRTC link to the dog,
  control + reflex/deadman, the app contract. **Torch-free.**
- **Mind** = cloud intelligence the body delegates to (OpenAI reasoning, perception, Deepgram +
  ElevenLabs voice).

## Run the robot (the body)
```bash
# connect Yugo to wifi + get its IP, then start the body — full reference in laptop/api.txt
ROBOT_IP=192.168.202.107 .venv/bin/uvicorn yugo.main:app --host 0.0.0.0 --port 8080 --reload
```
See **`laptop/api.txt`** for `dimos go2tool` wifi-provisioning, the route table, and curl examples.

## ⚠️ Do NOT `dimos run unitree-go2` on this machine
That name loads DimOS's **"smart" mapping blueprint** (`blueprints/smart/unitree_go2.py`), which:
- **Requires `torch`** — it imports the mapping/memory/embedding stack
  (`mapping.voxels → memory2.module → models.embedding → import torch`) at load time. This repo's
  body is **deliberately torch-free**, so it fails with `ModuleNotFoundError: No module named 'torch'`.
- **Is built around LiDAR** (`VoxelGridMapper`, `CostMapper`, `PointCloud2`) — which the **Air does
  not have**, so the mapping/nav panels run dark on an Air even with torch installed.

This is **not** about "agentic vs not": both **smart** and **agentic** blueprints pull torch + LiDAR.
Only **`basic`** is lightweight. So:

| Want… | Run |
|---|---|
| The Yugo body (recommended) | `uvicorn yugo.main:app` (torch-free, talks to the dog via `unitree_webrtc_connect`) |
| A DimOS-native camera+control blueprint | `dimos run unitree-go2-basic` (torch-free, no mapping) |
| Mapping/agentic (`unitree-go2`, `…-agentic`) | ❌ needs torch **and** LiDAR — wrong fit for an Air |

## Layout
- `yugo/` — the body FastAPI (robot I/O, control, deadman, persistence) — see `yugo/README.md`
- `laptop/api.txt` — routes, curl reference, wifi connect (`go2tool`), start commands
- `prd/` — architecture (body/mind), `openapi.yaml` surface spec, workstream PRDs
- `gpu/` — cloud "brain" node runbook
- `docs/plans/` — design docs
- `scripts/`, `utils/` — test harness + standalone robot utilities (`go2_trick.py`, `go2_teleop.py`)
