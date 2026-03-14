#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
from typing import Any

from poe.client import load_poe_config
from poe.media import generate_video
from poe.usage import append_cost_event, write_usage_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate constrained video clips from storyboard scenes.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--ffmpeg-binary",
        default="ffmpeg",
        help="ffmpeg binary path or command name for local static clip generation.",
    )
    return parser.parse_args()


def read_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object: {path}")
    return payload


def as_float(value: object, fallback: float) -> float:
    if isinstance(value, bool):
        return fallback
    if isinstance(value, (int, float)):
        return float(value)
    return fallback


def load_image_map(project_dir: pathlib.Path) -> dict[str, str]:
    manifest_path = project_dir / "assets" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = read_json(manifest_path, "asset manifest")
    except (ValueError, json.JSONDecodeError):
        return {}

    image_map: dict[str, str] = {}
    images = manifest.get("images")
    if not isinstance(images, list):
        return image_map
    for item in images:
        if not isinstance(item, dict):
            continue
        scene_id = item.get("scene_id")
        path = item.get("path")
        if isinstance(scene_id, str) and scene_id and isinstance(path, str) and path:
            image_map[scene_id] = path
    return image_map


def should_use_static_clip(scene: dict[str, Any]) -> bool:
    asset_mode = str(scene.get("asset_mode", "")).lower()
    motion_intent = str(scene.get("motion_intent", "")).lower()
    static_motion = {"static", "hold", "slow_pan", "locked"}
    if asset_mode == "static":
        return True
    return motion_intent in static_motion


def render_static_clip(
    *,
    ffmpeg_binary: str,
    project_dir: pathlib.Path,
    image_path: str,
    scene_id: str,
    duration_seconds: float,
) -> tuple[bool, str]:
    source_path = pathlib.Path(image_path)
    if not source_path.is_absolute():
        source_path = project_dir / source_path
    if not source_path.is_file():
        return False, f"image not found for static render: {image_path}"

    safe_duration = max(round(duration_seconds, 2), 0.8)
    output_path = project_dir / "video" / "static" / f"{scene_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    command = [
        ffmpeg_binary,
        "-y",
        "-loop",
        "1",
        "-i",
        str(source_path),
        "-t",
        str(safe_duration),
        "-vf",
        (
            "scale=720:1280:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
            "format=yuv420p"
        ),
        "-r",
        "30",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not output_path.is_file():
        return False, (result.stderr or "ffmpeg failed").strip()[-500:]
    return True, str(output_path.relative_to(project_dir))


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    storyboard = read_json(project_dir / "storyboard" / "storyboard.json", "storyboard")
    task_input = read_json(project_dir / "input" / "input.json", "input")

    scenes = storyboard.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("storyboard/scenes must be a non-empty array")

    ffmpeg_available = shutil.which(args.ffmpeg_binary) is not None
    image_map = load_image_map(project_dir)
    static_clip_errors: list[str] = []
    local_static_clips: dict[str, dict[str, Any]] = {}
    dynamic_scenes: list[dict[str, Any]] = []

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", ""))
        if not scene_id:
            continue
        duration = as_float(scene.get("duration_seconds"), 2.0)
        if should_use_static_clip(scene) and ffmpeg_available and scene_id in image_map:
            ok, output_or_error = render_static_clip(
                ffmpeg_binary=args.ffmpeg_binary,
                project_dir=project_dir,
                image_path=image_map[scene_id],
                scene_id=scene_id,
                duration_seconds=duration,
            )
            if ok:
                local_static_clips[scene_id] = {
                    "scene_id": scene_id,
                    "duration_seconds": duration,
                    "url": output_or_error,
                    "motion_intent": scene.get("motion_intent", "hold"),
                    "source_mode": "static_ffmpeg",
                }
            else:
                static_clip_errors.append(f"{scene_id}: {output_or_error}")
                dynamic_scenes.append(scene)
        else:
            dynamic_scenes.append(scene)

    video_result: dict[str, Any]
    if dynamic_scenes:
        # Prefer project-local Poe config (projects/<project>/.env) to support per-project keys.
        config = load_poe_config(env_path=project_dir / ".env")
        video_result = generate_video(
            config=config,
            model=str(task_input["video_model"]),
            scenes=dynamic_scenes,
            aspect_ratio=str(task_input["aspect_ratio"]),
        )
    else:
        video_result = {
            "mode": "local_static_only",
            "model": str(task_input["video_model"]),
            "request_id": "local-static-only",
            "clips": [],
            "raw_response": {"note": "all scenes rendered as static ffmpeg clips"},
            "usage": {"cost_points": 0, "mode": "local_static_only"},
        }

    generated_clips = video_result.get("clips")
    if not isinstance(generated_clips, list):
        generated_clips = []
    generated_by_scene: dict[str, dict[str, Any]] = {}
    for clip in generated_clips:
        if not isinstance(clip, dict):
            continue
        scene_id = clip.get("scene_id")
        if isinstance(scene_id, str) and scene_id:
            clip = dict(clip)
            clip.setdefault("source_mode", "model_generated")
            generated_by_scene[scene_id] = clip

    merged_clips: list[dict[str, Any]] = []
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", ""))
        if not scene_id:
            continue
        if scene_id in local_static_clips:
            merged_clips.append(local_static_clips[scene_id])
            continue
        clip = generated_by_scene.get(scene_id)
        if clip:
            merged_clips.append(clip)
            continue
        # Keep pipeline resilient even when a scene has no generated clip.
        merged_clips.append(
            {
                "scene_id": scene_id,
                "duration_seconds": as_float(scene.get("duration_seconds"), 2.0),
                "url": f"missing://video/{scene_id}.mp4",
                "motion_intent": scene.get("motion_intent", "mixed"),
                "source_mode": "missing",
            }
        )

    static_count = len(local_static_clips)
    dynamic_count = len(dynamic_scenes)
    mode = str(video_result.get("mode", "unknown"))
    if static_count and dynamic_count:
        mode = f"hybrid:{mode}"
    elif static_count and not dynamic_count:
        mode = "local_static_only"

    video_dir = project_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    clips_payload = {"clips": merged_clips}
    requests_payload = {
        "provider": "poe",
        "mode": mode,
        "model": str(task_input["video_model"]),
        "request_id": video_result.get("request_id"),
        "response": video_result.get("raw_response"),
        "strategy": {
            "static_clip_count": static_count,
            "dynamic_clip_count": dynamic_count,
            "static_clip_errors": static_clip_errors,
            "ffmpeg_available": ffmpeg_available,
        },
    }
    usage_payload = {
        "provider": "poe",
        "mode": mode,
        "model": str(task_input["video_model"]),
        "request_id": video_result.get("request_id"),
        "cost_points": (video_result.get("usage") or {}).get("cost_points", 0),
        "strategy": {
            "static_clip_count": static_count,
            "dynamic_clip_count": dynamic_count,
        },
    }

    write_usage_json(video_dir / "clips.json", clips_payload)
    write_usage_json(video_dir / "requests.json", requests_payload)
    write_usage_json(video_dir / "usage.json", usage_payload)
    append_cost_event(
        project_dir,
        {
            "skill": "constrained_video_generator",
            "model": str(task_input["video_model"]),
            "request_id": video_result.get("request_id"),
            "cost_points": (video_result.get("usage") or {}).get("cost_points", 0),
            "output_path": "video/clips.json",
        },
    )
    print(video_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
