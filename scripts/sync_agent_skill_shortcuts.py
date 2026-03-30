#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
import sys


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE_SKILLS_DIR = REPO_ROOT / "skills"
CLAUDE_LINK = REPO_ROOT / ".claude" / "skills"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create shortcut links so Claude Agent SDK and Codex can discover repo skills.",
    )
    parser.add_argument(
        "--codex-root",
        default=str(pathlib.Path.home() / ".agents" / "skills"),
        help="Codex skill discovery directory. Defaults to ~/.agents/skills",
    )
    parser.add_argument(
        "--codex-name",
        default=REPO_ROOT.name,
        help="Symlink name to create under the Codex skill root.",
    )
    parser.add_argument(
        "--skip-codex",
        action="store_true",
        help="Only create the repo-local Claude link.",
    )
    return parser.parse_args()


def ensure_symlink(link_path: pathlib.Path, target_path: pathlib.Path) -> None:
    link_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_target = target_path.resolve()

    if link_path.is_symlink():
        current_target = link_path.resolve()
        if current_target == resolved_target:
            return
        link_path.unlink()
    elif link_path.exists():
        raise RuntimeError(f"refusing to replace non-symlink path: {link_path}")

    relative_target = os.path.relpath(resolved_target, start=link_path.parent.resolve())
    link_path.symlink_to(relative_target)


def main() -> int:
    args = parse_args()

    if not SOURCE_SKILLS_DIR.is_dir():
        print(f"skills source directory not found: {SOURCE_SKILLS_DIR}", file=sys.stderr)
        return 1

    ensure_symlink(CLAUDE_LINK, SOURCE_SKILLS_DIR)
    print(f"claude -> {CLAUDE_LINK} -> {SOURCE_SKILLS_DIR}")

    if not args.skip_codex:
        codex_root = pathlib.Path(args.codex_root).expanduser()
        codex_link = codex_root / args.codex_name
        codex_root.mkdir(parents=True, exist_ok=True)
        ensure_symlink(codex_link, SOURCE_SKILLS_DIR)
        print(f"codex -> {codex_link} -> {SOURCE_SKILLS_DIR}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
