#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a beat-synced storyboard from the global timeline.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    script = json.loads((project_dir / "script" / "script.json").read_text(encoding="utf-8"))
    global_timeline = json.loads((project_dir / "timeline" / "global-timeline.json").read_text(encoding="utf-8"))

    scenes = []
    for index, slot in enumerate(global_timeline["scene_timing_slots"], start=1):
        visual = script["visual_track"][min(index - 1, len(script["visual_track"]) - 1)]
        scenes.append(
            {
                "scene_id": f"scene-{index}",
                "purpose": script["beats"][min(index - 1, len(script["beats"]) - 1)]["purpose"],
                "visual_description": visual,
                "start_time": slot["start"],
                "end_time": slot["end"],
                "duration_seconds": slot["duration"],
                "asset_mode": "mixed" if index == len(global_timeline["scene_timing_slots"]) else "static",
                "subtitle_text": script["audio_track"][min(index - 1, len(script["audio_track"]) - 1)],
                "beat_alignment": "transition_anchor" if index == len(global_timeline["scene_timing_slots"]) else "narration_sync",
                "transition_intent": "black_flash" if index == len(global_timeline["scene_timing_slots"]) else "hold",
                "motion_intent": "fast_push" if index == len(global_timeline["scene_timing_slots"]) else "slow_pan",
            }
        )

    payload = {"scenes": scenes}
    output_path = project_dir / "storyboard" / "storyboard.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
