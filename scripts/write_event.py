#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append an event to a project event log.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--event-type", required=True, help="Event type name.")
    parser.add_argument("--payload", required=True, help="JSON object payload.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    events_path = project_dir / "events" / "events.jsonl"

    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(args.payload)
    except json.JSONDecodeError as exc:
        print(f"invalid payload json: {exc}", file=sys.stderr)
        return 1

    if not isinstance(payload, dict):
        print("payload must be a JSON object", file=sys.stderr)
        return 1

    events_path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "event_type": args.event_type,
        "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
        "payload": payload,
    }
    with events_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(events_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
