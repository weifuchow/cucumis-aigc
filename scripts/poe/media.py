from __future__ import annotations

import hashlib
from typing import Any

from .client import PoeConfig, request_json


def _stable_request_id(prefix: str, model: str, prompt: str) -> str:
    digest = hashlib.sha1(f"{model}:{prompt}".encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(str(item.get("text", "")))
                elif "text" in item:
                    parts.append(str(item["text"]))
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(part for part in parts if part)
    return ""


def generate_audio(
    config: PoeConfig,
    model: str,
    prompt: str,
    duration_seconds: int,
    language: str,
) -> dict[str, Any]:
    if not config.api_key:
        segment_duration = round(max(duration_seconds, 1) / 2, 2)
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_request_id("audio", model, prompt),
            "segments": [
                {"segment_id": "seg-1", "text": prompt[:40] or "mock narration", "start": 0.0, "end": segment_duration},
                {
                    "segment_id": "seg-2",
                    "text": f"{language} continuation",
                    "start": segment_duration,
                    "end": round(segment_duration * 2, 2),
                },
            ],
            "raw_response": {"provider": "poe", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    response = request_json(
        config,
        "POST",
        "/chat/completions",
        payload={
            "model": model,
            "stream": False,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
        },
    )
    choice = ((response.get("choices") or [{}])[0]).get("message", {})
    content = _extract_text_content(choice.get("content"))
    return {
        "mode": "live",
        "model": model,
        "request_id": response.get("id", _stable_request_id("audio", model, prompt)),
        "segments": [
            {
                "segment_id": "seg-1",
                "text": content or prompt,
                "start": 0.0,
                "end": float(duration_seconds),
            }
        ],
        "raw_response": {
            "id": response.get("id"),
            "content": content,
        },
        "usage": {
            "cost_points": ((response.get("usage") or {}).get("total_tokens")),
            "mode": "live",
        },
    }


def generate_video(
    config: PoeConfig,
    model: str,
    scenes: list[dict[str, Any]],
    aspect_ratio: str,
) -> dict[str, Any]:
    if not config.api_key:
        clips = []
        for scene in scenes:
            scene_id = scene["scene_id"]
            clips.append(
                {
                    "scene_id": scene_id,
                    "duration_seconds": scene["duration_seconds"],
                    "url": f"mock://video/{scene_id}.mp4",
                    "motion_intent": scene.get("motion_intent"),
                }
            )
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_request_id("video", model, str(scenes)),
            "clips": clips,
            "raw_response": {"provider": "poe", "mode": "mock", "aspect_ratio": aspect_ratio},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    prompt = "\n".join(
        f"{scene['scene_id']}: {scene['visual_description']} ({scene['duration_seconds']}s, {scene.get('motion_intent', 'mixed')})"
        for scene in scenes
    )
    response = request_json(
        config,
        "POST",
        "/chat/completions",
        payload={
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": f"Aspect ratio {aspect_ratio}\n{prompt}"}],
        },
    )
    clips = []
    for scene in scenes:
        clips.append(
            {
                "scene_id": scene["scene_id"],
                "duration_seconds": scene["duration_seconds"],
                "url": f"poe://{response.get('id', 'video')}/{scene['scene_id']}",
                "motion_intent": scene.get("motion_intent"),
            }
        )
    return {
        "mode": "live",
        "model": model,
        "request_id": response.get("id", _stable_request_id("video", model, prompt)),
        "clips": clips,
        "raw_response": {"id": response.get("id")},
        "usage": {
            "cost_points": ((response.get("usage") or {}).get("total_tokens")),
            "mode": "live",
        },
    }


def generate_image(
    config: PoeConfig,
    model: str,
    prompts: list[dict[str, Any]],
) -> dict[str, Any]:
    if not config.api_key:
        images = []
        for prompt in prompts:
            scene_id = str(prompt.get("scene_id", "scene"))
            images.append(
                {
                    "scene_id": scene_id,
                    "prompt_id": str(prompt.get("prompt_id", "")),
                    "url": f"mock://image/{scene_id}.png",
                    "style": prompt.get("style"),
                    "aspect_ratio": prompt.get("aspect_ratio"),
                }
            )
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_request_id("image", model, str(prompts)),
            "images": images,
            "raw_response": {"provider": "poe", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    prompt = "\n".join(
        (
            f"{item.get('scene_id', 'scene')}: "
            f"{item.get('positive_prompt', '')} | "
            f"negative: {item.get('negative_prompt', '')} | "
            f"style: {item.get('style', '')} | "
            f"aspect: {item.get('aspect_ratio', '')}"
        )
        for item in prompts
    )
    response = request_json(
        config,
        "POST",
        "/chat/completions",
        payload={
            "model": model,
            "stream": False,
            "messages": [{"role": "user", "content": f"Generate image assets for:\n{prompt}"}],
        },
    )
    images = []
    for item in prompts:
        scene_id = str(item.get("scene_id", "scene"))
        images.append(
            {
                "scene_id": scene_id,
                "prompt_id": str(item.get("prompt_id", "")),
                "url": f"poe://{response.get('id', 'image')}/{scene_id}.png",
                "style": item.get("style"),
                "aspect_ratio": item.get("aspect_ratio"),
            }
        )
    return {
        "mode": "live",
        "model": model,
        "request_id": response.get("id", _stable_request_id("image", model, prompt)),
        "images": images,
        "raw_response": {"id": response.get("id")},
        "usage": {
            "cost_points": ((response.get("usage") or {}).get("total_tokens")),
            "mode": "live",
        },
    }
