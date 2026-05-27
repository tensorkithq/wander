# Reality Instrument — GPU "Brain" Node Setup Report

**Date:** 2026-05-27
**Operator:** Claude Code (autonomous execution, "no questions" mandate)
**Runbook executed:** `wander/gpu/runbook.txt` (the brain node)
**Design reference:** `wander/docs/plans/2026-05-27-reality-instrument-design.md`
**Target repo:** https://github.com/dimensionalOS/dimos (`#blueprints`)

---

## 1. Outcome

**DimOS brain node is installed and operational on this RunPod A5000 pod.**
The compute/perception/agent stack imports and runs; `torch` was preserved at the
pre-baked version throughout. Two stages (Tailscale auth, cross-machine DDS) are
**blocked on inputs this node cannot supply alone** — a Tailscale credential and the
laptop node's tailnet IP. Details in §5.

| Stage | Result |
|---|---|
| 1 — box prep (caches, apt libs, uv) | ✅ done |
| 2 — DimOS brain extras `[agents,perception,web]` | ✅ done + verified |
| 4 — DDS transport `[dds]` (cyclonedds) | ✅ installed; config skeleton written |
| 3 — Tailscale join tailnet | ⚠️ daemon up, **auth blocked** (no `TS_AUTHKEY`) |
| 4 — CycloneDDS unicast peering | ⚠️ **blocked** (needs laptop IP; userspace-mode conflict) |

---

## 2. Environment verified (matches runbook's "verified 2026-05-27")

- Host: RunPod pod, container, `hostname=54b70ca7f4dc`, **user=`admin`** (not `root`), passwordless sudo
- GPU: **NVIDIA RTX A5000, 24564 MiB, driver 570.211.01**
- PyTorch: **`torch 2.4.1+cu124`, `cuda.is_available()==True`** (sees the A5000) — unchanged end-to-end
- Disk: `/` overlay 36 G (ephemeral) · `/workspace` network volume (persistent) — confirmed
- Python: system `/usr/bin/python3` = **3.11.10**, site `/usr/local/lib/python3.11/dist-packages` (where pre-baked torch lives)

---

## 3. What was executed, stage by stage

### Stage 1 — box prep ✅
- Routed heavy data to the persistent volume: created `/workspace/cache/{uv,pip,hf}` and `/workspace/src`; exported `UV_CACHE_DIR`/`PIP_CACHE_DIR`/`HF_HOME`/`PATH` into `~/.bashrc` (adapted from the runbook's `/root` → `/home/admin`).
- `apt-get install`: git git-lfs g++ python3-dev portaudio19-dev libturbojpeg libgl1 libegl1 curl — installed.
- Installed **uv 0.11.16**.
- **VERIFY:** torch line printed `2.4.1+cu124 | cuda True | NVIDIA RTX A5000`. ✅

### Stage 2 — DimOS brain extras ✅
- Pinned `torch==2.4.1` in `/workspace/src/constraints.txt`.
- Cloned `dimos` to `/workspace/src/dimos` (HEAD `473160340` "feat: publish local slice of global map (#2257)"; full git-LFS assets pulled, ~40 G).
- Installed `-e '.[agents,perception,web]'` against `/usr/bin/python3` with the torch constraint.
- **VERIFY (all passed):**
  - `torch 2.4.1+cu124 | cuda True | NVIDIA RTX A5000` — **pin held; torch never changed.**
  - `import dimos` ok.
  - Brain subsystems import: `langchain, anthropic, openai, faster_whisper, ultralytics, transformers, fastapi, uvicorn`.
  - `dimos` CLI live at `/usr/local/bin/dimos`.
- Result: **179 packages installed**, `dimos==0.0.12` (editable). `onnxruntime` resolved to the **CPU** build (no CUDA-version fight). **No `xformers`** (the `cuda`/`all` extras were correctly avoided per the runbook).

### Stage 4 (part A) — DDS extra ✅
- Installed `-e '.[dds]'` → `cyclonedds==11.0.1`; `import cyclonedds` ok; torch still `2.4.1+cu124 True`.
- Wrote CycloneDDS unicast config skeleton: **`/workspace/src/cyclonedds.xml`** (placeholder `LAPTOP_TS_IP`).

---

## 4. Deviations from the runbook (and why)

1. **`root` → `admin`.** The runbook assumes `user=root`. This pod runs as `admin` with passwordless sudo. Env block went to `/home/admin/.bashrc`; apt and the final package link used `sudo`.
2. **Install required `sudo` for the link step.** First `uv pip install` (as `admin`) **failed at link** with `Permission denied` removing root-owned `Jinja2-3.1.3.dist-info` — the base image's site-packages are root-owned and the `web` extra bumps Jinja2 to ≥3.1.6. Re-ran the identical command under `sudo env …` (cache warm → 0 re-downloads) and it completed clean (`EXIT=0`). This is the one non-obvious gotcha for this pod; bake `sudo` into the brain install on root-owned base images.
3. **`numpy` upgraded 1.26.3 → 2.3.5** (pulled by the perception stack). Explicitly verified torch 2.4.1 interops with NumPy 2.x (CUDA tensor round-trip from a numpy array succeeded), so this is safe — but it's a change the runbook didn't anticipate. Only `torch` was pinned; everything else floated.
4. **`UV_LINK_MODE=copy`.** uv warned it can't hardlink across filesystems (cache on `/workspace`, target on `/usr`); set copy mode to silence it. Cosmetic/perf only.

---

## 5. Blockers (require operator input — could not self-complete)

### 5a. Tailscale auth — BLOCKED
- Installed Tailscale **1.98.3**; started `tailscaled` in **userspace-networking** mode (`--socks5-server=localhost:1055`, state at `/workspace/tailscale-state`) — required because the container has **no `/dev/net/tun`** (verified).
- `tailscale up --ssh --hostname=ri-gpu-brain` cannot complete: **no `TS_AUTHKEY` in the environment** and no interactive operator. Status: `Logged out`.
- **To finish (operator):** either
  - `export TS_AUTHKEY=<key from tailnet admin console>` then re-run `sudo tailscale up --ssh --hostname=ri-gpu-brain --authkey="$TS_AUTHKEY"`, or
  - open the live login URL: **https://login.tailscale.com/a/1a17e380148cc** (valid only while this `tailscaled` keeps running).

### 5b. CycloneDDS cross-machine peering — BLOCKED (two reasons)
1. **Needs the laptop's tailnet IP.** The unicast `<Peer address="LAPTOP_TS_IP"/>` can't be filled until the `ri-laptop` node joins the tailnet (laptop runbook Stage 5). Multicast won't traverse Tailscale (design §3).
2. **Runbook conflict I'm flagging:** Stage 4's config binds CycloneDDS to interface **`tailscale0`**, but Stage 3 runs Tailscale in **userspace mode**, which creates **no `tailscale0` kernel NIC** (verified: only `lo` + `eth0` exist). So DDS-over-tailnet **will not work as written**. Resolution options (documented inline in `cyclonedds.xml`):
   - (a) run the brain on a full GPU **VM** (has `/dev/net/tun` → kernel TUN mode → real `tailscale0`) — the design doc's own escape hatch (§3, §12);
   - (b) launch the container with `--device /dev/net/tun --cap-add NET_ADMIN`;
   - (c) shim DDS through the userspace SOCKS5 proxy (non-trivial; CycloneDDS has no native SOCKS).

---

## 6. Persistence caveat (important for stop-to-volume)

`uv pip install --system` writes dependencies to **`/usr/local/lib/python3.11/dist-packages`** — the **ephemeral 36 G overlay**, NOT `/workspace`. On pod **stop-to-volume / restart, the installed packages are lost.** What persists on `/workspace`: the **dimos repo + editable source** (`-e` points at `/workspace/src/dimos`), the **uv/pip/hf caches**, `constraints.txt`, `cyclonedds.xml`, and the Tailscale state dir.
→ **Recovery after restart is fast:** re-run Stage 2 + 4A install commands; with the warm cache it's a link-only pass (no downloads). Recommend baking those two commands into a pod **startup script** (design §12: "pre-bake setup so you don't pay GPU-hours to install").

---

## 7. READY CHECK (runbook's gate)

- [x] `nvidia-smi` shows RTX A5000
- [x] `torch 2.4.1+cu124` and `cuda.is_available() == True`
- [x] `python -c "import dimos"` succeeds
- [ ] `tailscale status` shows `ri-gpu-brain` **AND** the laptop node — **blocked** (auth + no laptop node; §5a)
- [x] caches + repo under `/workspace`; `df -h /` overlay at **14 %** (4.9 G / 36 G) — not near full

**4 of 5 pass.** The open item is entirely the Tailscale/laptop pairing, which is a two-node + credential dependency, not a brain-node install defect.

---

## 8. Handoff / next steps

1. **Operator:** supply `TS_AUTHKEY` (or click the login URL) to finish §5a; then `tailscale ip -4` and record it — the laptop node's CycloneDDS peer.
2. **Decide the DDS transport path** (§5b): VM/kernel-TUN vs container `/dev/net/tun` vs SOCKS shim. Until then, brain↔laptop DDS is non-functional; LAN-only DDS via `eth0` works for local tests.
3. **Stand up the laptop node** (`wander/laptop/runbook.txt`): holds the Go2 WebRTC `LocalSTA` link, reflex layer, Rerun porthole, FastAPI for the Expo app. Fill its `cyclonedds.xml` peer with this node's tailnet IP and vice-versa.
4. **v1 milestone** (design §9): Creature mode + Wi-Fi/BT Hunt — dog roams, gait/LED/mood shift with the room, creeps toward an RF source, porthole + laptop audio live.
5. **Persistence:** add the Stage-2/4A install commands to a pod startup script before the next stop-to-volume.

---

### Appendix — key artifacts on this node
- `/workspace/src/dimos` — DimOS repo (editable install target), HEAD `473160340`
- `/workspace/src/constraints.txt` — `torch==2.4.1` pin
- `/workspace/src/cyclonedds.xml` — DDS unicast skeleton + inline conflict notes
- `/workspace/cache/{uv,pip,hf}` — warm package caches (~9 G)
- `/workspace/tailscaled.log`, `/workspace/tailscale-state` — Tailscale runtime
- `/usr/local/bin/dimos` — CLI entrypoint
