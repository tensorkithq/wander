# PRD — Body Module: Camera Feed (`/feed`)

**Date:** 2026-05-28 · **Status:** draft · **Builds on:** `../yugo/bridge/web_bridge.py` (deprecated, `/video_feed/color_image`)

## Objective
Migrate the MJPEG camera stream off the **deprecated** WebBridge (`web_bridge.py`, port 5555) onto
the **canonical hub** (`yugo/main.py`, port 8080) as `GET /feed`. The bridge's teleop, deadman, and
`/healthz` are already superseded by the hub; the camera is its **only remaining unique capability**.
Once `/feed` lands, the bridge can be **retired entirely** (Phase 1 explicit goal).

Frames arrive over the body's single WebRTC `LocalSTA` link. The body JPEG-encodes them and serves a
continuous `multipart/x-mixed-replace` MJPEG stream — the same wire contract clients already consume
on `:5555`, now on the hub.

Authoritative contract: `../yugo/openapi.yaml` (the `/feed` operation under tag `telemetry`; the
`:5555` server and `/video_feed/color_image` are marked deprecated there).

## Scope
- Add `GET /feed` to the hub (`yugo/main.py`, port 8080), in the `telemetry` tier.
- Subscribe to the WebRTC color-image stream already held by the hub's WebRTC connection — no
  second link. One source of truth for frames.
- JPEG-encode the latest frame and serve it as `multipart/x-mixed-replace; boundary=frame`, matching
  the existing `_mjpeg()` wire format (repeating `--frame` parts, each `Content-Type: image/jpeg`).
- Track frame availability so `GET /healthz`/`GET /state` (or the operation description) can signal
  whether a first frame has arrived. Before the first frame, the stream yields nothing.
- After `/feed` is live and verified, **remove `web_bridge.py`** (or gate it behind a flag) and
  delete the `:5555` server entry from the OpenAPI once no clients target it.

## Non-goals
- WebSocket telemetry (`/ws/state`) — separate Phase 1 module.
- The internal **vision sampling path** (~1–3 fps frames sent to the mind for GPT-4o vision). That is
  a downstream consumer of the same frame source, specified in the mind/vision work — **not** part of
  this stream's output. Noted here only so both readers share one frame source.
- Re-encoding controls (resolution, quality, fps caps), audio, multi-camera, or recording.
- Any control/motion behavior — this module is read-only.
- Auth — LAN/Tailscale tool, no auth by design (per the OpenAPI document-level `security: [{}]`).

## Requirements (objective → endpoint)

### `GET /feed` — MJPEG camera stream
- **Tag:** `telemetry` · **x-execution:** `local` (frames over WebRTC; no cloud call).
- **Response `200`:** an open `multipart/x-mixed-replace; boundary=frame` stream. Each part is
  `Content-Type: image/jpeg` followed by the JPEG bytes.
- **Frame source:** the hub's existing WebRTC color-image subscription. The body holds the latest
  decoded frame and JPEG-encodes it (cv2 `imencode(".jpg", …)`, as in the bridge today).
- **Cadence:** push at up to ~30 fps; stream yields nothing until the first frame arrives.
- **Side effects:** none on the robot (read-only).
- **`have_frame` signal:** the body exposes whether a frame has been received. (Hub `/healthz` shape
  does not currently carry `have_frame`; if surfaced, do it via a documented field rather than
  duplicating the deprecated WebBridge `/healthz`.)
- The legacy path `GET /video_feed/color_image` on `:5555` is the thing being replaced; the canonical
  path on the hub is `/feed`. Do not add a second camera link to keep the legacy path alive.

## Safety
Read-only. No motion, no robot side effects, no clamps or deadman concerns — this module only reads
and encodes frames already flowing over the existing WebRTC link. The single WebRTC link is shared
with control; `/feed` must not open a new connection or interfere with the hub's reflex/deadman loop.

## Dependencies
- The hub's WebRTC `LocalSTA` connection (`yugo/main.py`) — the existing color-image stream.
- `cv2` (JPEG encode), FastAPI `StreamingResponse` (already used by the bridge).
- `ROBOT_IP` (DHCP — re-discovered per session).
- Phase 1 / M1; depends on M0 (done). Blocks **bridge retirement** (the remaining Phase 1 cleanup
  item: "All bridge functionality migrated; bridge code removed or gated behind a flag").

## Success criteria
- `GET /feed` on the hub (`:8080`) serves a live MJPEG stream renderable in an `<img>` tag / MJPEG
  player, with the same wire format as the old `:5555` `/video_feed/color_image`.
- Stream draws frames from the hub's single existing WebRTC link (no second connection).
- Frame availability is observable before/after the first frame arrives.
- The deprecated bridge (`web_bridge.py`, `:5555`) is removed or flag-gated, and the `:5555` server
  entry is dropped from `../yugo/openapi.yaml` once no client targets it.
- The mind vision sampling path can read from the same frame source without a second WebRTC link
  (verified by the downstream vision module, not this PRD).

## Open questions
- **Latest-frame vs per-client encode:** encode once per arriving frame into a shared latest-JPEG
  buffer (as the bridge does) and fan out to all `/feed` clients, vs encode per connection? Shared
  buffer is the single source of truth and matches the existing implementation — confirm it handles
  multiple concurrent `<img>` clients.
- **`have_frame` surfacing:** add a documented field to the hub `/healthz`/`/state`, or rely on the
  stream simply yielding nothing until ready? The OpenAPI hub `/healthz` shape currently omits
  `have_frame`.
- **Shared frame source wiring:** confirm the exact hub hook the WebRTC color-image stream exposes so
  both `/feed` and the mind-sampling path subscribe to one source (one source of truth).
- **Retirement timing:** remove `web_bridge.py` in the same change as `/feed`, or land `/feed` first
  and delete the bridge in a follow-up once clients have cut over?
