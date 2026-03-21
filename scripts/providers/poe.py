from __future__ import annotations

from pathlib import Path
from typing import Any

from poe.client import PoeConfig, load_poe_config
import poe.media as _media

from .base import MultimodalProvider


class PoeProvider(MultimodalProvider):
    """Multimodal provider backed by the Poe platform."""

    def __init__(self, config: PoeConfig) -> None:
        self.config = config

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def generate_image(
        self,
        model: str,
        prompts: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_image(self.config, model, prompts)

    def generate_video(
        self,
        model: str,
        scenes: list[dict[str, Any]],
        aspect_ratio: str,
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_video(self.config, model, scenes, aspect_ratio)

    def generate_audio(
        self,
        model: str,
        prompt: str,
        duration_seconds: int,
        language: str,
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_audio(self.config, model, prompt, duration_seconds, language)


def make_poe_provider(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
    **_ignored: object,
) -> PoeProvider:
    return PoeProvider(load_poe_config(env=env, env_path=env_path))
