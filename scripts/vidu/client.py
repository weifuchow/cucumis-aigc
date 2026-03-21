from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time
from typing import Any
import urllib.error
import urllib.parse
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[2]
VIDU_BASE_URL = "https://api.vidu.cn/ent/v2"

# Task states that mean "still running"
_PENDING_STATES = {"created", "queueing", "processing"}


@dataclass(frozen=True)
class ViduConfig:
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


def load_vidu_config(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
) -> ViduConfig:
    env_values = dict(_read_dotenv(env_path or REPO_ROOT / ".env"))
    env_values.update(env or os.environ)
    return ViduConfig(
        api_key=env_values.get("VIDU_API_KEY", ""),
        base_url=env_values.get("VIDU_BASE_URL", VIDU_BASE_URL),
    )


def request_json(
    config: ViduConfig,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    url = f"{config.base_url.rstrip('/')}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if config.api_key:
        # Vidu uses "Token <key>" not "Bearer <key>"
        headers["Authorization"] = f"Token {config.api_key}"
    request = urllib.request.Request(url, data=body, headers=headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(f"[vidu] HTTP {e.code} from {url}: {error_body[:500]}", flush=True)
        raise


def poll_task(
    config: ViduConfig,
    task_id: str,
    *,
    interval: float = 5.0,
    max_wait: float = 600.0,
    timeout: int = 30,
) -> dict[str, Any]:
    """Poll GET /query-task?task_id=<id> until state is success or failed.

    Returns the final task dict on success.
    Raises RuntimeError on failed state, TimeoutError if max_wait exceeded.
    """
    deadline = time.monotonic() + max_wait
    while True:
        result = request_json(
            config,
            "GET",
            "/query-task",
            params={"task_id": task_id},
            timeout=timeout,
        )
        state = result.get("state", "")
        if state == "success":
            return result
        if state == "failed":
            raise RuntimeError(f"[vidu] task {task_id} failed: {result}")
        if state not in _PENDING_STATES:
            raise RuntimeError(f"[vidu] task {task_id} unexpected state: {state!r}")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError(
                f"[vidu] task {task_id} timed out after {max_wait}s (last state: {state})"
            )
        sleep_secs = min(interval, remaining)
        print(f"[vidu] task {task_id} state={state}, polling in {sleep_secs:.0f}s ...", flush=True)
        time.sleep(sleep_secs)
