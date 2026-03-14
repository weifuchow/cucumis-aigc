#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import secrets
import shutil
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "templates" / "project"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a workspace project.")
    parser.add_argument("--project-name", default=None, help="Project directory name.")
    parser.add_argument(
        "--project-prefix",
        default="proj",
        help="Prefix used when auto-generating project id.",
    )
    parser.add_argument(
        "--projects-dir",
        default=str(REPO_ROOT / "projects"),
        help="Directory that holds initialized projects.",
    )
    return parser.parse_args()


def generate_project_id(prefix: str) -> str:
    now = dt.datetime.now(dt.timezone.utc)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(3)
    clean_prefix = prefix.strip().lower() or "proj"
    return f"{clean_prefix}-{timestamp}-{suffix}"


def write_project_metadata(project_dir: pathlib.Path, project_id: str) -> None:
    plan_path = project_dir / "orchestration" / "plan.json"
    if not plan_path.is_file():
        return

    payload = json.loads(plan_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return
    metadata = payload.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}
    metadata["project_id"] = project_id
    metadata["created_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    payload["metadata"] = metadata
    plan_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    projects_dir = pathlib.Path(args.projects_dir).resolve()
    project_id = args.project_name or generate_project_id(args.project_prefix)
    project_dir = projects_dir / project_id

    if not TEMPLATE_DIR.exists():
        print(f"template directory not found: {TEMPLATE_DIR}", file=sys.stderr)
        return 1
    if project_dir.exists():
        print(f"project already exists: {project_dir}", file=sys.stderr)
        return 1

    projects_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE_DIR, project_dir)
    write_project_metadata(project_dir, project_id)
    print(project_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
