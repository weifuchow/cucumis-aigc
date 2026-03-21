from __future__ import annotations

import base64
import hashlib
import mimetypes
import pathlib
from typing import Any

from .client import ViduConfig, request_json, poll_task


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_request_id(prefix: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _encode_image(path_or_url: str) -> str:
    """Return base64 data-URL for local files, or the original URL for http(s) links."""
    if path_or_url.startswith("http://") or path_or_url.startswith("https://"):
        return path_or_url
    p = pathlib.Path(path_or_url)
    if not p.is_file():
        raise FileNotFoundError(f"[vidu] image file not found: {path_or_url}")
    mime = mimetypes.guess_type(path_or_url)[0] or "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _extract_video_urls(task: dict[str, Any]) -> list[str]:
    """Extract video URLs from a completed task response.

    Vidu returns either:
      - task["creations"] = [{"url": "...", ...}, ...]
      - task["video"] = {"url": "..."}
      - task["url"] = "..."
    """
    creations = task.get("creations") or []
    if creations:
        return [c["url"] for c in creations if c.get("url")]
    if task.get("video", {}).get("url"):
        return [task["video"]["url"]]
    if task.get("url"):
        return [task["url"]]
    return []


# ---------------------------------------------------------------------------
# Image generation — POST /reference2image
# ---------------------------------------------------------------------------

def generate_image(
    config: ViduConfig,
    model: str,
    prompts: list[dict[str, Any]],
    *,
    poll_interval: float = 5.0,
    poll_max_wait: float = 300.0,
) -> dict[str, Any]:
    """Generate images via Vidu reference2image.

    ``prompts`` matches the shape used by poe/media.py:
      [{"scene_id": ..., "prompt_id": ..., "positive_prompt": ...,
        "negative_prompt": ..., "aspect_ratio": ...,
        "_ref_images": [{"path": "..."}, ...]}]

    Returns a dict compatible with the poe/media.py generate_image return format.
    """
    if not config.api_key:
        images = []
        for item in prompts:
            scene_id = str(item.get("scene_id", "scene"))
            images.append({
                "scene_id": scene_id,
                "prompt_id": str(item.get("prompt_id", "")),
                "url": f"mock://image/{scene_id}.png",
                "style": item.get("style"),
                "aspect_ratio": item.get("aspect_ratio"),
            })
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_request_id("image", str(prompts)),
            "images": images,
            "raw_response": {"provider": "vidu", "mode": "mock"},
            "usage": {"credits": 0, "mode": "mock"},
        }

    images: list[dict[str, Any]] = []
    task_ids: list[str] = []
    raw_responses: list[dict[str, Any]] = []
    total_credits = 0

    for item in prompts:
        scene_id = str(item.get("scene_id", "scene"))
        prompt_id = str(item.get("prompt_id", ""))
        positive_prompt = item.get("positive_prompt", "")
        aspect_ratio = item.get("aspect_ratio", "9:16")

        # Collect reference images (up to 7)
        ref_images: list[str] = []
        for ref in (item.get("_ref_images") or [])[:7]:
            encoded = _encode_image(str(ref.get("path", ref) if isinstance(ref, dict) else ref))
            ref_images.append(encoded)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": positive_prompt,
            "aspect_ratio": aspect_ratio,
        }
        if ref_images:
            payload["images"] = ref_images

        # Create task
        create_resp = request_json(config, "POST", "/reference2image", payload=payload)
        task_id = create_resp.get("task_id", "")
        task_ids.append(task_id)
        print(f"[vidu] image task created: {task_id} (scene={scene_id})", flush=True)

        # Poll until done
        result = poll_task(config, task_id, interval=poll_interval, max_wait=poll_max_wait)
        credits = result.get("credits", 0)
        total_credits += credits or 0

        result_images: list[str] = result.get("images") or []
        url = result_images[0] if result_images else ""

        raw_responses.append({
            "scene_id": scene_id,
            "prompt_id": prompt_id,
            "task_id": task_id,
            "urls": result_images,
        })
        images.append({
            "scene_id": scene_id,
            "prompt_id": prompt_id,
            "url": url,
            "style": item.get("style"),
            "aspect_ratio": aspect_ratio,
            "task_id": task_id,
        })

    return {
        "mode": "live",
        "model": model,
        "request_id": task_ids[-1] if task_ids else "",
        "task_ids": task_ids,
        "images": images,
        "raw_response": {"requests": raw_responses},
        "usage": {"credits": total_credits, "mode": "live"},
    }


# ---------------------------------------------------------------------------
# Video generation — POST /img2video or /text2video
# ---------------------------------------------------------------------------

def generate_video(
    config: ViduConfig,
    model: str,
    scenes: list[dict[str, Any]],
    aspect_ratio: str,
    *,
    resolution: str = "720p",
    poll_interval: float = 5.0,
    poll_max_wait: float = 600.0,
) -> dict[str, Any]:
    """Generate video clips via Vidu img2video or text2video.

    ``scenes`` matches the poe/media.py convention:
      [{"scene_id": ..., "duration_seconds": ..., "visual_description": ...,
        "motion_intent": ..., "_ref_images": [{"path": "..."}, ...]}]

    If a scene has ``_ref_images``, uses img2video; otherwise text2video.
    Returns a dict compatible with poe/media.py generate_video return format.
    """
    if not config.api_key:
        clips = []
        for scene in scenes:
            scene_id = scene["scene_id"]
            clips.append({
                "scene_id": scene_id,
                "duration_seconds": scene["duration_seconds"],
                "url": f"mock://video/{scene_id}.mp4",
                "motion_intent": scene.get("motion_intent"),
            })
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_request_id("video", str(scenes)),
            "clips": clips,
            "raw_response": {"provider": "vidu", "mode": "mock", "aspect_ratio": aspect_ratio},
            "usage": {"credits": 0, "mode": "mock"},
        }

    clips: list[dict[str, Any]] = []
    task_ids: list[str] = []
    raw_responses: list[dict[str, Any]] = []
    total_credits = 0

    for scene in scenes:
        scene_id = scene["scene_id"]
        duration = int(scene.get("duration_seconds", 5))
        prompt = scene.get("visual_description") or scene.get("motion_intent", "")

        ref_images = scene.get("_ref_images") or []
        use_img2video = bool(ref_images)

        if use_img2video:
            start_image = _encode_image(
                str(ref_images[0].get("path", ref_images[0]) if isinstance(ref_images[0], dict) else ref_images[0])
            )
            payload: dict[str, Any] = {
                "model": model,
                "start_image": start_image,
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            }
            endpoint = "/img2video"
        else:
            payload = {
                "model": model,
                "prompt": prompt,
                "duration": duration,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
            }
            endpoint = "/text2video"

        create_resp = request_json(config, "POST", endpoint, payload=payload)
        task_id = create_resp.get("task_id", "")
        task_ids.append(task_id)
        print(f"[vidu] video task created: {task_id} (scene={scene_id}, endpoint={endpoint})", flush=True)

        result = poll_task(config, task_id, interval=poll_interval, max_wait=poll_max_wait)
        credits = result.get("credits", 0)
        total_credits += credits or 0

        urls = _extract_video_urls(result)
        url = urls[0] if urls else ""

        raw_responses.append({"scene_id": scene_id, "task_id": task_id, "urls": urls})
        clips.append({
            "scene_id": scene_id,
            "duration_seconds": duration,
            "url": url,
            "motion_intent": scene.get("motion_intent"),
            "task_id": task_id,
        })

    return {
        "mode": "live",
        "model": model,
        "request_id": task_ids[-1] if task_ids else "",
        "task_ids": task_ids,
        "clips": clips,
        "raw_response": {"requests": raw_responses},
        "usage": {"credits": total_credits, "mode": "live"},
    }


# ---------------------------------------------------------------------------
# Multi-frame video — POST /multiframe
# ---------------------------------------------------------------------------

def generate_multiframe(
    config: ViduConfig,
    model: str,
    start_image: str,
    image_settings: list[dict[str, Any]],
    *,
    resolution: str = "720p",
    poll_interval: float = 5.0,
    poll_max_wait: float = 600.0,
) -> dict[str, Any]:
    """Generate a video from ordered keyframes via Vidu multiframe.

    Args:
        start_image: Local path or URL for the opening frame.
        image_settings: List of 2-9 keyframe dicts:
            [{"key_image": "<path_or_url>", "prompt": "...", "duration": 5}, ...]
            ``key_image`` is required; ``prompt`` and ``duration`` (2-7s) are optional.

    Returns task result dict with ``url`` for the generated video.
    """
    if not config.api_key:
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_request_id("multiframe", start_image),
            "url": "mock://video/multiframe.mp4",
            "raw_response": {"provider": "vidu", "mode": "mock"},
            "usage": {"credits": 0, "mode": "mock"},
        }

    encoded_start = _encode_image(start_image)
    encoded_settings: list[dict[str, Any]] = []
    for frame in image_settings:
        encoded_frame: dict[str, Any] = {
            "key_image": _encode_image(str(frame["key_image"])),
        }
        if "prompt" in frame:
            encoded_frame["prompt"] = frame["prompt"]
        if "duration" in frame:
            encoded_frame["duration"] = int(frame["duration"])
        encoded_settings.append(encoded_frame)

    payload: dict[str, Any] = {
        "model": model,
        "start_image": encoded_start,
        "image_settings": encoded_settings,
        "resolution": resolution,
    }

    create_resp = request_json(config, "POST", "/multiframe", payload=payload)
    task_id = create_resp.get("task_id", "")
    print(f"[vidu] multiframe task created: {task_id}", flush=True)

    result = poll_task(config, task_id, interval=poll_interval, max_wait=poll_max_wait)
    urls = _extract_video_urls(result)

    return {
        "mode": "live",
        "model": model,
        "request_id": task_id,
        "url": urls[0] if urls else "",
        "raw_response": result,
        "usage": {"credits": result.get("credits", 0), "mode": "live"},
    }


# ---------------------------------------------------------------------------
# TTS — POST /audio-tts  (voiceover / narration)
# ---------------------------------------------------------------------------

def generate_tts(
    config: ViduConfig,
    text: str,
    voice_id: str,
    *,
    speed: float = 1.0,
    volume: int = 0,
    pitch: int = 0,
    emotion: str | None = None,
    duration_seconds: int | None = None,
    poll_interval: float = 3.0,
    poll_max_wait: float = 120.0,
) -> dict[str, Any]:
    """Generate voiceover via Vidu TTS (/audio-tts).

    Supports pause markers in text: ``<#1.5#>`` inserts a 1.5-second pause.
    Returns a dict compatible with poe/media.py generate_audio return format.
    """
    if not config.api_key:
        seg_end = float(duration_seconds or 10)
        return {
            "mode": "mock",
            "model": "tts",
            "request_id": _stable_request_id("tts", text),
            "audio_url": None,
            "segments": [
                {"segment_id": "seg-1", "text": text[:40], "start": 0.0, "end": seg_end}
            ],
            "raw_response": {"provider": "vidu", "mode": "mock"},
            "usage": {"credits": 0, "mode": "mock"},
        }

    payload: dict[str, Any] = {
        "text": text,
        "voice_setting": {
            "voice_id": voice_id,
            "speed": speed,
            "volume": volume,
            "pitch": pitch,
        },
    }
    if emotion:
        payload["voice_setting"]["emotion"] = emotion

    # TTS is documented as synchronous but still returns a task_id
    create_resp = request_json(config, "POST", "/audio-tts", payload=payload)
    task_id = create_resp.get("task_id", "")

    # If already succeeded (synchronous path), use directly; otherwise poll.
    if create_resp.get("state") == "success":
        result = create_resp
    else:
        print(f"[vidu] tts task created: {task_id}", flush=True)
        result = poll_task(config, task_id, interval=poll_interval, max_wait=poll_max_wait)

    audio_url = result.get("file_url") or result.get("audio_url")
    actual_duration = float(duration_seconds or 10)

    return {
        "mode": "live",
        "model": "tts",
        "request_id": task_id,
        "audio_url": audio_url,
        "segments": [
            {"segment_id": "seg-1", "text": text, "start": 0.0, "end": actual_duration}
        ],
        "raw_response": result,
        "usage": {"credits": result.get("credits", 0), "mode": "live"},
    }


# ---------------------------------------------------------------------------
# BGM (background music) — POST /text2audio
# ---------------------------------------------------------------------------

def generate_bgm(
    config: ViduConfig,
    prompt: str,
    duration_seconds: int = 10,
    *,
    seed: int = 0,
    poll_interval: float = 5.0,
    poll_max_wait: float = 120.0,
) -> dict[str, Any]:
    """Generate background music via Vidu text2audio.

    ``duration_seconds`` must be 2-10.
    Returns {mode, model, request_id, audio_url, usage}.
    """
    duration = max(2, min(10, duration_seconds))

    if not config.api_key:
        return {
            "mode": "mock",
            "model": "audio1.0",
            "request_id": _stable_request_id("bgm", prompt),
            "audio_url": None,
            "raw_response": {"provider": "vidu", "mode": "mock"},
            "usage": {"credits": 0, "mode": "mock"},
        }

    payload: dict[str, Any] = {
        "model": "audio1.0",
        "prompt": prompt,
        "duration": duration,
    }
    if seed:
        payload["seed"] = seed

    create_resp = request_json(config, "POST", "/text2audio", payload=payload)
    task_id = create_resp.get("task_id", "")
    print(f"[vidu] bgm task created: {task_id}", flush=True)

    result = poll_task(config, task_id, interval=poll_interval, max_wait=poll_max_wait)
    audio_url = result.get("file_url") or result.get("audio_url")

    return {
        "mode": "live",
        "model": "audio1.0",
        "request_id": task_id,
        "audio_url": audio_url,
        "raw_response": result,
        "usage": {"credits": result.get("credits", 0), "mode": "live"},
    }


# ---------------------------------------------------------------------------
# Timed sound effects — POST /timing2audio
# ---------------------------------------------------------------------------

def generate_timed_audio(
    config: ViduConfig,
    timing_prompts: list[dict[str, Any]],
    duration_seconds: int = 10,
    *,
    seed: int = 0,
    poll_interval: float = 5.0,
    poll_max_wait: float = 120.0,
) -> dict[str, Any]:
    """Generate time-sequenced sound effects via Vidu timing2audio.

    Args:
        timing_prompts: List of timed events:
            [{"from": 0.0, "to": 2.5, "prompt": "thunder crack"}, ...]
            Overlapping events are supported.
        duration_seconds: Total audio length (2-10).

    Returns {mode, model, request_id, audio_url, timing_prompts, usage}.
    """
    duration = max(2, min(10, duration_seconds))

    if not config.api_key:
        return {
            "mode": "mock",
            "model": "audio1.0",
            "request_id": _stable_request_id("timed-audio", str(timing_prompts)),
            "audio_url": None,
            "timing_prompts": timing_prompts,
            "raw_response": {"provider": "vidu", "mode": "mock"},
            "usage": {"credits": 0, "mode": "mock"},
        }

    payload: dict[str, Any] = {
        "model": "audio1.0",
        "timing_prompts": timing_prompts,
        "duration": duration,
    }
    if seed:
        payload["seed"] = seed

    create_resp = request_json(config, "POST", "/timing2audio", payload=payload)
    task_id = create_resp.get("task_id", "")
    print(f"[vidu] timed-audio task created: {task_id}", flush=True)

    result = poll_task(config, task_id, interval=poll_interval, max_wait=poll_max_wait)
    audio_url = result.get("file_url") or result.get("audio_url")

    return {
        "mode": "live",
        "model": "audio1.0",
        "request_id": task_id,
        "audio_url": audio_url,
        "timing_prompts": timing_prompts,
        "raw_response": result,
        "usage": {"credits": result.get("credits", 0), "mode": "live"},
    }
