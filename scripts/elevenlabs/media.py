from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path
from typing import Any

from .client import ElevenLabsConfig, request_binary


# ElevenLabs model IDs
# eleven_multilingual_v2     — highest quality, 29 languages incl. Chinese/Japanese/Korean
# eleven_turbo_v2_5          — low latency, good quality
# eleven_flash_v2_5          — fastest, cost-efficient
RECOMMENDED_MODEL = "eleven_v3"

# Language → recommended voice (multilingual voices work across all languages)
# These are public voice IDs available in the ElevenLabs voice library.
LANG_VOICE_MAP = {
    "zh": "9lHjugDhwqoxA5MhX0az",     # Chinese voice
    "zh-CN": "9lHjugDhwqoxA5MhX0az",
    "zh-TW": "9lHjugDhwqoxA5MhX0az",
    "en": "21m00Tcm4TlvDq8ikWAM",   # "Rachel" — clear English
    "ja": "XB0fDUnXU5powFXDhCwa",   # "Charlotte"
    "ko": "AZnzlk1XvdvUeBnXmlld",   # "Domi"
}


def _stable_id(prefix: str, key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def generate_sound_effect(
    config: ElevenLabsConfig,
    text: str,
    duration_seconds: float | None = None,
    prompt_influence: float = 0.3,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate BGM / sound effect via ElevenLabs Sound Generation API.

    Endpoint: POST /v1/sound-generation
    - text: English description recommended, max 500 chars
    - duration_seconds: optional, max 22.0; omit to let ElevenLabs auto-determine
    - prompt_influence: 0.0–1.0, how closely to follow the text (default 0.3)

    Returns dict with keys: mode, model, request_id, audio_url (file://...), usage
    """
    if not config.api_key:
        # Mock mode: write silence placeholder
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            # Write a minimal valid file marker (not real audio, for mock only)
            output_path.write_bytes(b"")
        return {
            "mode": "mock",
            "model": "elevenlabs-sound-generation",
            "request_id": _stable_id("sfx", text),
            "audio_url": f"file://{output_path}" if output_path else None,
            "duration_seconds": duration_seconds,
            "raw_response": {"provider": "elevenlabs", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    payload: dict[str, Any] = {
        "text": text[:500],
        "prompt_influence": prompt_influence,
    }
    if duration_seconds is not None:
        payload["duration_seconds"] = min(float(duration_seconds), 22.0)

    print(
        f"[elevenlabs] sound-generation len={len(text)} dur={duration_seconds}s",
        flush=True,
    )
    audio_bytes = request_binary(config, "POST", "/sound-generation", payload=payload)

    dest = output_path or Path(
        tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp3", prefix="cucumis-el-sfx-"
        ).name
    )
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(audio_bytes)
    audio_url = f"file://{dest}"
    print(f"[elevenlabs] sound saved → {audio_url}", flush=True)

    return {
        "mode": "live",
        "model": "elevenlabs-sound-generation",
        "request_id": _stable_id("sfx", text),
        "audio_url": audio_url,
        "duration_seconds": duration_seconds,
        "raw_response": {"provider": "elevenlabs", "bytes": len(audio_bytes)},
        "usage": {
            "cost_points": len(text),
            "mode": "live",
            "note": "ElevenLabs sound generation charges per character",
        },
    }


def generate_tts(
    config: ElevenLabsConfig,
    prompt: str,
    duration_seconds: int,
    language: str,
    *,
    model_id: str = RECOMMENDED_MODEL,
    stability: float = 0.5,
    similarity_boost: float = 0.75,
    style: float = 0.0,
) -> dict[str, Any]:
    """Generate voiceover via ElevenLabs TTS.

    Returns a dict compatible with the unified audio response schema:
      {mode, model, request_id, audio_url (file://...), segments, usage}
    """
    if not config.api_key:
        return {
            "mode": "mock",
            "model": model_id,
            "request_id": _stable_id("tts", prompt),
            "audio_url": None,
            "segments": [
                {"segment_id": "seg-1", "text": prompt[:60], "start": 0.0, "end": float(duration_seconds)}
            ],
            "raw_response": {"provider": "elevenlabs", "mode": "mock"},
            "usage": {"cost_points": 0, "mode": "mock"},
        }

    # Pick voice based on language, fall back to config default
    lang_key = language if language in LANG_VOICE_MAP else language.split("-")[0]
    voice_id = LANG_VOICE_MAP.get(lang_key, config.default_voice_id)

    payload: dict[str, Any] = {
        "text": prompt,
        "model_id": model_id,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        },
    }

    print(f"[elevenlabs] TTS voice={voice_id} model={model_id} lang={language}", flush=True)
    audio_bytes = request_binary(
        config, "POST",
        f"/text-to-speech/{voice_id}",
        payload=payload,
    )

    # Save MP3 to temp file
    tmp = tempfile.NamedTemporaryFile(
        delete=False, suffix=".mp3", prefix="cucumis-el-tts-"
    )
    tmp.write(audio_bytes)
    tmp.close()
    audio_url = f"file://{tmp.name}"
    print(f"[elevenlabs] audio saved → {audio_url}", flush=True)

    request_id = _stable_id("tts", f"{voice_id}:{prompt}")
    return {
        "mode": "live",
        "model": model_id,
        "request_id": request_id,
        "audio_url": audio_url,
        "segments": [
            {"segment_id": "seg-1", "text": prompt, "start": 0.0, "end": float(duration_seconds)}
        ],
        "raw_response": {"provider": "elevenlabs", "voice_id": voice_id, "bytes": len(audio_bytes)},
        "usage": {"cost_points": len(prompt), "mode": "live", "note": "ElevenLabs charges per character"},
    }
