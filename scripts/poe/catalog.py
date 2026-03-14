from __future__ import annotations

from typing import Any

from .client import PoeConfig, request_json


RECOMMENDED_AUDIO_MODELS = [
    "elevenlabs-v3",
    "elevenlabs-v2.5-turbo",
    "sonic-3.0",
    "lyria",
]

RECOMMENDED_VIDEO_MODELS = [
    "veo-3.1",
    "veo-3.1-fast",
    "kling-2.1-pro",
    "kling-2.6-pro",
    "runway-gen-4.5",
    "sora-2",
    "sora-2-pro",
]

RECOMMENDED_IMAGE_MODELS = [
    "flux-schnell",
    "flux-pro-1.1-ultra",
    "imagen-4",
    "ideogram-v3",
]


def format_price_display(pricing: dict[str, Any] | None) -> str:
    if not pricing:
        return "Pricing not exposed in catalog"
    if pricing.get("request") is not None:
        return f"Request price: {pricing['request']}"
    prompt = pricing.get("prompt")
    completion = pricing.get("completion")
    if prompt is not None and completion is not None:
        return f"Token price: prompt={prompt}, completion={completion}"
    return "Pricing not exposed in catalog"


def _normalize_model(model: dict[str, Any], category: str, recommended: bool) -> dict[str, Any]:
    return {
        "id": model.get("id", ""),
        "owned_by": model.get("owned_by"),
        "category": category,
        "input_modalities": model.get("input_modalities", []),
        "output_modalities": model.get("output_modalities", []),
        "pricing": model.get("pricing"),
        "price_display": format_price_display(model.get("pricing")),
        "recommended": recommended,
        "last_observed_cost_points": None,
    }


def classify_media_models(models: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    audio: list[dict[str, Any]] = []
    image: list[dict[str, Any]] = []
    video: list[dict[str, Any]] = []
    for model in models:
        outputs = model.get("output_modalities", [])
        model_id = model.get("id", "")
        if "audio" in outputs:
            audio.append(_normalize_model(model, "audio", model_id in RECOMMENDED_AUDIO_MODELS))
        if "image" in outputs:
            image.append(_normalize_model(model, "image", model_id in RECOMMENDED_IMAGE_MODELS))
        if "video" in outputs:
            video.append(_normalize_model(model, "video", model_id in RECOMMENDED_VIDEO_MODELS))

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        return (0 if item["recommended"] else 1, item["id"])

    return {
        "audio": sorted(audio, key=sort_key),
        "image": sorted(image, key=sort_key),
        "video": sorted(video, key=sort_key),
    }


def fetch_media_catalog(config: PoeConfig) -> dict[str, list[dict[str, Any]]]:
    payload = request_json(config, "GET", "/models")
    raw_models = payload.get("data", [])
    normalized = []
    for model in raw_models:
        architecture = model.get("architecture") or {}
        normalized.append(
            {
                "id": model.get("id", ""),
                "owned_by": model.get("owned_by"),
                "input_modalities": architecture.get("input_modalities", []),
                "output_modalities": architecture.get("output_modalities", []),
                "pricing": model.get("pricing"),
            }
        )
    return classify_media_models(normalized)
