#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib

from poe.client import load_poe_config
from poe.media import generate_audio
from poe.usage import append_cost_event, write_usage_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mock audio foundations from a script.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    script = json.loads((project_dir / "script" / "script.json").read_text(encoding="utf-8"))
    task_input = json.loads((project_dir / "input" / "input.json").read_text(encoding="utf-8"))
    config = load_poe_config()

    audio_result = generate_audio(
        config=config,
        model=str(task_input["audio_model"]),
        prompt="\n".join(script["audio_track"]),
        duration_seconds=int(task_input["duration_seconds"]),
        language=str(task_input["language"]),
    )

    segments = audio_result["segments"]

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
    tts_response = {
        "provider": "poe",
        "mode": audio_result["mode"],
        "model": audio_result["model"],
        "request_id": audio_result["request_id"],
        "response": audio_result["raw_response"],
    }
    usage = {
        "provider": "poe",
        "mode": audio_result["mode"],
        "model": audio_result["model"],
        "request_id": audio_result["request_id"],
        "cost_points": audio_result["usage"]["cost_points"],
    }

    audio_dir = project_dir / "audio"
    (audio_dir / "voiceover.json").write_text(json.dumps(voiceover, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "bgm-selection.json").write_text(json.dumps(bgm_selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "beat-grid.json").write_text(json.dumps(beat_grid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_usage_json(audio_dir / "tts-response.json", tts_response)
    write_usage_json(audio_dir / "usage.json", usage)
    append_cost_event(
        project_dir,
        {
            "skill": "audio_foundation",
            "model": audio_result["model"],
            "request_id": audio_result["request_id"],
            "cost_points": audio_result["usage"]["cost_points"],
            "output_path": "audio/voiceover.json",
        },
    )
    print(audio_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
