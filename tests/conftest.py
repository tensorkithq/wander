"""Test harness: boot the ACTUAL Yugo API under uvicorn and hit it over real
HTTP. No mocking — the suite drives the live server and validates behaviour from
the server's HTTP responses.

The dog itself is hardware we can't attach in CI, so the server runs in offline
mode (YUGO_NO_ROBOT=1): the local reflex layer (nav, deadman, /state, /cmd_vel,
/stop) is fully live and self-validating; robot-bound expressive actions report
503, which is itself the correct, asserted behaviour offline.
"""

from __future__ import annotations

import os
import socket
import threading
import time

# Must be set before importing yugo.config (settings are read at import time).
os.environ["YUGO_NO_ROBOT"] = "1"
os.environ.setdefault("YUGO_MOTION_TIMEOUT", "0.3")  # short deadman window for fast tests

import httpx
import pytest
import uvicorn


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def base_url():
    from yugo.main import app

    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    url = f"http://127.0.0.1:{port}"
    # Wait for the server (and lifespan startup) to come up.
    deadline = time.time() + 20
    while time.time() < deadline:
        try:
            httpx.get(url + "/healthz", timeout=1.0)
            break
        except Exception:
            time.sleep(0.1)
    else:
        raise RuntimeError("test server did not start")

    yield url

    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture
def client(base_url):
    with httpx.Client(base_url=base_url, timeout=5.0) as c:
        yield c


@pytest.fixture
def deadman_window(client) -> float:
    """The server's actual deadman window (so timing assertions track config)."""
    return client.get("/state").json()["deadman_window"]
