"""Identity of the CONNECTED robot, keyed by its known IP (``settings.robot.ip``).

The WebRTC link doesn't expose the dog's serial/MAC, so we resolve them from the
LAN: serial via Unitree multicast discovery (sn↔ip), MAC via the host ARP table.
Both are best-effort (need the dog on the LAN) and cached once found.

BLE is a separate radio with no IP — the ``Go2_xxxxx`` BLE name can't be keyed by
IP; it only links via serial and needs ``bleak``. So it's not resolved here.
"""

from __future__ import annotations

import re
import subprocess
import threading
from typing import Optional

from yugo.config import settings

_MAC_RE = re.compile(r"(?:[0-9a-fA-F]{1,2}:){5}[0-9a-fA-F]{1,2}")
_lock = threading.Lock()
_cache: dict[str, dict] = {}  # ip -> {"serial": str, "mac": str}


def _arp_mac(ip: str) -> Optional[str]:
    """Best-effort MAC for `ip` from the host ARP table (`arp` exists on macOS + Linux)."""
    try:
        out = subprocess.run(
            ["arp", "-n", ip], capture_output=True, text=True, timeout=2
        ).stdout
    except Exception:
        return None
    m = _MAC_RE.search(out)
    if not m:
        return None
    return ":".join(p.zfill(2) for p in m.group(0).split(":")).upper()


def _serial_for_ip(ip: str) -> Optional[str]:
    """Match `ip` to a serial via Unitree multicast discovery (needs the LAN)."""
    try:
        from unitree_webrtc_connect.multicast_scanner import discover_ip_sn

        for sn, dip in discover_ip_sn(timeout=1.5).items():
            if dip == ip:
                return sn
    except Exception:
        pass
    return None


def connected_robot_info(conn) -> dict:
    """Identity of the one robot we're configured to talk to (by IP)."""
    ip = settings.robot.ip
    ready = getattr(conn, "connection_ready", None)
    connected = conn is not None and ready is not None and ready.is_set()

    with _lock:
        cached = dict(_cache.get(ip, {}))
    serial = cached.get("serial") or _serial_for_ip(ip)
    mac = cached.get("mac") or _arp_mac(ip)
    with _lock:
        entry = _cache.setdefault(ip, {})
        if serial:
            entry["serial"] = serial
        if mac:
            entry["mac"] = mac

    return {
        "source": "LAN",
        "name": settings.robot.name,
        "ip": ip,
        "mac": mac,
        "serial": serial,
        "connected": connected,
    }
