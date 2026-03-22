"""Image generation for Vidu web via direct internal API calls.

Uses page.evaluate(fetch(..., {credentials: 'include'})) to call the same
internal API the web UI uses — no DOM interaction required.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from . import api

VIDU_ORIGIN = "https://www.vidu.cn"


def generate_image(
    session,
    model: str,
    prompts: list[dict[str, Any]],
    output_dir: Path | None = None,
    poll_interval: float = 5.0,
    poll_max_wait: float = 300.0,
) -> dict[str, Any]:
    """Generate images for each prompt entry via Vidu internal API.

    If *output_dir* is given, each image is downloaded there (no watermark).

    Returns unified provider response::

        {
            "mode": "live",
            "model": model,
            "request_id": <uuid>,
            "images": [{"scene_id": ..., "prompt_id": ..., "url": ..., "local_path": "..."}],
            "usage": {"credits": 0},
        }
    """
    page = session.page
    page.goto(VIDU_ORIGIN, wait_until="domcontentloaded", timeout=60_000)

    images: list[dict[str, Any]] = []
    for prompt_entry in prompts:
        img = _generate_single(
            page=page,
            prompt_entry=prompt_entry,
            model=model,
            output_dir=output_dir,
            poll_interval=poll_interval,
            poll_max_wait=poll_max_wait,
        )
        images.append(img)

    return {
        "mode": "live",
        "model": model,
        "request_id": str(uuid.uuid4()),
        "images": images,
        "usage": {"credits": 0},
        "raw_response": {},
    }


def _generate_single(
    *,
    page,
    prompt_entry: dict[str, Any],
    model: str,
    output_dir: Path | None,
    poll_interval: float,
    poll_max_wait: float,
) -> dict[str, Any]:
    scene_id = prompt_entry.get("scene_id", "")
    prompt_id = prompt_entry.get("prompt_id", "")
    positive = prompt_entry.get("positive_prompt", "")

    print(f"[vidu_web] Generating image for prompt {prompt_id!r} …", flush=True)

    settings: dict[str, Any] = {}
    if model:
        settings["model_version"] = model

    task_id = api.create_task(page, "text2image", positive, settings)
    print(f"[vidu_web]   task_id={task_id}, polling …", flush=True)

    task_result = api.poll_task(
        page, task_id, poll_interval=poll_interval, max_wait=poll_max_wait
    )
    image_url = api.extract_media_url(task_result)

    local_path = ""
    if image_url and output_dir is not None:
        dest = output_dir / f"{task_id}.png"
        try:
            api.download_media(image_url, dest)
            local_path = str(dest)
            print(f"[vidu_web]   saved → {dest}", flush=True)
        except Exception as exc:
            print(f"[vidu_web]   Warning: download failed: {exc}", flush=True)

    return {
        "scene_id": scene_id,
        "prompt_id": prompt_id,
        "url": image_url or "",
        "local_path": local_path,
    }
