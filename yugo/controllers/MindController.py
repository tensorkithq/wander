"""Client for the Yugo **mind** (`expressmind`) — the cloud inference server the
body delegates vision + STT to (`settings.mind.base_url`,
https://openbeam.tensorkit.net by default).

Sync `httpx` (the vision/voice loops run in background threads). The body
base64-encodes a camera frame (from `FrameSource`) and POSTs it; the mind returns
a mood / find-commands / transcript. Live contract: `<base_url>/openapi.json`.
"""

from __future__ import annotations

from typing import Optional

import httpx


class MindClient:
    """Thin wrapper over the expressmind HTTP API. Methods return the parsed
    `result` (vision) or full body (STT); raise on transport/HTTP errors so the
    caller can degrade (hold/scan, keep the body safe)."""

    def __init__(self, base_url: str, timeout: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    # --- vision: POST /infer/vision (oneOf by task) --------------------------

    def vision(
        self, task: str, image_b64: str, target: Optional[str] = None, mime: str = "image/jpeg"
    ) -> dict:
        """One GPT-4o vision call. Returns the envelope `{task, model, latencyMs, result}`."""
        body: dict = {"task": task, "image": {"base64": image_b64, "mime": mime}}
        if target is not None:
            body["target"] = target
        return self._post("/infer/vision", json=body)

    def vision_personal(self, image_b64: str) -> dict:
        """`result` = `{facePresent, mood, confidence}` (personal/emotional mirror)."""
        return self.vision("personal", image_b64)["result"]

    def vision_find(self, image_b64: str, target: str) -> dict:
        """`result` = `{targetVisible, location{x,y}, decision, commands:[{action,steps}]}`."""
        return self.vision("find", image_b64, target)["result"]

    def vision_friend(self, image_b64: str, target: str) -> dict:
        """`result` = `{targetVisible, confidence, location{x,y}}`."""
        return self.vision("friend", image_b64, target)["result"]

    def find_friend(self, reference_b64: str, scene_b64: str, target: Optional[str] = None) -> dict:
        """Locate a known person by reference photo -> `{targetVisible, confidence, cell{row,col}}`."""
        body: dict = {
            "reference": {"base64": reference_b64},
            "scene": {"base64": scene_b64},
        }
        if target is not None:
            body["target"] = target
        return self._post("/infer/find-friend", json=body)["result"]

    # --- STT: POST /infer/stt/{whisper,deepgram} (multipart) -----------------

    def stt(
        self, audio: bytes, filename: str = "audio.wav", provider: str = "whisper",
        language: Optional[str] = None,
    ) -> dict:
        """Transcribe audio -> `{provider, model, transcript, ...}`."""
        data = {"language": language} if language else None
        files = {"audio": (filename, audio)}
        return self._post(f"/infer/stt/{provider}", files=files, data=data)

    def health(self) -> bool:
        try:
            with httpx.Client(base_url=self._base, timeout=5.0) as c:
                return c.get("/").status_code == 200
        except Exception:
            return False

    def _post(self, path: str, json=None, files=None, data=None) -> dict:
        with httpx.Client(base_url=self._base, timeout=self._timeout) as c:
            r = c.post(path, json=json, files=files, data=data)
            r.raise_for_status()
            return r.json()
