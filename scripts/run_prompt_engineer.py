#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert storyboard and keyframes into model prompts.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be an object")
    return payload


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    try:
        storyboard = load_json(project_dir / "storyboard" / "storyboard.json", "storyboard")
        keyframes_payload = load_json(project_dir / "keyframes" / "keyframes.json", "keyframes")
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    scenes = storyboard.get("scenes")
    keyframes = keyframes_payload.get("keyframes")
    if not isinstance(scenes, list) or not scenes:
        print("storyboard scenes must be a non-empty array", file=sys.stderr)
        return 1
    if not isinstance(keyframes, list) or not keyframes:
        print("keyframes list must be a non-empty array", file=sys.stderr)
        return 1

    keyframe_by_scene: dict[str, dict[str, Any]] = {}
    for keyframe in keyframes:
        if isinstance(keyframe, dict):
            scene_id = keyframe.get("scene_id")
            if isinstance(scene_id, str) and scene_id:
                keyframe_by_scene[scene_id] = keyframe

    prompts: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            print("scene must be an object", file=sys.stderr)
            return 1
        scene_id = str(scene.get("scene_id", f"scene-{index}"))
        keyframe = keyframe_by_scene.get(scene_id, {})
        positive_prompt = (
            f"{scene.get('visual_description', 'cinematic shot')}; "
            f"camera:{scene.get('motion_intent', keyframe.get('camera_intent', 'slow_pan'))}; "
            f"beat:{scene.get('beat_alignment', keyframe.get('emotion_hint', 'narration_sync'))}; "
            f"anchor:{keyframe.get('visual_anchor', scene.get('visual_description', 'base frame'))}"
        )
        prompts.append(
            {
                "prompt_id": f"prompt-{index}",
                "scene_id": scene_id,
                "positive_prompt": positive_prompt,
                "negative_prompt": "blurry, overexposed, low detail, broken anatomy",
                "style": "cinematic realism",
                "aspect_ratio": "9:16",
                "duration_seconds": scene.get("duration_seconds", 2),
            }
        )

    payload = {
        "metadata": {
            "source_storyboard": "storyboard/storyboard.json",
            "source_keyframes": "keyframes/keyframes.json",
            "prompt_count": len(prompts),
        },
        "prompts": prompts,
    }
    output_path = project_dir / "prompts" / "prompts.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
