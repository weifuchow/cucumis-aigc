#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
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


def load_scene_images(project_dir: pathlib.Path) -> dict[str, list[dict[str, Any]]]:
    manifest_path = project_dir / "assets" / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = read_json(manifest_path, "asset manifest")
    except (ValueError, json.JSONDecodeError):
        return {}

    scene_images: dict[str, list[dict[str, Any]]] = {}
    images = manifest.get("images")
    if not isinstance(images, list):
        return scene_images
    for item in images:
        if not isinstance(item, dict):
            continue
        scene_id = item.get("scene_id")
        path = item.get("path")
        if isinstance(scene_id, str) and scene_id and isinstance(path, str) and path:
            scene_images.setdefault(scene_id, []).append(item)
    for scene_id, items in scene_images.items():
        items.sort(
            key=lambda item: (
                int(item.get("frame_index", 1)) if isinstance(item.get("frame_index", 1), int) else 1,
                str(item.get("asset_id", "")),
            )
        )
        scene_images[scene_id] = items
    return scene_images


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


def render_image_sequence_clip(
    *,
    ffmpeg_binary: str,
    project_dir: pathlib.Path,
    scene_id: str,
    image_paths: list[str],
    duration_seconds: float,
) -> tuple[bool, str]:
    resolved_paths: list[pathlib.Path] = []
    for image_path in image_paths:
        source_path = pathlib.Path(image_path)
        if not source_path.is_absolute():
            source_path = project_dir / source_path
        if not source_path.is_file():
            return False, f"image not found for sequence render: {image_path}"
        resolved_paths.append(source_path)
    if not resolved_paths:
        return False, "no images available for sequence render"

    safe_duration = max(round(duration_seconds, 2), 0.8)
    per_frame_duration = max(0.35, safe_duration / max(1, len(resolved_paths)))
    output_path = project_dir / "video" / "static" / f"{scene_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".ffconcat", delete=False, encoding="utf-8") as handle:
        concat_path = pathlib.Path(handle.name)
        handle.write("ffconcat version 1.0\n")
        for image_path in resolved_paths:
            escaped = str(image_path).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\n")
            handle.write(f"duration {per_frame_duration:.3f}\n")
        escaped_last = str(resolved_paths[-1]).replace("'", "'\\''")
        handle.write(f"file '{escaped_last}'\n")

    command = [
        ffmpeg_binary,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_path),
        "-vf",
        (
            "scale=720:1280:force_original_aspect_ratio=decrease,"
            "pad=720:1280:(ow-iw)/2:(oh-ih)/2,"
            "fps=30,"
            "format=yuv420p"
        ),
        "-t",
        str(safe_duration),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    finally:
        concat_path.unlink(missing_ok=True)
    if result.returncode != 0 or not output_path.is_file():
        return False, (result.stderr or "ffmpeg sequence render failed").strip()[-500:]
    return True, str(output_path.relative_to(project_dir))


def should_use_local_image_clip(scene: dict[str, Any], scene_images: list[dict[str, Any]]) -> bool:
    if not scene_images:
        return False
    asset_mode = str(scene.get("asset_mode", "")).lower()
    motion_intent = str(scene.get("motion_intent", "")).lower()
    expensive_motion = {"fast_push", "black_flash", "whip_pan", "handheld"}
    if motion_intent in expensive_motion:
        return False
    if asset_mode == "mixed":
        return len(scene_images) >= 3
    if should_use_static_clip(scene):
        return True
    return len(scene_images) >= 2


def download_video(url: str, output_path: pathlib.Path) -> pathlib.Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, 4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "video/*,*/*"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
                content_type = str(resp.headers.get("Content-Type", ""))
            ext = ".mp4"
            if "webm" in content_type:
                ext = ".webm"
            elif "quicktime" in content_type or "mov" in content_type:
                ext = ".mov"
            final_path = output_path.with_suffix(ext)
            final_path.write_bytes(data)
            return final_path
        except Exception as exc:
            if attempt >= 3:
                raise RuntimeError(f"failed to download video after 3 attempts: {exc}") from exc
            time.sleep(attempt * 3)
    raise RuntimeError("download_video: unreachable")


def _build_ref_image_paths(
    scene_id: str,
    prev_scene_id: str | None,
    scene_images: dict[str, list[dict[str, Any]]],
    project_dir: pathlib.Path,
) -> list[dict[str, str]]:
    """Return annotated list of reference image absolute paths for video model."""
    refs: list[dict[str, str]] = []
    if prev_scene_id:
        prev_imgs = [str(item.get("path", "")) for item in scene_images.get(prev_scene_id, []) if item.get("path")]
        if prev_imgs:
            abs_path = str((project_dir / prev_imgs[-1]).resolve())
            refs.append({"path": abs_path, "role": "start_frame", "note": f"{prev_scene_id} 末帧，视频起跳点"})
    cur_imgs = [str(item.get("path", "")) for item in scene_images.get(scene_id, []) if item.get("path")]
    if cur_imgs:
        refs.append({"path": str((project_dir / cur_imgs[0]).resolve()), "role": "end_frame", "note": f"{scene_id} 首帧，落点参考"})
        if len(cur_imgs) > 1:
            refs.append({"path": str((project_dir / cur_imgs[-1]).resolve()), "role": "end_frame_alt", "note": f"{scene_id} 末帧，动态落幅"})
    return refs


def load_prompt_map(project_dir: pathlib.Path) -> dict[str, dict[str, Any]]:
    prompts_path = project_dir / "prompts" / "prompts.json"
    if not prompts_path.is_file():
        return {}
    try:
        payload = read_json(prompts_path, "prompts")
    except (ValueError, json.JSONDecodeError):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for item in payload.get("prompts", []):
        if isinstance(item, dict):
            scene_id = item.get("scene_id")
            if isinstance(scene_id, str) and scene_id:
                result[scene_id] = item
    return result


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    storyboard = read_json(project_dir / "storyboard" / "storyboard.json", "storyboard")
    task_input = read_json(project_dir / "input" / "input.json", "input")

    scenes = storyboard.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("storyboard/scenes must be a non-empty array")

    ffmpeg_available = shutil.which(args.ffmpeg_binary) is not None
    scene_images = load_scene_images(project_dir)
    prompt_map = load_prompt_map(project_dir)
    static_clip_errors: list[str] = []
    local_static_clips: dict[str, dict[str, Any]] = {}
    dynamic_scenes: list[dict[str, Any]] = []
    prev_scene_id: str | None = None

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", ""))
        if not scene_id:
            continue
        duration = as_float(scene.get("duration_seconds"), 2.0)
        scene_assets = scene_images.get(scene_id, [])
        image_paths = [str(item.get("path", "")) for item in scene_assets if isinstance(item.get("path"), str)]
        if should_use_local_image_clip(scene, scene_assets) and ffmpeg_available and image_paths:
            if len(image_paths) == 1:
                ok, output_or_error = render_static_clip(
                    ffmpeg_binary=args.ffmpeg_binary,
                    project_dir=project_dir,
                    image_path=image_paths[0],
                    scene_id=scene_id,
                    duration_seconds=duration,
                )
                source_mode = "static_ffmpeg"
            else:
                ok, output_or_error = render_image_sequence_clip(
                    ffmpeg_binary=args.ffmpeg_binary,
                    project_dir=project_dir,
                    scene_id=scene_id,
                    image_paths=image_paths,
                    duration_seconds=duration,
                )
                source_mode = "image_sequence_ffmpeg"
            if ok:
                per_frame_dur = max(0.35, duration / max(1, len(image_paths))) if len(image_paths) > 1 else duration
                local_static_clips[scene_id] = {
                    "scene_id": scene_id,
                    "duration_seconds": duration,
                    "url": output_or_error,
                    "motion_intent": scene.get("motion_intent", "hold"),
                    "source_mode": source_mode,
                    "planning": {
                        "source_images": image_paths,
                        "frame_count": len(image_paths),
                        "ffmpeg_params": {
                            "per_frame_duration_seconds": round(per_frame_dur, 3),
                            "resolution": "720x1280",
                            "fps": 30,
                            "codec": "libx264",
                        },
                    },
                }
            else:
                static_clip_errors.append(f"{scene_id}: {output_or_error}")
                # Attach reference images before adding to dynamic_scenes
                scene = dict(scene)
                scene["_ref_images"] = _build_ref_image_paths(scene_id, prev_scene_id, scene_images, project_dir)
                dynamic_scenes.append(scene)
        else:
            scene = dict(scene)
            scene["_ref_images"] = _build_ref_image_paths(scene_id, prev_scene_id, scene_images, project_dir)
            dynamic_scenes.append(scene)
        prev_scene_id = scene_id

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
    prev_scene_id: str | None = None
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", ""))
        if not scene_id:
            continue
        if scene_id in local_static_clips:
            merged_clips.append(local_static_clips[scene_id])
            prev_scene_id = scene_id
            continue
        clip = generated_by_scene.get(scene_id)
        if clip:
            if "planning" not in clip:
                prompt_entry = prompt_map.get(scene_id, {})
                cur_images = [str(item.get("path", "")) for item in scene_images.get(scene_id, []) if item.get("path")]

                # Build annotated reference list: last frame of prev scene → first/last of current
                reference_images: list[dict[str, str]] = []
                if prev_scene_id:
                    prev_imgs = [str(item.get("path", "")) for item in scene_images.get(prev_scene_id, []) if item.get("path")]
                    if prev_imgs:
                        reference_images.append({"path": prev_imgs[-1], "role": "start_frame", "scene": prev_scene_id, "note": "上一场景末帧，视频从此画面起跳"})
                if cur_images:
                    reference_images.append({"path": cur_images[0], "role": "end_frame", "scene": scene_id, "note": "本场景首帧，视频落点参考"})
                    if len(cur_images) > 1:
                        reference_images.append({"path": cur_images[-1], "role": "end_frame_alt", "scene": scene_id, "note": "本场景末帧，动态结束落幅"})

                clip["planning"] = {
                    "video_prompt": {
                        "positive": str(prompt_entry.get("positive_prompt", scene.get("visual_description", ""))),
                        "negative": str(prompt_entry.get("negative_prompt", "")),
                        "style": str(prompt_entry.get("style", "")),
                        "camera": str(scene.get("motion_intent", "")),
                        "duration_seconds": as_float(scene.get("duration_seconds"), 2.0),
                        "aspect_ratio": str(prompt_entry.get("aspect_ratio", task_input.get("aspect_ratio", "9:16"))),
                    },
                    "reference_images": reference_images,
                    "scene_metadata": {
                        "purpose": scene.get("purpose"),
                        "beat_alignment": scene.get("beat_alignment"),
                        "transition_intent": scene.get("transition_intent"),
                        "asset_mode": scene.get("asset_mode"),
                    },
                }
            merged_clips.append(clip)
            prev_scene_id = scene_id
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
        prev_scene_id = scene_id

    static_count = len(local_static_clips)
    dynamic_count = len(dynamic_scenes)
    mode = str(video_result.get("mode", "unknown"))
    if static_count and dynamic_count:
        mode = f"hybrid:{mode}"
    elif static_count and not dynamic_count:
        mode = "local_static_only"

    # Download model-generated video clips to local disk and update URLs
    video_dir = project_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    model_video_dir = video_dir / "model"
    all_request_ids: list[str] = []
    download_errors: list[str] = []
    for clip in merged_clips:
        rid = clip.get("request_id")
        if isinstance(rid, str) and rid and rid not in all_request_ids:
            all_request_ids.append(rid)
        if clip.get("source_mode") != "model_generated":
            continue
        url = str(clip.get("url", ""))
        if not url.startswith(("http://", "https://")):
            print(f"[video] {clip['scene_id']}: no downloadable URL (url={url!r}), skipping download", flush=True)
            continue
        scene_id = str(clip["scene_id"])
        output_stem = model_video_dir / scene_id
        print(f"[video] downloading {scene_id} from {url} ...", flush=True)
        try:
            local_path = download_video(url, output_stem)
            clip["url"] = str(local_path.relative_to(project_dir))
            clip["local_path"] = clip["url"]
            print(f"[video] saved {scene_id} → {clip['url']} ({local_path.stat().st_size // 1024}KB)", flush=True)
        except Exception as exc:
            download_errors.append(f"{scene_id}: {exc}")
            print(f"[video] ERROR downloading {scene_id}: {exc}", flush=True)

    clips_payload = {"clips": merged_clips}
    requests_payload = {
        "provider": "poe",
        "mode": mode,
        "model": str(task_input["video_model"]),
        "request_id": video_result.get("request_id"),
        "all_request_ids": all_request_ids,
        "response": video_result.get("raw_response"),
        "strategy": {
            "static_clip_count": static_count,
            "dynamic_clip_count": dynamic_count,
            "static_clip_errors": static_clip_errors,
            "download_errors": download_errors,
            "ffmpeg_available": ffmpeg_available,
            "local_image_scene_ids": sorted(local_static_clips.keys()),
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
