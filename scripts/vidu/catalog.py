from __future__ import annotations

from typing import Any


# ---------------------------------------------------------------------------
# Static model catalog — Vidu platform (as of 2026-02)
# ---------------------------------------------------------------------------

# Image generation models
IMAGE_MODELS: list[dict[str, Any]] = [
    {
        "id": "viduq2",
        "category": "image",
        "description": "ViduQ2 — text-to-image, image editing, reference generation",
        "aspect_ratios": ["16:9", "9:16", "1:1", "3:4", "4:3", "21:9", "2:3", "3:2", "auto"],
        "resolutions": ["1080p", "2K", "4K"],
        "max_ref_images": 7,
        "recommended": True,
    },
    {
        "id": "viduq1",
        "category": "image",
        "description": "ViduQ1 — reference image generation (requires ≥1 ref image)",
        "aspect_ratios": ["16:9", "9:16", "1:1", "3:4", "4:3"],
        "resolutions": ["1080p"],
        "max_ref_images": 7,
        "min_ref_images": 1,
        "recommended": False,
    },
]

# Video generation models
VIDEO_MODELS: list[dict[str, Any]] = [
    {
        "id": "viduq3-turbo",
        "category": "video",
        "description": "ViduQ3 Turbo — fastest generation, stable quality",
        "max_duration_seconds": 16,
        "resolutions": ["540p", "720p", "1080p"],
        "endpoints": ["text2video", "img2video"],
        "features": ["audio_sync", "bgm"],
        "recommended": True,
    },
    {
        "id": "viduq3-pro",
        "category": "video",
        "description": "ViduQ3 Pro — highest quality, first-and-last-frame support",
        "max_duration_seconds": 16,
        "resolutions": ["540p", "720p", "1080p"],
        "endpoints": ["text2video", "img2video", "multiframe"],
        "features": ["audio_sync", "bgm"],
        "recommended": True,
    },
    {
        "id": "viduq2",
        "category": "video",
        "description": "ViduQ2 — balanced quality/speed, multi-frame & extension support",
        "max_duration_seconds": 10,
        "resolutions": ["540p", "720p", "1080p"],
        "endpoints": ["text2video", "img2video", "multiframe", "extend"],
        "recommended": False,
    },
    {
        "id": "viduq2-turbo",
        "category": "video",
        "description": "ViduQ2 Turbo — faster Q2 variant",
        "max_duration_seconds": 10,
        "resolutions": ["540p", "720p", "1080p"],
        "endpoints": ["text2video", "img2video", "multiframe", "extend"],
        "recommended": False,
    },
    {
        "id": "viduq2-pro",
        "category": "video",
        "description": "ViduQ2 Pro — higher-quality Q2 variant",
        "max_duration_seconds": 10,
        "resolutions": ["540p", "720p", "1080p"],
        "endpoints": ["text2video", "img2video", "multiframe", "extend"],
        "recommended": False,
    },
    {
        "id": "viduq1",
        "category": "video",
        "description": "ViduQ1 — legacy 5-second model",
        "max_duration_seconds": 5,
        "resolutions": ["720p", "1080p"],
        "endpoints": ["text2video", "img2video"],
        "recommended": False,
    },
]

# Audio models
AUDIO_MODELS: list[dict[str, Any]] = [
    {
        "id": "audio1.0",
        "category": "audio",
        "description": "Vidu Audio 1.0 — BGM and timed sound effect generation",
        "max_duration_seconds": 10,
        "endpoints": ["text2audio", "timing2audio"],
        "recommended": True,
    },
    {
        "id": "tts",
        "category": "audio",
        "description": "Vidu TTS — text-to-speech with emotion and pause control",
        "max_text_chars": 10000,
        "endpoints": ["audio-tts"],
        "emotions": ["happy", "sad", "angry", "fearful", "disgusted", "surprised", "calm"],
        "recommended": True,
    },
]

# Convenience lookups
_ALL_MODELS: dict[str, dict[str, Any]] = {
    m["id"]: m
    for m in IMAGE_MODELS + VIDEO_MODELS + AUDIO_MODELS
}

RECOMMENDED_IMAGE_MODEL = "viduq2"
RECOMMENDED_VIDEO_MODEL = "viduq3-turbo"
RECOMMENDED_AUDIO_MODEL = "audio1.0"
RECOMMENDED_TTS_MODEL = "tts"


def get_model(model_id: str) -> dict[str, Any] | None:
    return _ALL_MODELS.get(model_id)


def list_models(category: str | None = None) -> list[dict[str, Any]]:
    all_models = IMAGE_MODELS + VIDEO_MODELS + AUDIO_MODELS
    if category:
        return [m for m in all_models if m["category"] == category]
    return all_models
