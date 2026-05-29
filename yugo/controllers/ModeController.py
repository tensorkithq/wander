"""The body's mode state machine — the single active mode every behavior module
plugs into.

Owns ONE active mode and serializes transitions: on a switch it runs the previous
mode's ``exit`` hook (tear down its loops) before the next mode's ``enter`` hook
(start its loops). Per-mode behavior (vision servoing, wand hashing, breathing,
voice-nav) lives in separate modules that ``register()`` their hooks here — this
controller owns only the lifecycle, never locomotion (motion always flows through
the clamped/deadman ``MotionController``).
"""

from __future__ import annotations

import threading
from typing import Callable, Optional

# The demo-arc modes, plus `creature` as the idle/default. POST /mode validates
# against this set (a Literal in the schema -> 422 on anything else).
MODES: tuple[str, ...] = ("creature", "personal", "friend", "find", "wand", "meditation")
DEFAULT_MODE = "creature"

Hook = Callable[[], None]


class ModeController:
    """Single source of truth for the active mode. Stateless w.r.t. the dog —
    a mode switch never publishes velocity."""

    def __init__(self, default: str = DEFAULT_MODE) -> None:
        # RLock: an enter/exit hook may itself read `.mode` while we hold the lock.
        self._lock = threading.RLock()
        self._mode = default
        self._handlers: dict[str, dict[str, Optional[Hook]]] = {}
        # Optional subject for the active mode (e.g. find/friend target person),
        # set via POST /mode {target}. Read by the mode loops as `mode_ctrl.target`.
        self.target: Optional[str] = None

    @property
    def mode(self) -> str:
        return self._mode

    def register(
        self, mode: str, *, enter: Optional[Hook] = None, exit: Optional[Hook] = None
    ) -> None:
        """A per-mode module registers its lifecycle hooks (run on enter/exit)."""
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        self._handlers[mode] = {"enter": enter, "exit": exit}

    def set_mode(self, mode: str) -> str:
        """Switch modes: ``exit(previous)`` -> set -> ``enter(next)``.

        Serialized (the lock spans the whole transition, so two switches never
        overlap); switching to the current mode is an idempotent no-op; a failing
        hook is swallowed so a mode switch can never crash the body.
        """
        if mode not in MODES:
            raise ValueError(f"unknown mode {mode!r}")
        with self._lock:
            if mode == self._mode:
                return self._mode
            self._run(self._mode, "exit")  # tear down the old mode's loops first
            self._mode = mode
            self._run(mode, "enter")  # then start the new mode's loops
            return self._mode

    def _run(self, mode: str, phase: str) -> None:
        hook = (self._handlers.get(mode) or {}).get(phase)
        if hook is None:
            return
        try:
            hook()
        except Exception:
            # Best-effort: loops/LED/Realtime swaps must not crash the switch;
            # the reflex/deadman layer keeps the body safe regardless.
            pass
