#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Initialize a global timeline from audio artifacts.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    voiceover = json.loads((project_dir / "audio" / "voiceover.json").read_text(encoding="utf-8"))
    beat_grid = json.loads((project_dir / "audio" / "beat-grid.json").read_text(encoding="utf-8"))
    input_path = project_dir / "input" / "input.json"
    task_input = json.loads(input_path.read_text(encoding="utf-8")) if input_path.is_file() else {}

    slots = []
    duration_seconds = float(
        task_input.get("duration_seconds")
        or voiceover.get("target_duration_seconds")
        or voiceover.get("actual_duration_seconds")
        or 0
    )
    if duration_seconds <= 0 and voiceover.get("segments"):
        duration_seconds = float(voiceover["segments"][-1]["end"])
    scene_duration = float(task_input.get("scene_duration_seconds") or 5)
    scene_count = int(math.ceil(duration_seconds / scene_duration)) if duration_seconds > 0 else len(voiceover["segments"])

    for index in range(1, scene_count + 1):
        start = round((index - 1) * scene_duration, 2)
        end = round(min(index * scene_duration, duration_seconds), 2)
        if end <= start:
            end = round(start + scene_duration, 2)
        overlapping = [
            segment["segment_id"]
            for segment in voiceover["segments"]
            if float(segment["start"]) < end and float(segment["end"]) > start
        ]
        slots.append(
            {
                "slot_id": f"scene-slot-{index}",
                "start": start,
                "end": end,
                "duration": round(end - start, 2),
                "narration_segment_ids": overlapping,
            }
        )

    payload = {
        "narration_windows": voiceover["segments"],
        "beat_anchors": beat_grid["beats"],
        "transition_windows": [
            {"time": beat_grid["beats"][-1]["time"], "label": "高潮切换"}
        ],
        "reserved_silence_gaps": [],
        "scene_timing_slots": slots,
        "scene_duration_seconds": scene_duration,
        "scene_count": scene_count,
        "contract_note": "Scene slots are fixed by workflow contract; narration windows may span multiple slots.",
    }
    output_path = project_dir / "timeline" / "global-timeline.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
