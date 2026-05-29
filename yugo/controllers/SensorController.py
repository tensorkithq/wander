"""The wand hash engine + spell firing.

A phone magnetometer trace is turned into a robot trick DETERMINISTICALLY:
normalize -> feature-extract -> stable hash -> bucket -> fixed trick table.

Body-only, pure math: no AI, no clock, no randomness, no network. The same
trace ALWAYS yields the same bucket/move, across processes and restarts — which
is why the hash is `hashlib.sha256` over quantized integer features, NEVER
Python's salted builtin `hash()`.

See PRD `prd/module-wand-hash.md` and `prd/02-yugo-app.md` §3.
"""

from __future__ import annotations

import hashlib
from typing import List, Optional, Sequence

from unitree_webrtc_connect.constants import SPORT_CMD

from yugo.controllers import RobotController

# --- Versioned, FIXED constants. Changing ANY of these changes every spell. ---

SPELL_VERSION = 1
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


def _stable_bucket(feats: Sequence[int]) -> int:
    """Hash quantized features to a stable bucket with sha256 (NOT builtin
    hash(), which is salted per-process). Deterministic across restarts."""
    payload = f"v{SPELL_VERSION}:" + ",".join(str(int(f)) for f in feats)
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % BUCKET_COUNT


# --- Public engine -----------------------------------------------------------

def spell_for_trace(
    magnetometer: Sequence[Sequence[float]],
    accel: Optional[Sequence[Sequence[float]]] = None,
) -> dict:
    """Pure: trace -> {"bucket", "move", "api_id"}. No state, no side effects.

    `accel` is accepted for forward-compat but not yet fed into the hash, so the
    magnetometer trace alone fully determines the spell (kept simple + stable).
    """
    norm = _normalize(magnetometer)
    bucket = _stable_bucket(_features(norm))
    move = TRICK_TABLE[bucket]
    return {"bucket": bucket, "move": move, "api_id": SPORT_CMD[move]}


def fire_spell(conn, trace) -> dict:
    """Compute the match ALWAYS (even offline), then fire the trick over WebRTC
    only when the link is live. Returns {"matched": {...}, "fired": bool}.

    `conn` may be None (offline) — then `fired` is False and nothing is published.
    Firing reuses RobotController.fire (the single trick path: SPORT_MOD publish
    + a BalanceStand precondition). We pass `ensure_balance=True` so EVERY spell
    settles into an upright stance first — a spell trace can resolve to any
    TRICK_TABLE move regardless of posture, and not every such move is listed in
    NEEDS_BALANCE, so this guarantees new spells won't fail from a bad posture.
    """
    matched = spell_for_trace(trace.magnetometer, trace.accel)
    fired = False
    if conn is not None and conn.connection_ready.is_set():
        RobotController.fire(conn, matched["move"], ensure_balance=True)
        fired = True
    return {"matched": matched, "fired": fired}
