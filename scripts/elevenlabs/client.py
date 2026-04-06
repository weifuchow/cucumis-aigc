from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"


@dataclass
class ElevenLabsConfig:
    api_key: str
    base_url: str = ELEVENLABS_BASE_URL
    # Default voice ID — Multilingual v2, natural Chinese + English
    default_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # "Rachel" — clear, neutral


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


def load_elevenlabs_config(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
) -> ElevenLabsConfig:
    repo_root = Path(__file__).resolve().parents[2]
    values = dict(_read_dotenv(env_path or repo_root / ".env"))
    values.update(os.environ)
    if env:
        values.update(env)

    return ElevenLabsConfig(
        api_key=values.get("ELEVENLABS_API_KEY", ""),
        base_url=values.get("ELEVENLABS_BASE_URL", ELEVENLABS_BASE_URL),
        default_voice_id=values.get("ELEVENLABS_VOICE_ID", "21m00Tcm4TlvDq8ikWAM"),
    )


def request_json(
    config: ElevenLabsConfig,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    """JSON request — used for non-binary endpoints (e.g. voices list)."""
    url = f"{config.base_url}{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {
        "xi-api-key": config.api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"[elevenlabs] HTTP {exc.code} {path}: {body}") from exc


def request_binary(
    config: ElevenLabsConfig,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 180,
) -> bytes:
    """Binary request — used for TTS audio download."""
    url = f"{config.base_url}{path}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    headers = {
        "xi-api-key": config.api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"[elevenlabs] HTTP {exc.code} {path}: {body}") from exc
