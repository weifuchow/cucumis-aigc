#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate keyframe anchors from a timed storyboard.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def load_storyboard(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing storyboard file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("storyboard payload must be an object")
    scenes = payload.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("storyboard scenes must be a non-empty array")
    return scenes


def as_float(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    return float(value)


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    try:
        scenes = load_storyboard(project_dir / "storyboard" / "storyboard.json")
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    keyframes: list[dict[str, Any]] = []
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict):
            print("storyboard scene must be an object", file=sys.stderr)
            return 1
        scene_id = str(scene.get("scene_id", f"scene-{index}"))
        start = as_float(scene.get("start_time"), f"{scene_id}.start_time")
        end = as_float(scene.get("end_time"), f"{scene_id}.end_time")
        if end <= start:
            print(f"invalid scene timing for {scene_id}", file=sys.stderr)
            return 1
        keyframes.append(
            {
                "keyframe_id": f"keyframe-{index}",
                "scene_id": scene_id,
                "timestamp": round((start + end) / 2, 2),
                "visual_anchor": str(scene.get("visual_description", "默认镜头")),
                "camera_intent": str(scene.get("motion_intent", "slow_pan")),
                "emotion_hint": str(scene.get("beat_alignment", "narration_sync")),
            }
        )

    payload = {
        "metadata": {
            "source": "storyboard/storyboard.json",
            "scene_count": len(keyframes),
        },
        "keyframes": keyframes,
    }
    output_path = project_dir / "keyframes" / "keyframes.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
