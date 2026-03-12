#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
import shutil
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE_DIR = REPO_ROOT / "templates" / "project"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a workspace project.")
    parser.add_argument("--project-name", required=True, help="Project directory name.")
    parser.add_argument(
        "--projects-dir",
        default=str(REPO_ROOT / "projects"),
        help="Directory that holds initialized projects.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    projects_dir = pathlib.Path(args.projects_dir).resolve()
    project_dir = projects_dir / args.project_name

    if not TEMPLATE_DIR.exists():
        print(f"template directory not found: {TEMPLATE_DIR}", file=sys.stderr)
        return 1
    if project_dir.exists():
        print(f"project already exists: {project_dir}", file=sys.stderr)
        return 1

    projects_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(TEMPLATE_DIR, project_dir)
    print(project_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
