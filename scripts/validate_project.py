#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys


REQUIRED_FILES = [
    pathlib.Path("README.md"),
    pathlib.Path("request.md"),
    pathlib.Path("events/events.jsonl"),
    pathlib.Path("orchestration/state.json"),
    pathlib.Path("orchestration/plan.json"),
    pathlib.Path("orchestration/decisions.jsonl"),
    pathlib.Path("input/input.json"),
]

REQUIRED_DIRS = [
    pathlib.Path("script"),
    pathlib.Path("storyboard"),
    pathlib.Path("timeline"),
    pathlib.Path("assets"),
    pathlib.Path("outputs"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a workspace project structure.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    missing = []
    for path in REQUIRED_FILES:
        if not (project_dir / path).is_file():
            missing.append(str(path))
    for path in REQUIRED_DIRS:
        if not (project_dir / path).is_dir():
            missing.append(str(path))

    input_path = project_dir / "input" / "input.json"
    if input_path.is_file():
        try:
            json.loads(input_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"invalid json in {input_path}: {exc}", file=sys.stderr)
            return 1

    if missing:
        print("missing required paths:", file=sys.stderr)
        for path in missing:
            print(f"- {path}", file=sys.stderr)
        return 1

    print(f"valid project: {project_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
