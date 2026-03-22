"""Video generation for Vidu web via direct internal API calls.

Uses page.evaluate(fetch(..., {credentials: 'include'})) to call the same
internal API the web UI uses — no DOM interaction required.

Task types (selected automatically):
  text2video      — no ref images
  character2video — ref images provided (_ref_images in scene dict)

Upload flow for character2video (verified 2026-03-21):
  1. api.upload_image() per image → "ssupload:?id=..."
  2. api.create_task(type="character2video", ref_image_uris=[...])
  3. api.poll_task() → download_uri (no watermark)
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from . import api

VIDU_ORIGIN = "https://www.vidu.cn"


def generate_video(
    session,
    model: str,
    scenes: list[dict[str, Any]],
    aspect_ratio: str,
    resolution: str = "720p",
    output_dir: Path | None = None,
    poll_interval: float = 5.0,
    poll_max_wait: float = 600.0,
) -> dict[str, Any]:
    """Drive Vidu internal API to generate video clips for *scenes*.

    Returns a dict compatible with the unified provider response::

        {
            "mode": "live",
            "model": model,
            "request_id": <uuid>,
            "clips": [{"scene_id": ..., "url": ..., "duration_seconds": ..., "local_path": ...}],
            "usage": {"credits": 0},
        }
    """
    page = session.page
    # Navigate once to establish cookie context
    page.goto(VIDU_ORIGIN, wait_until="domcontentloaded", timeout=60_000)

    clips: list[dict[str, Any]] = []
    for scene in scenes:
        clip = _generate_single_scene(
            page=page,
            scene=scene,
            model=model,
            aspect_ratio=aspect_ratio,
            resolution=resolution,
            output_dir=output_dir,
            poll_interval=poll_interval,
            poll_max_wait=poll_max_wait,
        )
        clips.append(clip)

    return {
        "mode": "live",
        "model": model,
        "request_id": str(uuid.uuid4()),
        "clips": clips,
        "usage": {"credits": 0},
        "raw_response": {},
    }


def _generate_single_scene(
    *,
    page,
    scene: dict[str, Any],
    model: str,
    aspect_ratio: str,
    resolution: str,
    output_dir: Path | None,
    poll_interval: float,
    poll_max_wait: float,
) -> dict[str, Any]:
    scene_id = scene.get("scene_id", "scene")
    prompt = scene.get("visual_description", "") or scene.get("prompt", "")
    duration = int(scene.get("duration_seconds", 4))
    ref_images: list[dict] = scene.get("_ref_images", [])

    print(f"[vidu_web] Generating video for scene {scene_id!r} …", flush=True)

    settings: dict[str, Any] = {
        "resolution": resolution,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
    }
    if model:
        settings["model_version"] = model

    # Upload reference images and choose task type
    ref_uris: list[str] = []
    if ref_images:
        for img in ref_images:
            p = img.get("path", "")
            if p and Path(p).is_file():
                print(f"[vidu_web]   uploading ref image: {p}", flush=True)
                ref_uris.append(api.upload_image(page, Path(p)))

    task_type = "character2video" if ref_uris else "text2video"
    task_id = api.create_task(page, task_type, prompt, settings, ref_image_uris=ref_uris)
    print(f"[vidu_web]   task_id={task_id} ({task_type}), polling …", flush=True)

    task_result = api.poll_task(
        page, task_id, poll_interval=poll_interval, max_wait=poll_max_wait
    )
    video_url = api.extract_media_url(task_result)

    local_path = ""
    if video_url and output_dir is not None:
        dest = output_dir / f"{task_id}.mp4"
        try:
            api.download_media(video_url, dest)
            local_path = str(dest)
            print(f"[vidu_web]   saved → {dest}", flush=True)
        except Exception as exc:
            print(f"[vidu_web]   Warning: download failed: {exc}", flush=True)

    return {
        "scene_id": scene_id,
        "url": video_url or "",
        "duration_seconds": duration,
        "local_path": local_path,
    }
