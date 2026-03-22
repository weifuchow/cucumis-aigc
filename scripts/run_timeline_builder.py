#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Assemble renderer-agnostic timeline artifacts.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required file: {label} ({path})")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json in {label} ({path}): {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def as_float(value: object, field: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number")
    if isinstance(value, (int, float)):
        return float(value)
    raise ValueError(f"{field} must be a number")


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    try:
        storyboard = load_json(project_dir / "storyboard" / "storyboard.json", "storyboard")
        global_timeline = load_json(project_dir / "timeline" / "global-timeline.json", "global timeline")
        clips_payload = load_json(project_dir / "video" / "clips.json", "video clips")
        voiceover_payload = load_json(project_dir / "audio" / "voiceover.json", "voiceover")
        bgm_payload = load_json(project_dir / "audio" / "bgm-selection.json", "bgm selection")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    scenes_raw = storyboard.get("scenes")
    if not isinstance(scenes_raw, list) or not scenes_raw:
        print("storyboard scenes are required", file=sys.stderr)
        return 1

    scenes: list[dict[str, Any]] = []
    try:
        for scene in scenes_raw:
            if not isinstance(scene, dict):
                raise ValueError("scene must be an object")
            scene_id = scene.get("scene_id")
            if not isinstance(scene_id, str) or not scene_id:
                raise ValueError("scene_id must be a non-empty string")
            start = as_float(scene.get("start_time"), f"{scene_id}.start_time")
            end = as_float(scene.get("end_time"), f"{scene_id}.end_time")
            if end <= start:
                raise ValueError(f"{scene_id} has invalid time range: start={start}, end={end}")
            scenes.append(scene)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    ordered_scenes = sorted(
        scenes,
        key=lambda scene: (
            as_float(scene["start_time"], "start_time"),
            str(scene["scene_id"]),
        ),
    )

    clips_raw = clips_payload.get("clips")
    if not isinstance(clips_raw, list):
        print("video/clips.json must contain a clips array", file=sys.stderr)
        return 1
    clip_by_scene: dict[str, dict[str, Any]] = {}
    for clip in clips_raw:
        if not isinstance(clip, dict):
            continue
        scene_id = clip.get("scene_id")
        if isinstance(scene_id, str) and scene_id:
            clip_by_scene[scene_id] = clip

    voice_segments_raw = voiceover_payload.get("segments")
    if not isinstance(voice_segments_raw, list):
        print("audio/voiceover.json must contain a segments array", file=sys.stderr)
        return 1

    segments: list[dict[str, Any]] = []
    video_items: list[dict[str, Any]] = []
    for index, scene in enumerate(ordered_scenes, start=1):
        scene_id = str(scene["scene_id"])
        start = round(as_float(scene["start_time"], "start_time"), 2)
        end = round(as_float(scene["end_time"], "end_time"), 2)
        duration = round(end - start, 2)
        clip = clip_by_scene.get(scene_id, {})
        clip_url = str(clip.get("url", f"missing://{scene_id}"))
        motion_intent = str(scene.get("motion_intent", clip.get("motion_intent", "mixed")))

        segments.append(
            {
                "segment_id": f"segment-{index}",
                "scene_id": scene_id,
                "start": start,
                "end": end,
                "duration_seconds": duration,
                "video_clip_url": clip_url,
                "subtitle_text": str(scene.get("subtitle_text", "")),
                "beat_alignment": str(scene.get("beat_alignment", "narration_sync")),
                "transition_intent": str(scene.get("transition_intent", "hold")),
                "motion_intent": motion_intent,
            }
        )
        video_items.append(
            {
                "item_id": f"video-item-{index}",
                "scene_id": scene_id,
                "start": start,
                "end": end,
                "duration_seconds": duration,
                "source": clip_url,
                "motion_intent": motion_intent,
            }
        )

    total_duration = round(max(segment["end"] for segment in segments), 2)

    voice_items: list[dict[str, Any]] = []
    for index, segment in enumerate(voice_segments_raw, start=1):
        if not isinstance(segment, dict):
            continue
        start = round(as_float(segment.get("start"), "voiceover.start"), 2)
        end = round(as_float(segment.get("end"), "voiceover.end"), 2)
        if end <= start:
            print(f"voiceover segment has invalid time range: start={start}, end={end}", file=sys.stderr)
            return 1
        voice_items.append(
            {
                "item_id": f"voice-item-{index}",
                "segment_id": str(segment.get("segment_id", f"seg-{index}")),
                "start": start,
                "end": end,
                "text": str(segment.get("text", "")),
            }
        )

    if not voice_items:
        print("audio/voiceover.json contains no usable segments", file=sys.stderr)
        return 1

    bgm_track_id = str(bgm_payload.get("track_id", "bgm-unknown"))
    bgm_items = [
        {
            "item_id": "bgm-item-1",
            "track_id": bgm_track_id,
            "mood": str(bgm_payload.get("mood", "neutral")),
            "start": 0.0,
            "end": total_duration,
        }
    ]

    input_path = project_dir / "input" / "input.json"
    aspect_ratio = "9:16"
    if input_path.is_file():
        try:
            input_payload = json.loads(input_path.read_text(encoding="utf-8"))
            if isinstance(input_payload, dict):
                aspect_ratio = str(input_payload.get("aspect_ratio", aspect_ratio))
        except json.JSONDecodeError:
            pass

    # 若混音文件存在，合并为单音频轨；否则保留旁白+BGM双轨
    mix_manifest_path = project_dir / "audio" / "mix-manifest.json"
    mixed_audio_path = project_dir / "audio" / "mixed-final.mp3"
    use_mixed = mix_manifest_path.is_file() and mixed_audio_path.is_file()

    if use_mixed:
        audio_source_note = "audio/mixed-final.mp3"
        audio_tracks: list[dict[str, Any]] = [
            {
                "track_id": "audio_mixed",
                "track_type": "audio",
                "source": "audio/mixed-final.mp3",
                "items": [
                    {
                        "item_id": "mixed-item-1",
                        "start": 0.0,
                        "end": total_duration,
                    }
                ],
            }
        ]
    else:
        audio_source_note = "audio/voiceover.json"
        audio_tracks = [
            {
                "track_id": "audio_voiceover",
                "track_type": "audio",
                "source": "audio/voiceover.json",
                "items": voice_items,
            },
            {
                "track_id": "audio_bgm",
                "track_type": "audio",
                "source": "audio/bgm-selection.json",
                "items": bgm_items,
            },
        ]

    timeline_payload = {
        "metadata": {
            "global_timeline_source": "timeline/global-timeline.json",
            "storyboard_source": "storyboard/storyboard.json",
            "clips_source": "video/clips.json",
            "voiceover_source": "audio/voiceover.json",
            "audio_source": audio_source_note,
            "scene_count": len(segments),
            "beat_anchor_count": len(global_timeline.get("beat_anchors", [])),
            "duration_seconds": total_duration,
        },
        "tracks": [
            {
                "track_id": "video_main",
                "track_type": "video",
                "source": "video/clips.json",
                "items": video_items,
            },
            *audio_tracks,
        ],
        "segments": segments,
        "output": {
            "format": "mp4",
            "aspect_ratio": aspect_ratio,
        },
    }

    output_path = project_dir / "timeline" / "timeline.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(timeline_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
