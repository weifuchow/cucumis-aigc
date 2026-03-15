#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build input.json from brief/intake.json (with model defaults).")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


MODEL_DEFAULTS: dict[str, object] = {
    "audio_model": "elevenlabs-v3",
    "image_model": "flux-schnell",
    "video_model": "veo-3.1-fast",
    "requires_voiceover": True,
    "requires_subtitles": True,
}

FIELD_DEFAULTS: dict[str, object] = {
    "goal": "生成一条音频优先的 AI 视频",
    "duration_seconds": 30,
    "language": "中文",
    "aspect_ratio": "9:16",
    "style": "专业、克制",
    "music_emotion": "平稳推进",
    "pacing_preference": "均匀",
}


def build_input(intake: dict[str, object]) -> dict[str, object]:
    """Map brief/intake.json fields to pipeline input.json, adding model defaults."""
    result: dict[str, object] = {}

    # Copy all content fields from intake
    for key in ("topic", "goal", "duration_seconds", "language", "aspect_ratio",
                "style", "music_emotion", "pacing_preference",
                "audience", "platform", "voiceover_requirements", "subtitle_requirements",
                "content_structure", "visual_preferences", "constraints"):
        if key in intake:
            result[key] = intake[key]

    # Apply field defaults for missing required fields
    for key, default in FIELD_DEFAULTS.items():
        if not result.get(key):
            result[key] = default

    # Add model configuration (can be overridden by intake if present)
    for key, default in MODEL_DEFAULTS.items():
        result[key] = intake.get(key, default)

    return result


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    intake_path = project_dir / "brief" / "intake.json"
    output_path = project_dir / "input" / "input.json"

    intake = json.loads(intake_path.read_text(encoding="utf-8"))
    payload = build_input(intake)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
