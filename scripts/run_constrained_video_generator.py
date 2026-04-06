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
from providers.factory import load_provider


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate constrained video clips from storyboard scenes.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--ffmpeg-binary",
        default="ffmpeg",
        help="ffmpeg binary path or command name for local static clip generation.",
    )
    parser.add_argument(
        "--max-video-calls",
        type=int,
        default=2,
        help="Maximum number of video model API calls. Excess scenes are rendered locally.",
    )
    parser.add_argument(
        "--scenes",
        default="",
        help="Comma-separated scene IDs to force through the video model API. "
             "All other scenes reuse existing clips from clips.json (if available) "
             "or fall back to local FFmpeg render. Example: --scenes scene-7,scene-8",
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


def render_alternating_clip(
    *,
    ffmpeg_binary: str,
    project_dir: pathlib.Path,
    scene_id: str,
    image_paths: list[str],
    duration_seconds: float,
    frame_hold_seconds: float = 0.15,
) -> tuple[bool, str]:
    """Rapid frame alternation for action scenes (running, fighting, etc.)."""
    resolved_paths: list[pathlib.Path] = []
    for image_path in image_paths[:2]:
        p = pathlib.Path(image_path) if pathlib.Path(image_path).is_absolute() else project_dir / image_path
        if not p.is_file():
            return False, f"image not found: {image_path}"
        resolved_paths.append(p)
    if len(resolved_paths) < 2:
        return False, "alternating requires at least 2 images"

    safe_duration = max(round(duration_seconds, 2), 0.8)
    output_path = project_dir / "video" / "static" / f"{scene_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.NamedTemporaryFile("w", suffix=".ffconcat", delete=False, encoding="utf-8") as handle:
        concat_path = pathlib.Path(handle.name)
        handle.write("ffconcat version 1.0\n")
        elapsed, i = 0.0, 0
        while elapsed < safe_duration:
            img = resolved_paths[i % len(resolved_paths)]
            hold = min(frame_hold_seconds, safe_duration - elapsed)
            escaped = str(img).replace("'", "'\\''")
            handle.write(f"file '{escaped}'\nduration {hold:.3f}\n")
            elapsed += frame_hold_seconds
            i += 1
        last = resolved_paths[(i - 1) % len(resolved_paths)]
        handle.write(f"file '{str(last).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'\n")

    command = [
        ffmpeg_binary, "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_path),
        "-vf", "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p",
        "-t", str(safe_duration), "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True)
    finally:
        concat_path.unlink(missing_ok=True)
    if result.returncode != 0 or not output_path.is_file():
        return False, (result.stderr or "alternating render failed").strip()[-500:]
    return True, str(output_path.relative_to(project_dir))


def render_crossfade_clip(
    *,
    ffmpeg_binary: str,
    project_dir: pathlib.Path,
    scene_id: str,
    image_paths: list[str],
    duration_seconds: float,
    fade_duration: float = 0.5,
) -> tuple[bool, str]:
    """Smooth crossfade between two images for slow transitions."""
    resolved_paths: list[pathlib.Path] = []
    for image_path in image_paths[:2]:
        p = pathlib.Path(image_path) if pathlib.Path(image_path).is_absolute() else project_dir / image_path
        if not p.is_file():
            return False, f"image not found: {image_path}"
        resolved_paths.append(p)
    if len(resolved_paths) < 2:
        return False, "crossfade requires at least 2 images"

    safe_duration = max(round(duration_seconds, 2), 1.0)
    per_seg = round(safe_duration / 2, 3)
    fade_dur = min(fade_duration, per_seg * 0.4)
    output_path = project_dir / "video" / "static" / f"{scene_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    scale_vf = "scale=720:1280:force_original_aspect_ratio=decrease,pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"
    filter_complex = (
        f"[0:v]{scale_vf}[v0];[1:v]{scale_vf}[v1];"
        f"[v0][v1]xfade=transition=fade:duration={fade_dur:.3f}:offset={per_seg - fade_dur:.3f}[vout]"
    )
    command = [
        ffmpeg_binary, "-y",
        "-loop", "1", "-t", str(per_seg), "-i", str(resolved_paths[0]),
        "-loop", "1", "-t", str(per_seg), "-i", str(resolved_paths[1]),
        "-filter_complex", filter_complex,
        "-map", "[vout]", "-t", str(safe_duration),
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not output_path.is_file():
        return False, (result.stderr or "crossfade render failed").strip()[-500:]
    return True, str(output_path.relative_to(project_dir))


def render_zoom_pan_clip(
    *,
    ffmpeg_binary: str,
    project_dir: pathlib.Path,
    scene_id: str,
    image_path: str,
    duration_seconds: float,
    direction: str = "zoom_in",
) -> tuple[bool, str]:
    """Ken Burns zoom/pan effect on a single image."""
    source_path = pathlib.Path(image_path) if pathlib.Path(image_path).is_absolute() else project_dir / image_path
    if not source_path.is_file():
        return False, f"image not found: {image_path}"

    safe_duration = max(round(duration_seconds, 2), 0.8)
    total_frames = int(safe_duration * 30)
    output_path = project_dir / "video" / "static" / f"{scene_id}.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    zoompan_exprs: dict[str, str] = {
        "zoom_in":   f"zoompan=z='min(zoom+0.0015,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=720x1280:fps=30",
        "zoom_out":  f"zoompan=z='if(lte(zoom,1.0),1.5,max(zoom-0.0015,1.0))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=720x1280:fps=30",
        "pan_left":  f"zoompan=z=1.2:x='min(x+1,iw*(1-1/zoom))':y='ih/2-(ih/zoom/2)':d={total_frames}:s=720x1280:fps=30",
        "pan_right": f"zoompan=z=1.2:x='max(x-1,0)':y='ih/2-(ih/zoom/2)':d={total_frames}:s=720x1280:fps=30",
    }
    zp = zoompan_exprs.get(direction, zoompan_exprs["zoom_in"])
    command = [
        ffmpeg_binary, "-y",
        "-loop", "1", "-i", str(source_path),
        "-vf", f"scale=1440:2560,{zp},format=yuv420p",
        "-t", str(safe_duration), "-r", "30",
        "-c:v", "libx264", "-pix_fmt", "yuv420p",
        str(output_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not output_path.is_file():
        return False, (result.stderr or "zoom_pan render failed").strip()[-500:]
    return True, str(output_path.relative_to(project_dir))


def _render_by_technique(
    *,
    technique: str,
    ffmpeg_binary: str,
    project_dir: pathlib.Path,
    scene_id: str,
    image_paths: list[str],
    duration_seconds: float,
) -> tuple[bool, str, str]:
    """Dispatch to the right local renderer. Returns (ok, path_or_error, source_mode)."""
    if technique == "alternating" and len(image_paths) >= 2:
        ok, result = render_alternating_clip(
            ffmpeg_binary=ffmpeg_binary, project_dir=project_dir,
            scene_id=scene_id, image_paths=image_paths, duration_seconds=duration_seconds,
        )
        return ok, result, "alternating_ffmpeg"
    if technique == "crossfade" and len(image_paths) >= 2:
        ok, result = render_crossfade_clip(
            ffmpeg_binary=ffmpeg_binary, project_dir=project_dir,
            scene_id=scene_id, image_paths=image_paths, duration_seconds=duration_seconds,
        )
        return ok, result, "crossfade_ffmpeg"
    if technique in ("zoom_in", "zoom_out", "pan_left", "pan_right", "zoom_pan") and image_paths:
        direction = technique if technique != "zoom_pan" else "zoom_in"
        ok, result = render_zoom_pan_clip(
            ffmpeg_binary=ffmpeg_binary, project_dir=project_dir,
            scene_id=scene_id, image_path=image_paths[0], duration_seconds=duration_seconds,
            direction=direction,
        )
        return ok, result, f"{direction}_ffmpeg"
    if len(image_paths) == 1:
        ok, result = render_static_clip(
            ffmpeg_binary=ffmpeg_binary, project_dir=project_dir,
            image_path=image_paths[0], scene_id=scene_id, duration_seconds=duration_seconds,
        )
        return ok, result, "static_ffmpeg"
    ok, result = render_image_sequence_clip(
        ffmpeg_binary=ffmpeg_binary, project_dir=project_dir,
        scene_id=scene_id, image_paths=image_paths, duration_seconds=duration_seconds,
    )
    return ok, result, "image_sequence_ffmpeg"


def _default_technique(motion_intent: str, image_count: int) -> str:
    """Pick best local render technique when storyboard doesn't specify one."""
    if motion_intent in {"fast_push", "whip_pan", "handheld"} and image_count >= 2:
        return "alternating"
    if motion_intent == "slow_pan" and image_count >= 1:
        return "zoom_in"
    if motion_intent == "locked" and image_count >= 2:
        return "crossfade"
    return "sequence" if image_count > 1 else "loop"


def should_use_local_image_clip(scene: dict[str, Any], scene_images: list[dict[str, Any]]) -> bool:
    if not scene_images:
        return False
    asset_mode = str(scene.get("asset_mode", "")).lower()
    # asset_mode is the explicit storyboard decision — take precedence over motion_intent
    if asset_mode == "mixed":
        return False  # explicitly requires video model
    if asset_mode == "static":
        return True  # explicitly local render regardless of motion_intent
    # fallback for unset asset_mode: use motion_intent heuristic
    motion_intent = str(scene.get("motion_intent", "")).lower()
    expensive_motion = {"fast_push", "black_flash", "whip_pan", "handheld"}
    if motion_intent in expensive_motion:
        return False
    if should_use_static_clip(scene):
        return True
    return len(scene_images) >= 2


def download_video(url: str, output_path: pathlib.Path, api_key: str = "") -> pathlib.Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Google AI file download requires the API key as a query parameter
    if api_key and "generativelanguage.googleapis.com" in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}key={api_key}"
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


def _generate_with_multiframe(
    dynamic_scenes: list[dict[str, Any]],
    scene_images: dict[str, list[dict[str, Any]]],
    project_dir: pathlib.Path,
    task_input: dict[str, Any],
) -> dict[str, Any]:
    """Generate video clips using Vidu multiframe API for scenes with 3+ keyframe images.

    For each dynamic scene:
      - Collects scene keyframe images (sorted by frame_index)
      - Selects start_image + 2-3 segment images to hit target duration (~5s)
      - Calls provider.generate_multiframe_video()
      - Falls back to single-image img2video when fewer than 2 images available

    Returns a dict shaped like generate_video() output:
      {mode, model, clips: [{scene_id, url, duration_seconds, ...}], usage}
    """
    provider = load_provider()
    video_model = str(task_input.get("video_model", "viduq3-turbo"))
    aspect_ratio = str(task_input.get("aspect_ratio", "9:16"))

    clips: list[dict[str, Any]] = []
    total_credits = 0

    for scene in dynamic_scenes:
        scene_id = str(scene.get("scene_id", ""))
        target_duration = float(scene.get("duration_seconds", 5.0))
        motion_intent = str(scene.get("motion_intent", "mixed"))

        # Gather this scene's keyframe images (sorted by frame_index)
        scene_imgs = scene_images.get(scene_id, [])
        image_paths = [
            str(project_dir / str(item.get("path", "")))
            for item in sorted(scene_imgs, key=lambda x: int(x.get("frame_index", 1)))
            if item.get("path") and (project_dir / str(item.get("path", ""))).is_file()
        ]

        if len(image_paths) < 2:
            # Not enough images for multiframe — use standard generate_video fallback
            print(f"[video] {scene_id}: only {len(image_paths)} image(s), falling back to generate_video", flush=True)
            fallback_result = provider.generate_video(
                video_model,
                [dict(scene, _ref_images=[{"path": p} for p in image_paths])],
                aspect_ratio,
            )
            for clip in fallback_result.get("clips", []):
                clips.append(clip)
            total_credits += int((fallback_result.get("usage") or {}).get("credits", 0) or (fallback_result.get("usage") or {}).get("cost_points", 0))
            continue

        # Select keyframes for multiframe:
        # start_image + image_settings (2-3 segments to approximate target_duration)
        # Vidu constraint: each segment duration 2-7s (integers)
        n_segments = min(3, len(image_paths) - 1)  # 1-3 transition segments
        segment_duration = max(2, min(7, round(target_duration / max(1, n_segments))))
        # Pick evenly-spaced frames: first, ~middle(s), last
        indices: list[int] = [0]
        if n_segments >= 2 and len(image_paths) >= 3:
            mid = len(image_paths) // 2
            indices.append(mid)
        indices.append(len(image_paths) - 1)
        # Deduplicate while preserving order
        seen: set[int] = set()
        selected_indices: list[int] = []
        for idx in indices:
            if idx not in seen:
                seen.add(idx)
                selected_indices.append(idx)

        start_image = image_paths[selected_indices[0]]
        image_settings = [
            {"key_image": image_paths[i], "duration": segment_duration}
            for i in selected_indices[1:]
        ]

        print(
            f"[video] {scene_id}: multiframe {len(selected_indices)} frames, "
            f"{segment_duration}s/segment, target={target_duration:.1f}s",
            flush=True,
        )

        try:
            result = provider.generate_multiframe_video(
                video_model,
                start_image,
                image_settings,
            )
            url = str(result.get("url", ""))
            total_credits += int((result.get("usage") or {}).get("credits", 0))
            clips.append({
                "scene_id": scene_id,
                "duration_seconds": target_duration,
                "url": url,
                "motion_intent": motion_intent,
                "source_mode": "multiframe_vidu",
                "task_id": result.get("request_id", ""),
                "planning": {
                    "keyframe_count": len(selected_indices),
                    "segment_duration": segment_duration,
                    "selected_frame_paths": [image_paths[i] for i in selected_indices],
                },
            })
        except Exception as exc:
            print(f"[video] {scene_id}: multiframe failed ({exc}), clip url will be empty", file=sys.stderr)
            clips.append({
                "scene_id": scene_id,
                "duration_seconds": target_duration,
                "url": f"error://multiframe/{scene_id}",
                "motion_intent": motion_intent,
                "source_mode": "multiframe_error",
                "error": str(exc),
            })

    return {
        "mode": "multiframe_vidu",
        "model": video_model,
        "request_id": clips[-1].get("task_id", "") if clips else "",
        "clips": clips,
        "raw_response": {"provider": "vidu", "clip_count": len(clips)},
        "usage": {"credits": total_credits, "mode": "live"},
    }


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

    # --scenes: only these scene IDs are sent to the video model API.
    # All other scenes reuse existing clips from clips.json (when valid) or fall back to local render.
    force_api_scenes: set[str] = {s.strip() for s in args.scenes.split(",") if s.strip()} if args.scenes else set()

    # Load existing clips to reuse for scenes not in force_api_scenes.
    existing_clips: dict[str, dict[str, Any]] = {}
    existing_clips_path = project_dir / "video" / "clips.json"
    if existing_clips_path.is_file():
        try:
            existing_data = json.loads(existing_clips_path.read_text(encoding="utf-8"))
            for clip in existing_data.get("clips", []):
                if isinstance(clip, dict):
                    sid = clip.get("scene_id")
                    if isinstance(sid, str) and sid:
                        existing_clips[sid] = clip
        except (json.JSONDecodeError, OSError):
            pass

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", ""))
        if not scene_id:
            continue
        duration = as_float(scene.get("duration_seconds"), 2.0)
        scene_assets = scene_images.get(scene_id, [])
        image_paths = [str(item.get("path", "")) for item in scene_assets if isinstance(item.get("path"), str)]
        technique = str(scene.get("local_render_technique", "")).lower()

        # Reuse existing clip when --scenes is specified and this scene is not in the forced list.
        if force_api_scenes and scene_id not in force_api_scenes and scene_id in existing_clips:
            existing_clip = existing_clips[scene_id]
            existing_url = str(existing_clip.get("url", ""))
            if existing_url:
                local_static_clips[scene_id] = existing_clip
                print(f"[video] {scene_id}: reusing existing clip ({existing_url[:60]})", flush=True)
                prev_scene_id = scene_id
                continue

        if should_use_local_image_clip(scene, scene_assets) and ffmpeg_available and image_paths:
            if not technique:
                technique = _default_technique(str(scene.get("motion_intent", "")).lower(), len(image_paths))
            ok, output_or_error, source_mode = _render_by_technique(
                technique=technique,
                ffmpeg_binary=args.ffmpeg_binary,
                project_dir=project_dir,
                scene_id=scene_id,
                image_paths=image_paths,
                duration_seconds=duration,
            )
            if ok:
                local_static_clips[scene_id] = {
                    "scene_id": scene_id,
                    "duration_seconds": duration,
                    "url": output_or_error,
                    "motion_intent": scene.get("motion_intent", "hold"),
                    "local_render_technique": technique,
                    "source_mode": source_mode,
                    "planning": {
                        "source_images": image_paths,
                        "frame_count": len(image_paths),
                        "ffmpeg_params": {"resolution": "720x1280", "fps": 30, "codec": "libx264"},
                    },
                }
            else:
                static_clip_errors.append(f"{scene_id}: {output_or_error}")
                scene = dict(scene)
                scene["_ref_images"] = _build_ref_image_paths(scene_id, prev_scene_id, scene_images, project_dir)
                dynamic_scenes.append(scene)
        else:
            scene = dict(scene)
            scene["_ref_images"] = _build_ref_image_paths(scene_id, prev_scene_id, scene_images, project_dir)
            dynamic_scenes.append(scene)
        prev_scene_id = scene_id

    # Budget enforcement: cap video model calls, force overflow scenes to local render
    # input.json cost_tier takes precedence over CLI --max-video-calls
    max_video_calls = int(task_input.get("max_video_calls", args.max_video_calls))
    if len(dynamic_scenes) > max_video_calls:
        priority_motion = {"fast_push", "whip_pan", "handheld", "black_flash"}
        dynamic_scenes.sort(key=lambda s: (
            0 if str(s.get("asset_mode", "")).lower() == "mixed" else 1,
            0 if str(s.get("motion_intent", "")).lower() in priority_motion else 1,
            -as_float(s.get("duration_seconds"), 2.0),
        ))
        over_budget = dynamic_scenes[max_video_calls:]
        dynamic_scenes = dynamic_scenes[:max_video_calls]
        print(f"[video] budget cap={max_video_calls}: forcing {len(over_budget)} scene(s) to local render", flush=True)
        for scene in over_budget:
            scene_id = str(scene.get("scene_id", ""))
            scene_assets_list = scene_images.get(scene_id, [])
            image_paths_list = [str(item.get("path", "")) for item in scene_assets_list if isinstance(item.get("path"), str)]
            duration = as_float(scene.get("duration_seconds"), 2.0)
            motion_intent = str(scene.get("motion_intent", "")).lower()
            technique = str(scene.get("local_render_technique", "")).lower() or _default_technique(motion_intent, len(image_paths_list))
            if not image_paths_list or not ffmpeg_available:
                print(f"[video] {scene_id}: no images for forced-local render, keeping in dynamic", flush=True)
                dynamic_scenes.append(scene)
                continue
            ok, output_or_error, source_mode = _render_by_technique(
                technique=technique,
                ffmpeg_binary=args.ffmpeg_binary,
                project_dir=project_dir,
                scene_id=scene_id,
                image_paths=image_paths_list,
                duration_seconds=duration,
            )
            if ok:
                local_static_clips[scene_id] = {
                    "scene_id": scene_id,
                    "duration_seconds": duration,
                    "url": output_or_error,
                    "motion_intent": motion_intent,
                    "local_render_technique": technique,
                    "source_mode": source_mode + "_budget_forced",
                    "planning": {"source_images": image_paths_list, "frame_count": len(image_paths_list)},
                }
                print(f"[video] {scene_id}: budget-forced → {source_mode} ({technique})", flush=True)
            else:
                print(f"[video] {scene_id}: forced-local failed ({output_or_error}), keeping in dynamic", flush=True)
                dynamic_scenes.append(scene)

    video_result: dict[str, Any]
    if dynamic_scenes:
        # Use Vidu multiframe when provider supports it (MEDIA_PROVIDER=vidu in .env)
        _provider = load_provider()
        if _provider.supports("multiframe_video"):
            video_result = _generate_with_multiframe(
                dynamic_scenes=dynamic_scenes,
                scene_images=scene_images,
                project_dir=project_dir,
                task_input=task_input,
            )
        else:
            # Use the active provider's generate_video (supports google/veo, poe, etc.)
            _video_model = getattr(_provider, "default_video_model", None) or str(task_input["video_model"])
            print(f"[video] calling provider.generate_video model={_video_model} scenes={[s['scene_id'] for s in dynamic_scenes]}", flush=True)
            video_result = _provider.generate_video(
                model=_video_model,
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
    # Extract API key for authenticated downloads (e.g. Google AI file URLs)
    _dl_api_key = getattr(getattr(_provider if dynamic_scenes else None, "config", None), "api_key", "") or ""
    for clip in merged_clips:
        rid = clip.get("request_id")
        if isinstance(rid, str) and rid and rid not in all_request_ids:
            all_request_ids.append(rid)
        if clip.get("source_mode") != "model_generated":
            continue
        url = str(clip.get("url", ""))
        if not url.startswith(("http://", "https://", "file://")):
            print(f"[video] {clip['scene_id']}: no downloadable URL (url={url!r}), skipping download", flush=True)
            continue
        scene_id = str(clip["scene_id"])
        output_stem = model_video_dir / scene_id
        print(f"[video] downloading {scene_id} from {url} ...", flush=True)
        try:
            local_path = download_video(url, output_stem, api_key=_dl_api_key)
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
