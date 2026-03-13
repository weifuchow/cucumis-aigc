#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib

from poe.client import load_poe_config
from poe.media import generate_video
from poe.usage import append_cost_event, write_usage_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate constrained video clips from storyboard scenes.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    storyboard = json.loads((project_dir / "storyboard" / "storyboard.json").read_text(encoding="utf-8"))
    task_input = json.loads((project_dir / "input" / "input.json").read_text(encoding="utf-8"))
    config = load_poe_config()

    video_result = generate_video(
        config=config,
        model=str(task_input["video_model"]),
        scenes=storyboard["scenes"],
        aspect_ratio=str(task_input["aspect_ratio"]),
    )

    video_dir = project_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    clips_payload = {"clips": video_result["clips"]}
    requests_payload = {
        "provider": "poe",
        "mode": video_result["mode"],
        "model": video_result["model"],
        "request_id": video_result["request_id"],
        "response": video_result["raw_response"],
    }
    usage_payload = {
        "provider": "poe",
        "mode": video_result["mode"],
        "model": video_result["model"],
        "request_id": video_result["request_id"],
        "cost_points": video_result["usage"]["cost_points"],
    }

    write_usage_json(video_dir / "clips.json", clips_payload)
    write_usage_json(video_dir / "requests.json", requests_payload)
    write_usage_json(video_dir / "usage.json", usage_payload)
    append_cost_event(
        project_dir,
        {
            "skill": "constrained_video_generator",
            "model": video_result["model"],
            "request_id": video_result["request_id"],
            "cost_points": video_result["usage"]["cost_points"],
            "output_path": "video/clips.json",
        },
    )
    print(video_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
