# WebRTC Video Feed Relay — Design

**Date:** 2026-05-29
**Status:** Approved (brainstorming) — ready for implementation planning
**Component:** `yugo` hub (FastAPI, `yugo.main`), namespace `feed`

## Problem & goal

Stream the Go2's camera ("what the robot sees") from the Yugo hub to viewers with
low latency, so we can pilot/observe the dog. Today the only video is MJPEG on the
**deprecated** WebBridge (`:5555`). We want it on the hub (`:8080`) over WebRTC, and
delivering it there removes the WebBridge's last unique capability — finishing its
deprecation.

Acronyms used below (expanded per request):
- **ICE** — Interactive Connectivity Establishment
- **STUN** — Session Traversal Utilities for NAT
- **TURN** — Traversal Using Relays around NAT
- **SDP** — Session Description Protocol
- **WHIP** — WebRTC-HTTP Ingestion Protocol

## Scope (v1)

- **In:** a hub-served HTML **cockpit** at `GET /feed` — a grid with one live video
  pane plus telemetry side-panes — and a minimal `/ws/state` WebSocket feeding the
  panes. WebRTC relay for **1–2 concurrent viewers** on the **LAN only**.
- **Deferred:** native app (will reuse the same `/feed/offer` signaling + `/ws/state`
  later via `react-native-webrtc`); detections/mood panes (depend on the mind's
  perception loop — rendered as "pending" placeholders for now); audio.
- **Out:** multi-viewer/broadcast scale (would need HLS/LL-HLS or a passthrough SFU),
  NAT traversal / remote access (no Tailscale in this configuration), authentication
  (inherits the hub's no-auth-on-LAN stance — do not expose the port publicly).

## Decisions (from brainstorming)

| Question | Decision |
|---|---|
| v1 scope | Cockpit: video pane + telemetry panes |
| Native app | HTML cockpit first; app reuses the same WebRTC endpoint later |
| Telemetry data | Build a minimal `/ws/state` now (motion + connection + battery) |
| Concurrency | 1–2 viewers; no hard cap needed |
| Transport approach | **A** — aiortc transcoding relay; **B** (decode→WS/MJPEG) kept as fallback / native-app path |
| Tailscale | Not required; LAN-only |
| Tests | Fast tier only (no heavy WebRTC media-loopback in CI) |
| Namespace | `feed` (not `video_feed`) |

## Approach

**A — aiortc transcoding relay (chosen).** The hub sources frames from the dog
connection's decoded frame observable, holds the latest frame, and serves it to each
viewer's WebRTC peer connection (aiortc re-encodes per peer). Signaling is a single
**WHIP**-style HTTP round-trip.

Rejected for v1:
- **B — decode → WebSocket/MJPEG.** Simpler, no signaling, but higher latency and no
  audio path. Kept in our back pocket as the native-app transport and as a safety
  valve if the loop integration proves painful.
- **C — true passthrough SFU sidecar (Pion/mediasoup/GStreamer).** Lowest CPU/latency
  and real encoded-RTP passthrough, but a whole second runtime; overkill for 1–2
  viewers. This is the path *if* broadcast becomes a product pillar.

**Why source from frames, not the raw inbound track:** aiortc re-encodes outbound
regardless, so there is no quality/CPU advantage to grabbing the raw aiortc track —
and the driver fires its track callback only once at connect (racy to capture late).
`conn.raw_video_stream()` is a memoized RxPY `Observable[av.VideoFrame]` that already
handles inbound capture; sourcing from it is robust and supported.

## Architecture

Three asyncio loops, cleanly separated:

```
 Go2 ──H.264/WebRTC──▶ conn.loop (daemon thread, unitree driver)
                          │  raw_video_stream(): Observable[av.VideoFrame]
                          ▼
                   FeedRelay (own asyncio loop, own thread)
                     • on_frame → store latest av.VideoFrame (lock + tick)
                     • owns all OUTBOUND aiortc RTCPeerConnections
                     • RobotCameraTrack.recv() → latest frame, monotonic pts
                          ▲ run_coroutine_threadsafe(create_answer, relay_loop)
                          │
 Browser ◀─WebRTC video──┤  uvicorn loop (FastAPI)
   cockpit  ◀────────────┤  GET /feed (HTML/JS)   POST /feed/offer
   panes    ◀──WS────────┘  WS /ws/state (motion + health + battery @ ~10 Hz)
```

- **uvicorn loop** runs the FastAPI handlers. The `POST /feed/offer` handler marshals
  to the relay loop via `run_coroutine_threadsafe(relay.create_answer(offer), relay_loop)`
  and awaits the future.
- **Relay loop** (dedicated thread) owns *all* outbound aiortc objects, so aiortc lives
  on exactly one loop. Viewers' `RobotCameraTrack`s read one shared "latest frame" — no
  `MediaRelay` needed at this scale.
- **conn loop** is the dog connection's existing loop. Inbound frames cross to the relay
  as a single shared `av.VideoFrame` under a lock; the relay loop is woken via
  `call_soon_threadsafe`.

## Components & files

**New backend:**
- `yugo/controllers/FeedRelay.py` — relay loop + thread; subscribes to an **injectable
  frame source** (default `conn.raw_video_stream()`; synthetic for tests); holds latest
  `av.VideoFrame`; defines `RobotCameraTrack(MediaStreamTrack)`; manages the set of
  outbound `RTCPeerConnection`s; `async create_answer(offer) -> answer`, `health()`,
  `close()`.
- `yugo/controllers/StateAggregator.py` — assembles the `/ws/state` frame: motion
  (`MotionController.state()`), connection (`healthz`), battery (from
  `conn.lowstate_stream`); pushes at ~10 Hz.
- `yugo/routers/FeedRouter.py` (tag `telemetry`) — `GET /feed` (cockpit HTML),
  `POST /feed/offer` (signaling), `GET /feed/health`, `WS /ws/state`.
- `yugo/static/cockpit.html` — grid cockpit: `<video>` pane + telemetry panes; vanilla-JS
  `RTCPeerConnection` against `/feed/offer`; `/ws/state` WebSocket. Replaces the
  deprecated `bridge/static/debug.html`.

**Touched:**
- `yugo/main.py` — lifespan creates/starts `FeedRelay` + `StateAggregator` on
  `app.state`; stops them on shutdown.
- `yugo/dependencies.py` — `get_feed` (like `get_motion`).
- `yugo/config.py` — `FeedConfig` (target fps, max viewers, ICE servers = none for LAN).
- `yugo/schemas/RobotSchema.py` — `SdpOffer`, `SdpAnswer`, `StateFrame`, `FeedHealth`.
- `pyproject.toml` — declare `aiortc` + `av` explicitly (present transitively today).
- `yugo/openapi.yaml` — add `/feed`, `/feed/offer`, `/feed/health`; mark `/ws/state`
  implemented; flip the `:5555` MJPEG note from "no hub equivalent yet" to "superseded
  by `/feed`."

## Data flow & signaling

**Signaling — WHIP-style, single-shot, non-trickle:**
1. Browser loads `GET /feed`; cockpit JS creates `RTCPeerConnection` with **no ICE
   servers**, `addTransceiver('video','recvonly')`, `createOffer`, `setLocalDescription`,
   waits for ICE gathering to complete (bundles host candidates into one SDP offer).
2. JS `POST /feed/offer` with the offer SDP.
3. Hub handler → `run_coroutine_threadsafe(relay.create_answer(offer), relay_loop)`,
   awaits, returns the answer SDP.
4. `relay.create_answer` (relay loop): new `RTCPeerConnection`, `addTrack(RobotCameraTrack)`,
   `setRemoteDescription(offer)`, `createAnswer`, gather host candidates, return
   `localDescription`. Track the pc; `connectionstatechange → failed/closed` discards it.
5. Browser `setRemoteDescription(answer)`; `ontrack` → `<video>.srcObject`.

**Frame path:** RxPY subscription on the conn thread stores the latest `av.VideoFrame`
and wakes the relay loop (`call_soon_threadsafe`). Each `RobotCameraTrack.recv()` paces to
target fps, stamps monotonic `pts/time_base`, returns the shared latest frame; aiortc
encodes H.264 per peer.

**`/ws/state`:** on connect, push a JSON `StateFrame` at ~10 Hz (motion, `connected`,
battery). Read-only; independent of the video peer connections.

**Lifecycle:** relay loop starts at app startup; frame subscription attaches when the
dog is connected; viewers attach/detach independently; shutdown closes all peer
connections and the subscription.

## Error handling & degradation

Governing principle: **the feed is non-critical telemetry; it can fail freely and never
touches safety.** The deadman/nav reflex layer and `/stop` share no state with the relay.

- **No dog / offline (`YUGO_NO_ROBOT`):** no frame source. `GET /feed` still serves;
  `POST /feed/offer` → `503` ("no video source") unless a synthetic source is enabled.
  `/ws/state` still streams (robot fields null/0, `connected:false`).
- **Connected, no frames yet:** `recv()` blocks until the first frame (with timeout) or
  emits a placeholder, so negotiation completes instead of hanging.
- **Viewer drops / blip:** `connectionstatechange → failed/disconnected/closed` ⇒ relay
  closes/discards that pc; others and the frame subscription are unaffected.
- **ICE fails / no candidate pair:** `POST /feed/offer` future times out (~5 s) → `504`;
  the cockpit surfaces "couldn't connect" and can retry.
- **Frame source error (RxPY `on_error`):** log, drop the subscription, re-subscribe when
  `connected` returns; viewers see the last frame freeze then a placeholder.
- **Relay loop isolation:** a per-pc exception is caught and never propagates to the relay
  loop, uvicorn, or the conn loop.
- **Backpressure:** `recv()` serves only the latest frame (drops stale); a slow encoder
  degrades to lower fps, never unbounded buffering/latency.

## Testing (fast tier only)

Same ethos as the deadman suite: **boot the actual app under uvicorn, validate from real
responses, no mocks.** The hardware camera is the only stand-in — an **injected synthetic
frame source** (`av.VideoFrame` color bars) enabled via `YUGO_FEED_FAKE=1`, mirroring how
`YUGO_NO_ROBOT` stands in for the dog. No heavy in-process WebRTC media loopback in CI.

- `POST /feed/offer`: malformed → `422`; no source → `503`; synthetic source → `200` with
  a well-formed answer SDP (`type:answer`, has a video m-line). Exercises the real
  `create_answer` path on the relay loop without establishing media.
- `WS /ws/state`: connect to the live server; assert ~10 Hz `StateFrame`s with the
  expected schema (motion present; `connected:false`; battery null offline).
- `GET /feed`: `200`, `text/html`, contains the `RTCPeerConnection` / `/feed/offer` /
  `/ws/state` hooks.
- `GET /feed/health`: `{viewers, source_active}` — relay state assertable over HTTP;
  confirm a closed client pc is reaped.
- **Pure units:** frame pacing + pts stamping (deterministic given a clock);
  `StateAggregator` frame assembly (fake inputs → expected dict).
- **Manual verification (not CI):** open `/feed` in a browser to confirm live video — the
  one thing the fast tier does not prove automatically.

## Open follow-ups (post-v1)

- Native app: `react-native-webrtc` against `/feed/offer` + `/ws/state`.
- Perception panes (detections/mood) once the mind's vision loop lands.
- Snapshot endpoint `GET /feed/frame.jpg` for cheap periodic LLM-vision sampling.
- Delete the WebBridge entirely once `/feed` is in use.
- Scale path (only if broadcast becomes a goal): HLS/LL-HLS or a passthrough SFU.
