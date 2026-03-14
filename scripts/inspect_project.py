#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect workspace project state.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    state_path = project_dir / "orchestration" / "state.json"
    state = {
        "current_stage": None,
        "completed_stages": [],
        "skipped_stages": [],
        "last_failed_stage": None,
        "next_stage": None,
    }
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))

    payload = {
        "project": str(project_dir),
        "current_stage": state.get("current_stage"),
        "completed_stages": state.get("completed_stages", []),
        "skipped_stages": state.get("skipped_stages", []),
        "last_failed_stage": state.get("last_failed_stage"),
        "next_stage": state.get("next_stage"),
        "artifacts": {
            "creative_brief_exists": (project_dir / "brief" / "creative-brief.md").is_file(),
            "input_exists": (project_dir / "input" / "input.json").is_file(),
            "script_exists": (project_dir / "script" / "script.json").is_file(),
            "storyboard_exists": (project_dir / "storyboard" / "storyboard.json").is_file(),
            "keyframes_exists": (project_dir / "keyframes" / "keyframes.json").is_file(),
            "prompts_exists": (project_dir / "prompts" / "prompts.json").is_file(),
            "asset_manifest_exists": (project_dir / "assets" / "manifest.json").is_file(),
            "image_requests_exists": (project_dir / "assets" / "image-requests.json").is_file(),
            "image_usage_exists": (project_dir / "assets" / "image-usage.json").is_file(),
            "subtitles_exists": (project_dir / "subtitles" / "subtitles.json").is_file(),
            "clips_exists": (project_dir / "video" / "clips.json").is_file(),
            "timeline_exists": (project_dir / "timeline" / "timeline.json").is_file(),
            "render_plan_exists": (project_dir / "outputs" / "render-plan.json").is_file(),
        },
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
