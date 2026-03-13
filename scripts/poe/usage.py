from __future__ import annotations

import datetime as dt
import json
from pathlib import Path


def write_usage_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_cost_event(project_dir: Path, payload: dict) -> None:
    costs_path = project_dir / "costs" / "poe-usage.jsonl"
    costs_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        **payload,
    }
    with costs_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")
