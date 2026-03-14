#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


BASELINE_REQUIRED_FILES = [
    pathlib.Path("README.md"),
    pathlib.Path("request.md"),
    pathlib.Path("events/events.jsonl"),
    pathlib.Path("orchestration/state.json"),
    pathlib.Path("orchestration/plan.json"),
    pathlib.Path("orchestration/decisions.jsonl"),
    pathlib.Path("input/input.json"),
]

STAGE_ARTIFACTS = {
    "input_parser": [pathlib.Path("input/input.json")],
    "script_writer": [pathlib.Path("script/script.json")],
    "audio_foundation": [
        pathlib.Path("audio/voiceover.json"),
        pathlib.Path("audio/bgm-selection.json"),
        pathlib.Path("audio/beat-grid.json"),
    ],
    "global_timeline_initializer": [pathlib.Path("timeline/global-timeline.json")],
    "beat_sync_storyboard_planner": [pathlib.Path("storyboard/storyboard.json")],
    "keyframe_planner": [pathlib.Path("keyframes/keyframes.json")],
    "prompt_engineer": [pathlib.Path("prompts/prompts.json")],
    "image_generator": [pathlib.Path("assets/manifest.json")],
    "constrained_video_generator": [
        pathlib.Path("video/clips.json"),
        pathlib.Path("video/requests.json"),
        pathlib.Path("video/usage.json"),
    ],
    "subtitle_asset_manager": [pathlib.Path("subtitles/subtitles.json"), pathlib.Path("assets/manifest.json")],
    "timeline_builder": [pathlib.Path("timeline/timeline.json")],
    "ffmpeg_renderer_reviewer": [pathlib.Path("outputs/render-plan.json")],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Review project readiness and write a report.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def read_json(path: pathlib.Path, fallback: object) -> object:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def format_run_action(stage: str | None) -> str:
    if stage:
        return f"Run {stage}."
    return "Run input_parser."


def derive_recommendation(missing_artifacts: list[str], state: dict[str, object]) -> str:
    if missing_artifacts:
        first = missing_artifacts[0]
        return f"Restore or regenerate {first}."

    next_stage = state.get("next_stage")
    if isinstance(next_stage, str) and next_stage:
        return format_run_action(next_stage)

    current_stage = state.get("current_stage")
    if isinstance(current_stage, str) and current_stage:
        return f"Continue {current_stage}."

    return "Run input_parser."


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    state = read_json(
        project_dir / "orchestration" / "state.json",
        {
            "current_stage": None,
            "completed_stages": [],
            "skipped_stages": [],
            "last_failed_stage": None,
            "next_stage": None,
        },
    )
    if not isinstance(state, dict):
        print("invalid orchestration/state.json", file=sys.stderr)
        return 1

    missing_artifacts: list[str] = []
    warnings: list[str] = []

    for path in BASELINE_REQUIRED_FILES:
        if not (project_dir / path).is_file():
            missing_artifacts.append(str(path))

    completed_stages = state.get("completed_stages", [])
    if not isinstance(completed_stages, list):
        print("invalid completed_stages in orchestration/state.json", file=sys.stderr)
        return 1

    for stage in completed_stages:
        if not isinstance(stage, str):
            print("completed stage names must be strings", file=sys.stderr)
            return 1
        for path in STAGE_ARTIFACTS.get(stage, []):
            if not (project_dir / path).is_file():
                missing_artifacts.append(str(path))

    next_stage = state.get("next_stage")
    if isinstance(next_stage, str) and next_stage:
        prerequisites = {
            "script_writer": ["input/input.json"],
            "audio_foundation": ["script/script.json"],
            "global_timeline_initializer": [
                "audio/voiceover.json",
                "audio/bgm-selection.json",
                "audio/beat-grid.json",
            ],
            "beat_sync_storyboard_planner": [
                "script/script.json",
                "timeline/global-timeline.json",
            ],
            "keyframe_planner": ["storyboard/storyboard.json"],
            "prompt_engineer": ["storyboard/storyboard.json", "keyframes/keyframes.json"],
            "image_generator": ["prompts/prompts.json"],
            "constrained_video_generator": ["storyboard/storyboard.json"],
            "subtitle_asset_manager": [
                "audio/voiceover.json",
                "storyboard/storyboard.json",
                "video/clips.json",
            ],
            "timeline_builder": [
                "storyboard/storyboard.json",
                "timeline/global-timeline.json",
                "video/clips.json",
                "audio/voiceover.json",
            ],
            "ffmpeg_renderer_reviewer": ["timeline/timeline.json"],
        }.get(next_stage, [])

        missing_prerequisites = [path for path in prerequisites if not (project_dir / path).is_file()]
        if missing_prerequisites:
            warnings.append(
                "next_stage prerequisites missing for "
                f"{next_stage}: {', '.join(missing_prerequisites)}"
            )
            missing_artifacts.extend(path for path in missing_prerequisites if path not in missing_artifacts)

    if missing_artifacts:
        status = "blocked"
    elif state.get("current_stage") and not state.get("next_stage"):
        status = "in_progress"
    else:
        status = "ready"

    report = {
        "project": project_dir.name,
        "status": status,
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "completed_stages": completed_stages,
        "missing_artifacts": missing_artifacts,
        "warnings": warnings,
        "next_recommended_action": derive_recommendation(missing_artifacts, state),
    }

    review_dir = project_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    report_path = review_dir / "review-report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
