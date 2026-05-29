# Wander — watchOS wand

A standalone Apple Watch app that casts spells on Yugo by **wrist motion**. Hold
the on-screen button and flick your wrist; on release it sends the gesture to the
body API and the dog performs the matched trick.

## How it works

The watch has no raw magnetometer for third-party apps, so it casts from
**device motion** instead of the phone's magnetometer:

- While the button is held, CoreMotion `CMDeviceMotion` streams at 50 Hz into two
  parallel `[t_ms, x, y, z]` traces: **user-acceleration** (the gesture's path)
  and **rotation-rate** (its twist).
- On release the app POSTs both to `POST /sensor/spell` as
  `{ "source": "watch-wand", "sample_hz": 50, "accel": [...], "gyro": [...] }`.
- The server (`yugo/controllers/SensorController.py::spell_for_motion`) hashes the
  two channels deterministically into a trick. This is a **separate hash
  namespace** (`m1`) from the phone's magnetometer engine (`v1`), so the iOS wand
  is unaffected — the one endpoint serves both clients. A cast that arrives while
  another is still firing is dropped by the server's single-flight gate.

The spell is computed from gesture *shape* only (the traces are scale/drift
normalized), so raw units (g, rad/s) go straight over the wire — no calibration.

## API target

The body API URL is hardcoded in `wander Watch App/WandCaster.swift`:

```swift
private let apiBase = "https://willette-multicapitate-limnologically.ngrok-free.dev"
```

Change that line to point elsewhere (e.g. a LAN/Tailscale IP). HTTPS works as-is;
for a plain-HTTP LAN address you'd need an ATS exception in the build settings.

## Build & run

Open the project and run — it's a real Xcode project (no XcodeGen):

```sh
open watch/wander/wander.xcodeproj
```

In Xcode: select the **wander Watch App** scheme, set your signing **Team**
(Signing & Capabilities), pick your watch (Series 5+ recommended), and Run. On
first cast the watch asks for Motion permission (the `NSMotionUsageDescription`
prompt, set in the target's Info build settings).

The project uses Xcode 16 **file-system synchronized groups**, so any file added
under `wander Watch App/` is included in the build automatically — no manual
target membership step.

## Files

| File | Role |
|------|------|
| `wander Watch App/wanderApp.swift` | `@main` app entry |
| `wander Watch App/ContentView.swift` | The single press-and-hold Cast button + status |
| `wander Watch App/WandCaster.swift`  | CoreMotion capture + `/sensor/spell` POST |
