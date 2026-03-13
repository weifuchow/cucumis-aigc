#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
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

    slots = []
    for index, segment in enumerate(voiceover["segments"], start=1):
        slots.append(
            {
                "slot_id": f"scene-slot-{index}",
                "start": segment["start"],
                "end": segment["end"],
                "duration": round(segment["end"] - segment["start"], 2),
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
    }
    output_path = project_dir / "timeline" / "global-timeline.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
