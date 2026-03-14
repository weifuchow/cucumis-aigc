#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate subtitle assets and update project manifest.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def read_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def read_manifest(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {"images": [], "subtitles": [], "audio": [], "videos": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"images": [], "subtitles": [], "audio": [], "videos": []}
    return payload


def match_scene_id(start: float, scenes: list[dict[str, Any]]) -> str:
    for scene in scenes:
        scene_start = scene.get("start_time")
        scene_end = scene.get("end_time")
        if isinstance(scene_start, (int, float)) and isinstance(scene_end, (int, float)):
            if float(scene_start) <= start <= float(scene_end):
                return str(scene.get("scene_id", "scene-unknown"))
    if scenes:
        return str(scenes[0].get("scene_id", "scene-1"))
    return "scene-unknown"


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    try:
        voiceover_payload = read_json(project_dir / "audio" / "voiceover.json", "voiceover")
        storyboard_payload = read_json(project_dir / "storyboard" / "storyboard.json", "storyboard")
        clips_payload = read_json(project_dir / "video" / "clips.json", "video clips")
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    segments = voiceover_payload.get("segments")
    scenes = storyboard_payload.get("scenes")
    clips = clips_payload.get("clips")
    if not isinstance(segments, list) or not segments:
        print("voiceover segments must be a non-empty array", file=sys.stderr)
        return 1
    if not isinstance(scenes, list) or not scenes:
        print("storyboard scenes must be a non-empty array", file=sys.stderr)
        return 1
    if not isinstance(clips, list):
        print("video clips must be an array", file=sys.stderr)
        return 1

    subtitle_entries: list[dict[str, Any]] = []
    for index, segment in enumerate(segments, start=1):
        if not isinstance(segment, dict):
            continue
        start = float(segment.get("start", 0))
        end = float(segment.get("end", 0))
        if end <= start:
            continue
        subtitle_entries.append(
            {
                "index": index,
                "scene_id": match_scene_id(start, [scene for scene in scenes if isinstance(scene, dict)]),
                "start": round(start, 2),
                "end": round(end, 2),
                "text": str(segment.get("text", "")),
            }
        )

    if not subtitle_entries:
        print("unable to generate subtitle entries", file=sys.stderr)
        return 1

    subtitles_payload = {
        "format": "json",
        "language": "中文",
        "entries": subtitle_entries,
    }
    subtitles_path = project_dir / "subtitles" / "subtitles.json"
    subtitles_path.parent.mkdir(parents=True, exist_ok=True)
    subtitles_path.write_text(json.dumps(subtitles_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    manifest_path = project_dir / "assets" / "manifest.json"
    manifest = read_manifest(manifest_path)
    manifest.setdefault("images", [])
    manifest["subtitles"] = [
        {
            "asset_id": "subtitle-main",
            "path": "subtitles/subtitles.json",
            "format": "json",
            "entry_count": len(subtitle_entries),
        }
    ]
    manifest["audio"] = [
        {"asset_id": "voiceover-main", "path": "audio/voiceover.json"},
        {"asset_id": "bgm-main", "path": "audio/bgm-selection.json"},
    ]
    manifest["videos"] = [
        {
            "asset_id": f"video-{index}",
            "scene_id": str(clip.get("scene_id", f"scene-{index}")),
            "url": str(clip.get("url", "")),
            "duration_seconds": clip.get("duration_seconds"),
        }
        for index, clip in enumerate(clips, start=1)
        if isinstance(clip, dict)
    ]

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(subtitles_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
