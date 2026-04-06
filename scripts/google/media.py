from __future__ import annotations

import base64
import hashlib
import mimetypes
import pathlib
import re
import struct
import tempfile
from typing import Any

from .client import GoogleConfig, request_json, poll_operation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _stable_id(prefix: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def _encode_image(path: str) -> tuple[str, str] | None:
    """Return (base64_data, mime_type) for a local image file, or None."""
    p = pathlib.Path(path)
    if not p.is_file():
        return None
    mime = mimetypes.guess_type(path)[0] or "image/jpeg"
    data = base64.b64encode(p.read_bytes()).decode("utf-8")
    return data, mime


def _save_inline_image(b64_data: str, mime_type: str) -> str:
    """Save base64 image to a temp file; return file:// URL."""
    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    ext = ext_map.get(mime_type.split(";")[0].strip(), ".png")
    raw = base64.b64decode(b64_data)
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=ext, prefix="cucumis-google-img-"
    )
    tmp.write(raw)
    tmp.close()
    return f"file://{tmp.name}"


def _pcm_to_wav(pcm: bytes, sample_rate: int = 24000, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw PCM bytes in a WAV container."""
    data_size = len(pcm)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", data_size + 36, b"WAVE",
        b"fmt ", 16, 1, channels, sample_rate,
        sample_rate * channels * bits // 8, channels * bits // 8, bits,
        b"data", data_size,
    )
    return header + pcm


def _save_inline_audio(b64_data: str, mime_type: str) -> str:
    """Save base64 audio to a temp file; return file:// URL."""
    raw_mime = mime_type.split(";")[0].strip().lower()
    if raw_mime in ("audio/l16", "audio/pcm"):
        # Wrap in WAV
        pcm = base64.b64decode(b64_data)
        wav = _pcm_to_wav(pcm)
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=".wav", prefix="cucumis-google-tts-"
        )
        tmp.write(wav)
        tmp.close()
    else:
        ext_map = {"audio/mp3": ".mp3", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/ogg": ".ogg"}
        ext = ext_map.get(raw_mime, ".mp3")
        raw = base64.b64decode(b64_data)
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix=ext, prefix="cucumis-google-tts-"
        )
        tmp.write(raw)
        tmp.close()
    return f"file://{tmp.name}"


def _extract_http_urls(text: str) -> list[str]:
    if not text:
        return []
    raw = re.findall(r"https?://[^\s)>\"]+", text)
    seen: set[str] = set()
    urls: list[str] = []
    for u in raw:
        n = u.rstrip(".,]")
        if n and n not in seen:
            seen.add(n)
            urls.append(n)
    return urls


# ---------------------------------------------------------------------------
# Image — Gemini image generation
# ---------------------------------------------------------------------------

def generate_image(
    config: GoogleConfig,
    model: str,
    prompts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate images via Gemini image generation model.

    Gemini returns inline base64 image data; this function saves each image
    to a temp file and returns a file:// URL so downstream runners can
    process them without modification.
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
            "request_id": _stable_id("image", str(prompts)),
            "images": images,
            "raw_response": {"provider": "google", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    images: list[dict[str, Any]] = []
    request_ids: list[str] = []

    # Detect Imagen models (use :predict endpoint, different payload/response)
    _is_imagen = model.startswith("imagen-")

    for item in prompts:
        scene_id = str(item.get("scene_id", "scene"))
        prompt_id = str(item.get("prompt_id", ""))
        positive_prompt = item.get("positive_prompt", "")
        aspect_ratio = item.get("aspect_ratio", "9:16")

        print(f"[google] generating image for scene={scene_id} model={model}", flush=True)
        request_id = _stable_id("image", f"{model}:{positive_prompt}")
        image_url = ""

        if _is_imagen:
            # Imagen 4 API: POST /models/{model}:predict
            payload: dict[str, Any] = {
                "instances": [{"prompt": positive_prompt}],
                "parameters": {
                    "sampleCount": 1,
                    "aspectRatio": aspect_ratio,
                },
            }
            # Inject reference image if available
            ref_images = item.get("_ref_images") or []
            if ref_images:
                encoded = _encode_image(str(ref_images[0].get("path", "") if isinstance(ref_images[0], dict) else ref_images[0]))
                if encoded:
                    b64, mime = encoded
                    payload["instances"][0]["referenceImages"] = [
                        {"referenceType": "REFERENCE_TYPE_SUBJECT", "referenceImage": {"bytesBase64Encoded": b64, "mimeType": mime}}
                    ]

            response = request_json(
                config, "POST", f"/models/{model}:predict", payload=payload, timeout=180
            )
            for pred in response.get("predictions", []):
                b64 = pred.get("bytesBase64Encoded", "")
                mime = pred.get("mimeType", "image/png")
                if b64:
                    image_url = _save_inline_image(b64, mime)
                    print(f"[google] image saved → {image_url}", flush=True)
                    break
        else:
            # Gemini image generation: POST /models/{model}:generateContent
            # Retry up to 3 times with back-off — rate limits cause intermittent empty responses
            import time as _time
            for attempt in range(1, 4):
                if attempt > 1:
                    wait = attempt * 10
                    print(f"[google] waiting {wait}s before retry (attempt {attempt})…", flush=True)
                    _time.sleep(wait)
                content_parts: list[dict[str, Any]] = []
                for ref in (item.get("_ref_images") or [])[:4]:
                    encoded = _encode_image(str(ref.get("path", "") if isinstance(ref, dict) else ref))
                    if encoded:
                        b64, mime = encoded
                        content_parts.append({"inlineData": {"mimeType": mime, "data": b64}})
                content_parts.append({"text": positive_prompt})

                payload = {
                    "contents": [{"role": "user", "parts": content_parts}],
                    "generationConfig": {
                        "responseModalities": ["TEXT", "IMAGE"],
                    },
                }
                response = request_json(
                    config, "POST", f"/models/{model}:generateContent", payload=payload, timeout=300
                )
                for candidate in response.get("candidates", []):
                    for part in candidate.get("content", {}).get("parts", []):
                        if "inlineData" in part:
                            b64 = part["inlineData"].get("data", "")
                            mime = part["inlineData"].get("mimeType", "image/png")
                            if b64:
                                image_url = _save_inline_image(b64, mime)
                                print(f"[google] image saved → {image_url}", flush=True)
                                break
                        if "text" in part:
                            urls = _extract_http_urls(part["text"])
                            if urls:
                                image_url = urls[0]
                    if image_url:
                        break
                if image_url:
                    break
                print(f"[google] attempt {attempt} returned no image, retrying…", flush=True)

        request_ids.append(request_id)
        images.append({
            "scene_id": scene_id,
            "prompt_id": prompt_id,
            "url": image_url,
            "style": item.get("style"),
            "aspect_ratio": aspect_ratio,
            "request_id": request_id,
        })
        # Rate-limit: avoid hitting QPM limits on Gemini image models
        if not _is_imagen and len(prompts) > 1:
            import time as _time
            _time.sleep(5)

    return {
        "mode": "live",
        "model": model,
        "request_id": request_ids[-1] if request_ids else "",
        "request_ids": request_ids,
        "images": images,
        "raw_response": {"provider": "google"},
        "usage": {"cost_points": 0, "mode": "live", "note": "Google AI usage tracked via console"},
    }


# ---------------------------------------------------------------------------
# Video — Veo 2 (long-running operation)
# ---------------------------------------------------------------------------

def generate_video(
    config: GoogleConfig,
    model: str,
    scenes: list[dict[str, Any]],
    aspect_ratio: str,
) -> dict[str, Any]:
    """Generate video clips via Veo 3.1 Lite.

    Each scene is submitted as a separate long-running operation.
    Supports start-image keyframe via _ref_images[0].
    Resolution: 720p. Default duration: 6s.
    Note: Veo 3.1 Lite has no official generateAudio=False parameter;
    audio is generated by default and stripped during FFmpeg rendering.
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
            "request_id": _stable_id("video", str(scenes)),
            "clips": clips,
            "raw_response": {"provider": "google", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    # Veo 2 aspect ratio mapping
    veo_aspect = "9:16" if "9:16" in aspect_ratio or "portrait" in aspect_ratio else "16:9"

    clips: list[dict[str, Any]] = []

    for scene in scenes:
        scene_id = scene["scene_id"]
        duration = int(scene.get("duration_seconds", 6))
        # Veo 3.1 Lite supports 5–8 second clips; default 6s
        veo_duration = max(5, min(8, duration))
        prompt = scene.get("visual_description") or scene.get("motion_intent", "")

        instance: dict[str, Any] = {"prompt": prompt}

        # Attach keyframe images
        # _ref_images[0] → first frame (all Veo models)
        # _ref_images[1] → last frame  (veo-3.1-generate-preview only, NOT Lite)
        ref_images = scene.get("_ref_images") or []
        params: dict[str, Any] = {
            "aspectRatio": veo_aspect,
            "durationSeconds": veo_duration,
            # numberOfVideos: not supported by veo-3.1-lite; omit to use model default (1)
            "resolution": "720p",
        }

        if ref_images:
            first_ref = ref_images[0]
            path = str(first_ref.get("path", "") if isinstance(first_ref, dict) else first_ref)
            encoded = _encode_image(path)
            if encoded:
                b64, mime = encoded
                instance["image"] = {"bytesBase64Encoded": b64, "mimeType": mime}

        # Last frame: only supported by veo-3.1-generate-preview (non-Lite).
        # veo-3.1-lite-generate-preview does NOT support lastFrame.
        _is_lite = "lite" in model.lower()
        if len(ref_images) >= 2 and not _is_lite:
            last_ref = ref_images[1]
            path = str(last_ref.get("path", "") if isinstance(last_ref, dict) else last_ref)
            encoded = _encode_image(path)
            if encoded:
                b64, mime = encoded
                params["lastFrame"] = {"bytesBase64Encoded": b64, "mimeType": mime}
                print(f"[google] using last frame for scene={scene_id}", flush=True)

        payload: dict[str, Any] = {
            "instances": [instance],
            "parameters": params,
        }

        print(f"[google] submitting video job for scene={scene_id} model={model}", flush=True)
        response = request_json(
            config, "POST", f"/models/{model}:predictLongRunning", payload=payload, timeout=60
        )

        operation_name = response.get("name", "")
        video_url = ""

        if operation_name:
            print(f"[google] polling operation {operation_name}", flush=True)
            try:
                result = poll_operation(config, operation_name, max_wait=600, interval=10)
                resp_body = result.get("response", {})
                # Handle both response shapes from Google AI
                for key in ("generateVideoResponse", "predictResponse"):
                    samples = resp_body.get(key, {}).get("generatedSamples") or []
                    if samples:
                        video_url = samples[0].get("video", {}).get("uri", "")
                        break
                # Fallback: predictions list (Vertex-style)
                if not video_url:
                    for pred in resp_body.get("predictions", []):
                        uri = pred.get("video", {}).get("uri") or pred.get("uri", "")
                        if uri:
                            video_url = uri
                            break
                print(f"[google] video url={video_url or '(empty)'}", flush=True)
            except TimeoutError as exc:
                print(f"[google] {exc}", flush=True)

        clips.append({
            "scene_id": scene_id,
            "duration_seconds": duration,
            "url": video_url,
            "motion_intent": scene.get("motion_intent"),
            "operation_name": operation_name,
        })

    return {
        "mode": "live",
        "model": model,
        "request_id": _stable_id("video", str(scenes)),
        "clips": clips,
        "raw_response": {"provider": "google"},
        "usage": {"cost_points": 0, "mode": "live", "note": "Google AI usage tracked via console"},
    }


# ---------------------------------------------------------------------------
# Audio — Gemini TTS
# ---------------------------------------------------------------------------

def generate_audio(
    config: GoogleConfig,
    model: str,
    prompt: str,
    duration_seconds: int,
    language: str,
) -> dict[str, Any]:
    """Generate TTS voiceover via Gemini TTS model.

    Returns a file:// URL pointing to a temp WAV/MP3 file.
    """
    if not config.api_key:
        return {
            "mode": "mock",
            "model": model,
            "request_id": _stable_id("audio", f"{model}:{prompt}"),
            "audio_url": None,
            "segments": [
                {"segment_id": "seg-1", "text": prompt[:60], "start": 0.0, "end": float(duration_seconds)}
            ],
            "raw_response": {"provider": "google", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    # Language → Gemini voice name mapping
    voice_map = {
        "zh": "Kore",
        "zh-CN": "Kore",
        "zh-TW": "Aoede",
        "en": "Puck",
        "ja": "Charon",
        "ko": "Fenrir",
    }
    voice_name = voice_map.get(language, voice_map.get(language.split("-")[0], "Kore"))

    payload: dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {
                "voiceConfig": {
                    "prebuiltVoiceConfig": {"voiceName": voice_name}
                }
            },
        },
    }

    print(f"[google] generating TTS voice={voice_name} model={model}", flush=True)
    response = request_json(
        config, "POST", f"/models/{model}:generateContent", payload=payload, timeout=180
    )

    request_id = _stable_id("audio", f"{model}:{prompt}")
    audio_url: str | None = None

    for candidate in response.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "inlineData" in part:
                b64 = part["inlineData"].get("data", "")
                mime = part["inlineData"].get("mimeType", "audio/L16")
                if b64:
                    audio_url = _save_inline_audio(b64, mime)
                    print(f"[google] TTS audio saved → {audio_url}", flush=True)
                    break
        if audio_url:
            break

    return {
        "mode": "live",
        "model": model,
        "request_id": request_id,
        "audio_url": audio_url,
        "segments": [
            {"segment_id": "seg-1", "text": prompt, "start": 0.0, "end": float(duration_seconds)}
        ],
        "raw_response": {"provider": "google", "has_audio": bool(audio_url)},
        "usage": {"cost_points": 0, "mode": "live"},
    }
