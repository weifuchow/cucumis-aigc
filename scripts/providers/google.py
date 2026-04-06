from __future__ import annotations

from pathlib import Path
from typing import Any

from google.client import GoogleConfig, load_google_config
import google.media as _gmedia

from elevenlabs.client import ElevenLabsConfig, load_elevenlabs_config
import elevenlabs.media as _elmedia

from .base import MultimodalProvider


class GoogleProvider(MultimodalProvider):
    """Multimodal provider backed by Google AI (Gemini + Veo 2).

    Audio routing:
      - If ELEVENLABS_API_KEY is present → ElevenLabs TTS (higher quality)
      - Otherwise → Gemini TTS (included in Google AI Pro)

    Image:  Gemini image generation (gemini-2.0-flash-preview-image-generation)
    Video:  Veo 2 (veo-2.0-generate-001) — no audio, supports keyframe conditioning
    """

    def __init__(self, config: GoogleConfig, el_config: ElevenLabsConfig) -> None:
        self.config = config
        self.el_config = el_config

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def generate_image(
        self,
        model: str,
        prompts: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        return _gmedia.generate_image(self.config, model, prompts)

    def generate_video(
        self,
        model: str,
        scenes: list[dict[str, Any]],
        aspect_ratio: str,
        **opts: Any,
    ) -> dict[str, Any]:
        return _gmedia.generate_video(self.config, model, scenes, aspect_ratio)

    def generate_audio(
        self,
        model: str,
        prompt: str,
        duration_seconds: int,
        language: str,
        **opts: Any,
    ) -> dict[str, Any]:
        # Prefer ElevenLabs when API key is available
        if self.el_config.api_key:
            return _elmedia.generate_tts(
                self.el_config,
                prompt=prompt,
                duration_seconds=duration_seconds,
                language=language,
            )
        # Fall back to Gemini TTS
        return _gmedia.generate_audio(
            self.config, self.config.tts_model, prompt, duration_seconds, language
        )

    # ------------------------------------------------------------------
    # Default model IDs (used by runners when no explicit model is given)
    # ------------------------------------------------------------------

    @property
    def default_image_model(self) -> str:
        return self.config.image_model

    @property
    def default_video_model(self) -> str:
        return self.config.video_model

    @property
    def default_audio_model(self) -> str:
        return "eleven_multilingual_v2" if self.el_config.api_key else self.config.tts_model


def make_google_provider(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
    **_ignored: object,
) -> GoogleProvider:
    g_config = load_google_config(env=env, env_path=env_path)
    el_config = load_elevenlabs_config(env=env, env_path=env_path)

    audio_backend = "elevenlabs" if el_config.api_key else "gemini-tts"
    print(
        f"[google] image={g_config.image_model}  video={g_config.video_model}  audio={audio_backend}",
        flush=True,
    )
    return GoogleProvider(g_config, el_config)
