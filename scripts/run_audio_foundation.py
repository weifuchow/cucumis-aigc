#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mock audio foundations from a script.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    script = json.loads((project_dir / "script" / "script.json").read_text(encoding="utf-8"))

    segments = []
    current = 0.0
    for index, line in enumerate(script["audio_track"], start=1):
        duration = 2.5 if index < len(script["audio_track"]) else 3.0
        segment = {
            "segment_id": f"seg-{index}",
            "text": line,
            "start": round(current, 2),
            "end": round(current + duration, 2),
        }
        segments.append(segment)
        current += duration

    beat_grid = {
        "beats": [
            {"time": round(segment["start"], 2), "kind": "narration_start"}
            for segment in segments
        ]
        + [{"time": round(segments[-1]["end"], 2), "kind": "climax"}]
    }
    bgm_selection = {
        "track_id": "bgm-audio-first-001",
        "mood": script["emotion_markers"][0]["label"],
    }
    voiceover = {"segments": segments}

    audio_dir = project_dir / "audio"
    (audio_dir / "voiceover.json").write_text(json.dumps(voiceover, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "bgm-selection.json").write_text(json.dumps(bgm_selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "beat-grid.json").write_text(json.dumps(beat_grid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(audio_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
