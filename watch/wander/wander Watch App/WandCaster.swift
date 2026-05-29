import Foundation
import Combine
import CoreMotion

/// Captures a device-motion gesture on the watch and casts it as a spell.
///
/// Press-and-hold the button -> `startCast()` streams CoreMotion device-motion
/// (user-acceleration + rotation-rate) at `sampleHz` into two parallel traces.
/// Release -> `endCast()` POSTs the traces to the body API's `/sensor/spell`,
/// which hashes them DETERMINISTICALLY into a robot trick (the watch path in
/// `yugo/controllers/SensorController.py::spell_for_motion`). Units don't matter
/// to the hash — only gesture shape — so raw g / rad/s go straight over the wire.
///
/// Sample buffering lives in `SampleBuffer` (a lock-guarded, non-MainActor type)
/// so the 50 Hz CoreMotion handler can append from its background queue without
/// hopping the actor; only @Published UI state is updated on the MainActor.
@MainActor
final class WandCaster: ObservableObject {
    enum Phase: Equatable {
        case idle
        case casting
        case sending
        case result(String)
        case failed(String)
    }

    @Published private(set) var phase: Phase = .idle
    @Published private(set) var sampleCount = 0

    // Hardcoded body API (ngrok tunnel to the Yugo body).
    private let apiBase = "https://willette-multicapitate-limnologically.ngrok-free.dev"
    private let sampleHz: Double = 50
    private let minSamples = 4

    private let motion = CMMotionManager()
    private let buffer = SampleBuffer(maxSamples: 400)   // ~8 s cap, matches the server bound
    private let queue: OperationQueue = {
        let q = OperationQueue()
        q.maxConcurrentOperationCount = 1   // serial: keeps sample timestamps monotonic
        q.name = "wand.motion"
        return q
    }()

    /// Begin recording. Safe to call repeatedly; ignores re-entry while casting.
    func startCast() {
        guard motion.isDeviceMotionAvailable else { phase = .failed("No motion sensor"); return }
        if phase == .casting { return }
        buffer.reset()
        sampleCount = 0
        phase = .casting
        motion.deviceMotionUpdateInterval = 1.0 / sampleHz
        motion.startDeviceMotionUpdates(to: queue) { [weak self, buffer] dm, _ in
            guard let dm else { return }
            if let n = buffer.append(dm) {
                Task { @MainActor [weak self] in self?.sampleCount = n }
            }
        }
    }

    /// Stop recording and cast. Snapshots on the motion queue so any in-flight
    /// append finishes first, then POSTs.
    func endCast() {
        motion.stopDeviceMotionUpdates()
        queue.addOperation { [weak self, buffer] in
            let snap = buffer.snapshot()
            Task { @MainActor [weak self] in self?.finish(accel: snap.accel, gyro: snap.gyro) }
        }
    }

    private func finish(accel: [[Double]], gyro: [[Double]]) {
        guard accel.count >= minSamples else { phase = .failed("Too short — flick longer"); return }
        phase = .sending
        Task { await cast(accel: accel, gyro: gyro) }
    }

    private func cast(accel: [[Double]], gyro: [[Double]]) async {
        guard let url = URL(string: apiBase + "/sensor/spell") else { phase = .failed("Bad URL"); return }
        let body: [String: Any] = [
            "source": "watch-wand",
            "sample_hz": sampleHz,
            "accel": accel,
            "gyro": gyro,
        ]
        guard let data = try? JSONSerialization.data(withJSONObject: body) else {
            phase = .failed("Encode failed"); return
        }

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.setValue("true", forHTTPHeaderField: "ngrok-skip-browser-warning")
        req.httpBody = data
        req.timeoutInterval = 15

        do {
            let (respData, _) = try await URLSession.shared.data(for: req)
            guard
                let obj = try? JSONSerialization.jsonObject(with: respData) as? [String: Any],
                let matched = obj["matched"] as? [String: Any],
                let move = matched["move"] as? String
            else { phase = .failed("Bad response"); return }
            let fired = (obj["fired"] as? Bool) ?? false
            let dropped = (obj["dropped"] as? Bool) ?? false
            phase = .result(dropped ? "· busy ·" : (fired ? "✨ \(move)" : "\(move) · offline"))
        } catch {
            phase = .failed(error.localizedDescription)
        }
    }
}

/// Thread-safe sample store, deliberately OUTSIDE the MainActor so the 50 Hz
/// CoreMotion handler can append from its background queue lock-free of the actor.
private final class SampleBuffer: @unchecked Sendable {
    private let lock = NSLock()
    private let maxSamples: Int
    private var accel: [[Double]] = []
    private var gyro: [[Double]] = []
    private var t0: TimeInterval?

    init(maxSamples: Int) { self.maxSamples = maxSamples }

    func reset() {
        lock.lock(); defer { lock.unlock() }
        accel.removeAll(keepingCapacity: true)
        gyro.removeAll(keepingCapacity: true)
        t0 = nil
    }

    /// Append one sample as [t_ms, x, y, z] for each channel. Returns the new
    /// count, or nil once capped at `maxSamples`.
    func append(_ dm: CMDeviceMotion) -> Int? {
        lock.lock(); defer { lock.unlock() }
        if t0 == nil { t0 = dm.timestamp }
        guard accel.count < maxSamples else { return nil }
        let tms = (dm.timestamp - (t0 ?? dm.timestamp)) * 1000
        let ua = dm.userAcceleration   // gravity removed, in g
        let rr = dm.rotationRate       // rad/s
        accel.append([tms, ua.x, ua.y, ua.z])
        gyro.append([tms, rr.x, rr.y, rr.z])
        return accel.count
    }

    func snapshot() -> (accel: [[Double]], gyro: [[Double]]) {
        lock.lock(); defer { lock.unlock() }
        return (accel, gyro)
    }
}
