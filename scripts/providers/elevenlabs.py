from __future__ import annotations

from pathlib import Path
from typing import Any

from elevenlabs.client import ElevenLabsConfig, load_elevenlabs_config
import elevenlabs.media as _media

from .base import MultimodalProvider


class ElevenLabsProvider(MultimodalProvider):
    """Audio-only provider backed by ElevenLabs TTS.

    Image and video generation are not supported — use alongside another
    provider (e.g. set MEDIA_PROVIDER=google and let GoogleProvider route
    audio to ElevenLabs automatically).
    """

    def __init__(self, config: ElevenLabsConfig) -> None:
        self.config = config

    def generate_image(self, model: str, prompts: list[dict[str, Any]], **opts: Any) -> dict[str, Any]:
        raise NotImplementedError("ElevenLabsProvider does not support image generation")

    def generate_video(
        self,
        model: str,
        scenes: list[dict[str, Any]],
        aspect_ratio: str,
        **opts: Any,
    ) -> dict[str, Any]:
        raise NotImplementedError("ElevenLabsProvider does not support video generation")

    def generate_audio(
        self,
        model: str,
        prompt: str,
        duration_seconds: int,
        language: str,
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_tts(
            self.config,
            prompt=prompt,
            duration_seconds=duration_seconds,
            language=language,
            model_id=model,
        )


def make_elevenlabs_provider(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
    **_ignored: object,
) -> ElevenLabsProvider:
    config = load_elevenlabs_config(env=env, env_path=env_path)
    return ElevenLabsProvider(config)
