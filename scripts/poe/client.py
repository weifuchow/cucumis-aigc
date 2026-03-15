from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class PoeConfig:
    api_key: str
    base_url: str


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def load_poe_config(env: dict[str, str] | None = None, env_path: Path | None = None) -> PoeConfig:
    env_values = dict(_read_dotenv(env_path or REPO_ROOT / ".env"))
    env_values.update(env or os.environ)
    return PoeConfig(
        api_key=env_values.get("POE_API_KEY", ""),
        base_url=env_values.get("POE_BASE_URL", "https://api.poe.com/v1"),
    )


def request_json(
    config: PoeConfig,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    extra_headers: dict[str, str] | None = None,
    timeout: int = 120,
) -> dict[str, Any]:
    url = f"{config.base_url.rstrip('/')}/{path.lstrip('/')}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    if extra_headers:
        headers.update(extra_headers)

    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[poe] HTTP {e.code} from {url}: {error_body[:500]}", flush=True)
        raise
