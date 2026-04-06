from __future__ import annotations

import json
import os
import time
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


@dataclass
class GoogleConfig:
    api_key: str
    base_url: str = GOOGLE_AI_BASE_URL
    # Default model IDs — can be overridden via env vars
    image_model: str = "gemini-3.1-flash-image-preview"
    video_model: str = "veo-3.1-lite-generate-preview"
    tts_model: str = "gemini-2.5-flash-preview-tts"


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip("'").strip('"')
    return values


def load_google_config(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
) -> GoogleConfig:
    repo_root = Path(__file__).resolve().parents[2]
    values = dict(_read_dotenv(env_path or repo_root / ".env"))
    values.update(os.environ)
    if env:
        values.update(env)

    return GoogleConfig(
        api_key=values.get("GOOGLE_AI_API_KEY", ""),
        base_url=values.get("GOOGLE_AI_BASE_URL", GOOGLE_AI_BASE_URL),
        image_model=values.get("GOOGLE_IMAGE_MODEL", "gemini-3.1-flash-image-preview"),
        video_model=values.get("GOOGLE_VIDEO_MODEL", "veo-3.1-lite-generate-preview"),
        tts_model=values.get("GOOGLE_TTS_MODEL", "gemini-2.5-flash-preview-tts"),
    )


def request_json(
    config: GoogleConfig,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """Make a JSON request to the Google AI API."""
    url = f"{config.base_url}{path}?key={config.api_key}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {"Content-Type": "application/json"}
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"[google] HTTP {exc.code} {path}: {body}") from exc


def poll_operation(
    config: GoogleConfig,
    operation_name: str,
    max_wait: int = 300,
    interval: int = 5,
) -> dict[str, Any]:
    """Poll a long-running operation until done or timeout."""
    elapsed = 0
    while elapsed < max_wait:
        # operation_name is already a full path like "models/veo-.../operations/abc"
        result = request_json(config, "GET", f"/{operation_name}")
        if result.get("done"):
            return result
        print(f"[google] operation pending ({elapsed}s elapsed)…", flush=True)
        time.sleep(interval)
        elapsed += interval
    raise TimeoutError(
        f"[google] operation {operation_name!r} did not complete within {max_wait}s"
    )
