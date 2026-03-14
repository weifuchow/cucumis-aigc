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
    pathlib.Path("audio/voiceover.json"),
    pathlib.Path("audio/bgm-selection.json"),
    pathlib.Path("audio/beat-grid.json"),
    pathlib.Path("audio/tts-response.json"),
    pathlib.Path("audio/usage.json"),
    pathlib.Path("keyframes/keyframes.json"),
    pathlib.Path("prompts/prompts.json"),
    pathlib.Path("subtitles/subtitles.json"),
    pathlib.Path("video/clips.json"),
    pathlib.Path("video/requests.json"),
    pathlib.Path("video/usage.json"),
    pathlib.Path("timeline/global-timeline.json"),
    pathlib.Path("timeline/timeline.json"),
    pathlib.Path("assets/manifest.json"),
    pathlib.Path("assets/image-requests.json"),
    pathlib.Path("assets/image-usage.json"),
    pathlib.Path("outputs/render-plan.json"),
    pathlib.Path("review/review-report.json"),
    pathlib.Path("review/observer-summary.md"),
    pathlib.Path("costs/poe-usage.jsonl"),
]

REQUIRED_DIRS = [
    pathlib.Path("script"),
    pathlib.Path("storyboard"),
    pathlib.Path("video"),
    pathlib.Path("timeline"),
    pathlib.Path("keyframes"),
    pathlib.Path("prompts"),
    pathlib.Path("subtitles"),
    pathlib.Path("audio"),
    pathlib.Path("review"),
    pathlib.Path("costs"),
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

    json_paths = [
        project_dir / "input" / "input.json",
        project_dir / "audio" / "tts-response.json",
        project_dir / "audio" / "usage.json",
        project_dir / "keyframes" / "keyframes.json",
        project_dir / "prompts" / "prompts.json",
        project_dir / "subtitles" / "subtitles.json",
        project_dir / "video" / "clips.json",
        project_dir / "video" / "requests.json",
        project_dir / "video" / "usage.json",
        project_dir / "timeline" / "global-timeline.json",
        project_dir / "timeline" / "timeline.json",
        project_dir / "assets" / "manifest.json",
        project_dir / "assets" / "image-requests.json",
        project_dir / "assets" / "image-usage.json",
        project_dir / "outputs" / "render-plan.json",
        project_dir / "review" / "review-report.json",
    ]
    for input_path in json_paths:
        if not input_path.is_file():
            continue
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
