"""The wand hash engine + spell firing.

A gesture trace is turned into a robot trick DETERMINISTICALLY:
normalize -> feature-extract -> stable hash -> bucket -> fixed trick table.

ONE engine, TWO client channels (the wand runs on both iOS phone and watchOS):
  - PHONE — a magnetometer trace (`spell_for_trace`). The original engine,
    namespaced "v{SPELL_VERSION}"; kept byte-for-byte so phone spells never
    remap. The watch has no usable raw magnetometer, hence the second channel.
  - WATCH — a device-motion trace (`spell_for_motion`): user-acceleration
    (path) is primary, rotation-rate (twist) the optional secondary; their
    features are concatenated then hashed under a separate "m{MOTION_SPELL_VERSION}"
    namespace so the two channels can version independently and never collide.

Body-only, pure math: no AI, no clock, no randomness, no network. The same
trace ALWAYS yields the same bucket/move, across processes and restarts — which
is why the hash is `hashlib.sha256` over quantized integer features, NEVER
Python's salted builtin `hash()`. The shared normalize/feature pipeline makes
both channels rotation/scale/drift-robust, so units (µT vs g vs rad/s) don't
matter — only gesture shape does.

See PRD `prd/module-wand-hash.md` and `prd/02-yugo-app.md` §3.
"""

from __future__ import annotations

import enum
import hashlib
import threading
import time
from typing import List, Optional, Sequence

from unitree_webrtc_connect.constants import SPORT_CMD

from yugo.config import settings
from yugo.controllers import RobotController

# --- Versioned, FIXED constants. Changing ANY of these changes every spell. ---

SPELL_VERSION = 1  # phone magnetometer engine — FROZEN; bumping remaps every phone spell.
MOTION_SPELL_VERSION = 1  # watch device-motion engine (accel + gyro); versions independently.
RESAMPLE_N = 64  # fixed trace length after time-uniform resampling
SCALE_EPS = 1e-6  # guard against divide-by-zero on a still trace

# Fixed bucket -> SPORT_CMD trick table. Safe expressive moves only — NO flips,
# NO handstand, and NO WiggleHips (removed as broken). BUCKET_COUNT is
# len(TRICK_TABLE); every bucket maps to a move, so a valid trace always casts.
TRICK_TABLE: List[str] = [
    "Hello",
    "Scrape",
    "Stretch",
    "FingerHeart",
    "Dance1",
    "Sit",
    "Dance2",
    "MoonWalk",
    "Pose",
    "Content",
    "RiseSit",
    # repeats below weight the more expressive / "fun" moves a bit higher
    "Dance1",
    "FingerHeart",
    "Dance2",
    "Hello",
    "Stretch",
    "Pose",
    "MoonWalk",
]
BUCKET_COUNT = len(TRICK_TABLE)

# Validate the table against SPORT_CMD at import time: an unknown move is a
# startup error (per R5), never a runtime surprise.
for _m in TRICK_TABLE:
    if _m not in SPORT_CMD:
        raise RuntimeError(f"spell trick table references unknown move {_m!r}")


# --- Normalization -----------------------------------------------------------

def _resample(trace: Sequence[Sequence[float]], n: int = RESAMPLE_N) -> List[List[float]]:
    """Time-uniform resample to `n` samples of [x, y, z] using the per-sample
    t_ms timestamps — so cadence jitter and hold duration don't move features.

    Falls back to index-uniform spacing if timestamps are non-monotonic/degenerate.
    """
    ts = [float(s[0]) for s in trace]
    xyz = [[float(s[1]), float(s[2]), float(s[3])] for s in trace]
    m = len(xyz)
    if m == 1:
        return [xyz[0][:] for _ in range(n)]

    t0, t1 = ts[0], ts[-1]
    use_time = t1 > t0 and all(ts[i + 1] >= ts[i] for i in range(m - 1))

    out: List[List[float]] = []
    for k in range(n):
        if use_time:
            target = t0 + (t1 - t0) * k / (n - 1)
            j = 0
            while j < m - 2 and ts[j + 1] < target:
                j += 1
            span = ts[j + 1] - ts[j]
            frac = 0.0 if span <= 0 else (target - ts[j]) / span
        else:
            pos = (m - 1) * k / (n - 1)
            j = min(int(pos), m - 2)
            frac = pos - j
        out.append([xyz[j][a] + (xyz[j + 1][a] - xyz[j][a]) * frac for a in range(3)])
    return out


def _normalize(trace: Sequence[Sequence[float]]) -> List[List[float]]:
    """Resample, zero-mean each axis against the start reading (kills baseline
    drift / location dependence), then scale-normalize per axis so a big slow
    sweep and a small fast sweep of the same SHAPE hash alike."""
    res = _resample(trace)
    start = res[0][:]
    centered = [[s[a] - start[a] for a in range(3)] for s in res]
    # Per-axis scale = max abs deviation; keeps shape, drops magnitude.
    scale = [max((abs(s[a]) for s in centered), default=0.0) for a in range(3)]
    scale = [v if v > SCALE_EPS else 1.0 for v in scale]
    return [[s[a] / scale[a] for a in range(3)] for s in centered]


# --- Feature extraction (quantized, rotation/scale-robust) -------------------

def _features(norm: List[List[float]]) -> List[int]:
    """Compact QUANTIZED feature vector — same normalized trace -> same ints,
    on every machine, forever. Binned so small natural variation in one gesture
    lands in the same bins."""
    n = len(norm)
    feats: List[int] = []

    for a in range(3):
        col = [s[a] for s in norm]

        # Direction-change count: sign flips of the first difference (binned).
        flips = 0
        prev = 0
        for i in range(1, n):
            d = col[i] - col[i - 1]
            sign = 1 if d > 0.05 else (-1 if d < -0.05 else 0)
            if sign != 0 and prev != 0 and sign != prev:
                flips += 1
            if sign != 0:
                prev = sign
        feats.append(min(flips, 12))

        # Coarse start->end displacement direction (-1/0/+1).
        disp = col[-1] - col[0]
        feats.append(1 if disp > 0.25 else (-1 if disp < -0.25 else 0))

        # Spread: max - min, bucketed into 5 levels (shape amplitude class).
        spread = max(col) - min(col)
        feats.append(min(int(spread / 0.5), 4))

        # Coarse 4-segment shape signature: sign of each quarter's mean.
        seg = n // 4
        for q in range(4):
            lo, hi = q * seg, (q + 1) * seg if q < 3 else n
            mean = sum(col[lo:hi]) / max(hi - lo, 1)
            feats.append(1 if mean > 0.1 else (-1 if mean < -0.1 else 0))

    # Dominant axis (largest variance) — rotation-discriminating.
    var = [sum((s[a] - sum(c[a] for c in norm) / n) ** 2 for s in norm) for a in range(3)]
    feats.append(max(range(3), key=lambda a: var[a]))
    return feats


def _stable_bucket(feats: Sequence[int], tag: str) -> int:
    """Hash quantized features to a stable bucket with sha256 (NOT builtin
    hash(), which is salted per-process). `tag` namespaces the engine + version
    (e.g. "v1" magnetometer, "m1" motion) so the two channels never collide and
    each can version independently. Deterministic across restarts."""
    payload = f"{tag}:" + ",".join(str(int(f)) for f in feats)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % BUCKET_COUNT


def _bucket_to_move(bucket: int) -> dict:
    move = TRICK_TABLE[bucket]
    return {"bucket": bucket, "move": move, "api_id": SPORT_CMD[move]}


# --- Public engine -----------------------------------------------------------

def spell_for_trace(magnetometer: Sequence[Sequence[float]]) -> dict:
    """Pure: a PHONE magnetometer trace -> {"bucket", "move", "api_id"}.

    The original engine, hashed under "v{SPELL_VERSION}". Kept byte-for-byte so
    existing phone spells never remap. No state, no side effects.
    """
    feats = _features(_normalize(magnetometer))
    return _bucket_to_move(_stable_bucket(feats, f"v{SPELL_VERSION}"))


def spell_for_motion(
    accel: Sequence[Sequence[float]],
    gyro: Optional[Sequence[Sequence[float]]] = None,
) -> dict:
    """Pure: a WATCH device-motion trace -> {"bucket", "move", "api_id"}.

    `accel` (the gesture's path) is the primary channel; `gyro` (its twist) the
    optional secondary. Per-channel features are concatenated and hashed under
    "m{MOTION_SPELL_VERSION}" — a separate namespace from the magnetometer
    engine, so the two never collide. No state, no side effects.
    """
    feats: List[int] = list(_features(_normalize(accel)))
    if gyro:
        feats += _features(_normalize(gyro))
    return _bucket_to_move(_stable_bucket(feats, f"m{MOTION_SPELL_VERSION}"))


# --- Single-flight state machine ---------------------------------------------


class SensorPhase(str, enum.Enum):
    IDLE = "idle"
    CASTING = "casting"


class _SensorMachine:
    """Single-flight gate for the wand sensor namespace.

    A cast claims the gate for a HOLD window covering the trick's FULL execution
    (the BalanceStand settle + the move itself, ~`trick_suspend_s`), NOT just
    until the SPORT_MOD publish returns. While held — phase CASTING — every other
    sensor request (a second spell OR an ambient /sensor reading) is DROPPED
    ("piped to null"), so the next cast is only accepted once the current one has
    actually finished on the dog — no stacking, no mid-move interruption (e.g. a
    Pose cut short by the next cast).

    The hold is a monotonic DEADLINE, so it auto-releases when the move is done;
    an offline or failed cast (nothing will execute) releases it early via
    `end_cast`. Thread-safe: FastAPI runs these sync endpoints in a threadpool,
    so concurrent posts land on different threads and race here.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy_until = 0.0  # monotonic deadline; now < this => CASTING

    @property
    def phase(self) -> SensorPhase:
        with self._lock:
            return SensorPhase.CASTING if time.monotonic() < self._busy_until else SensorPhase.IDLE

    @property
    def busy(self) -> bool:
        with self._lock:
            return time.monotonic() < self._busy_until

    def begin_cast(self, hold_s: float) -> bool:
        """Atomically claim the gate for `hold_s` seconds. True = won it; False =
        a cast is still in flight, so drop this request. On success the deadline
        releases the gate on its own once the trick has executed — the caller only
        needs `end_cast` to free it EARLY (offline / failed cast)."""
        with self._lock:
            now = time.monotonic()
            if now < self._busy_until:
                return False
            self._busy_until = now + hold_s
            return True

    def end_cast(self) -> None:
        """Release the gate now — for a cast that won't actually execute (offline
        or errored), so it doesn't needlessly lock out the next one."""
        with self._lock:
            self._busy_until = 0.0


# Process-wide singleton: the wand is one physical robot, so one cast at a time.
machine = _SensorMachine()


def fire_spell(conn, trace) -> dict:
    """Match ALWAYS (even offline), then fire the trick over WebRTC only when the
    link is live. Returns {"matched": {...}, "fired": bool, "dropped": bool}.

    Single-flight: the match is cheap and always computed, but the FIRING is
    gated by `machine` — if a cast is already executing this one is dropped
    (`dropped:true`, nothing published) rather than queued. The gate is held for
    the trick's FULL execution (`trick_suspend_s`), so the next cast is only
    accepted once this one has actually finished — not just once it's published.

    Dispatch by client channel: a magnetometer trace is the phone (original
    engine, accel ignored as before); otherwise it's the watch's device-motion
    (accel + gyro). The watch can't supply a raw magnetometer, so its absence is
    the reliable discriminator and keeps the phone path 100% unchanged.

    `conn` may be None (offline) — then `fired` is False and nothing is published.
    Firing reuses RobotController.fire (the single trick path: SPORT_MOD publish
    + a BalanceStand precondition). We pass `ensure_balance=True` so EVERY spell
    settles into an upright stance first — a spell trace can resolve to any
    TRICK_TABLE move regardless of posture, and not every such move is listed in
    NEEDS_BALANCE, so this guarantees new spells won't fail from a bad posture.
    """
    if getattr(trace, "magnetometer", None):
        matched = spell_for_trace(trace.magnetometer)
    else:
        matched = spell_for_motion(trace.accel, getattr(trace, "gyro", None))

    # Hold the gate for the trick's full execution window (settle + move), so the
    # next cast is only accepted once this one has actually finished on the dog.
    if not machine.begin_cast(settings.motion.trick_suspend_s):
        return {"matched": matched, "fired": False, "dropped": True}
    try:
        fired = False
        if conn is not None and conn.connection_ready.is_set():
            RobotController.fire(conn, matched["move"], ensure_balance=True)
            fired = True
        if not fired:
            machine.end_cast()  # offline: nothing will execute — free the gate now
        return {"matched": matched, "fired": fired, "dropped": False}
    except Exception:
        machine.end_cast()  # failed cast won't execute — don't lock out the next
        raise
