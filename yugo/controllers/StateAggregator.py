"""Assembles the `/ws/state` StateFrame — the aggregated telemetry the app's
"aura" reads. Merges body-local state (connection, active mode, last-known mood)
with robot-sourced fields (battery) when the dog is connected.

Stateless and best-effort: every accessor is guarded so a transient error (DB
hiccup, missing dog field) degrades to an omitted field rather than crashing the
push loop. Offline (`YUGO_NO_ROBOT=1`) it still produces a frame — `connected`
is false and robot-sourced fields (battery/pose/imu) are simply absent, while
mode and the last-known mood keep flowing (PRD success criterion).
"""

from __future__ import annotations

from typing import Optional


class StateAggregator:
    def __init__(self, motion, mode_ctrl, session_factory, conn) -> None:
        self._motion = motion
        self._mode_ctrl = mode_ctrl
        self._SessionLocal = session_factory
        self._conn = conn

    @property
    def connected(self) -> bool:
        c = self._conn
        ready = getattr(c, "connection_ready", None)
        return c is not None and ready is not None and ready.is_set()

    def _mood(self) -> Optional[dict]:
        """Last-known mood as a `MoodState` {scalar, label, color}, or None."""
        try:
            from yugo.controllers.MoodController import current_mood

            db = self._SessionLocal()
            try:
                m = current_mood(db)
            finally:
                db.close()
            return {
                "scalar": float(m["scalar"]),
                "label": m["state"],
                "color": m["color"],
            }
        except Exception:
            return None

    def _battery(self) -> Optional[float]:
        """Battery fraction 0..1 from the dog's lowstate, or None (offline / unknown).

        The lowstate shape is dimos/firmware-specific, so this probes a couple of
        common shapes and bails to None on anything unexpected — the field is
        simply omitted rather than guessed.
        """
        if not self.connected:
            return None
        try:
            ls = getattr(self._conn, "lowstate_stream", None)
            ls = ls() if callable(ls) else ls
            soc = None
            if isinstance(ls, dict):
                bms = ls.get("bms_state") or ls.get("bms") or {}
                soc = (bms.get("soc") if isinstance(bms, dict) else None) or ls.get("soc")
            else:
                bms = getattr(ls, "bms_state", None)
                soc = getattr(bms, "soc", None) if bms is not None else getattr(ls, "soc", None)
            if soc is None:
                return None
            return max(0.0, min(1.0, float(soc) / 100.0))
        except Exception:
            return None

    def frame(self) -> dict:
        """One StateFrame. Always carries `connected` + `mode`; adds `mood` and
        `battery` when available. Every field is optional per the schema."""
        out: dict = {
            "connected": self.connected,
            "mode": self._mode_ctrl.mode if self._mode_ctrl is not None else "creature",
        }
        mood = self._mood()
        if mood is not None:
            out["mood"] = mood
        battery = self._battery()
        if battery is not None:
            out["battery"] = battery
        return out
