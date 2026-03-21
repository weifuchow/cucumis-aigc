from __future__ import annotations

from pathlib import Path
from typing import Any

from vidu.client import ViduConfig, load_vidu_config
import vidu.media as _media

from .base import MultimodalProvider


class ViduProvider(MultimodalProvider):
    """Multimodal provider backed by the Vidu platform.

    Vidu-specific options can be set at construction time as defaults and
    overridden per-call via ``**opts``.

    Args:
        config: ViduConfig with api_key and base_url.
        default_voice_id: Default TTS voice. Required for generate_audio.
        default_video_resolution: One of 540p / 720p / 1080p.
        poll_interval: Seconds between task status polls.
        poll_max_wait: Maximum seconds to wait for a task.
    """

    def __init__(
        self,
        config: ViduConfig,
        *,
        default_voice_id: str = "",
        default_video_resolution: str = "720p",
        poll_interval: float = 5.0,
        poll_max_wait: float = 600.0,
    ) -> None:
        self.config = config
        self.default_voice_id = default_voice_id
        self.default_video_resolution = default_video_resolution
        self.poll_interval = poll_interval
        self.poll_max_wait = poll_max_wait

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def generate_image(
        self,
        model: str,
        prompts: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_image(
            self.config,
            model,
            prompts,
            poll_interval=opts.get("poll_interval", self.poll_interval),
            poll_max_wait=opts.get("poll_max_wait", self.poll_max_wait),
        )

    def generate_video(
        self,
        model: str,
        scenes: list[dict[str, Any]],
        aspect_ratio: str,
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_video(
            self.config,
            model,
            scenes,
            aspect_ratio,
            resolution=opts.get("resolution", self.default_video_resolution),
            poll_interval=opts.get("poll_interval", self.poll_interval),
            poll_max_wait=opts.get("poll_max_wait", self.poll_max_wait),
        )

    def generate_audio(
        self,
        model: str,
        prompt: str,
        duration_seconds: int,
        language: str,
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate voiceover via Vidu TTS.

        ``model`` is ignored (Vidu uses a fixed TTS engine); pass any string.
        ``language`` is ignored at the API level but preserved for logging.
        ``opts`` may contain: voice_id, speed, volume, pitch, emotion.
        """
        voice_id = opts.get("voice_id") or self.default_voice_id
        return _media.generate_tts(
            self.config,
            prompt,
            voice_id,
            speed=opts.get("speed", 1.0),
            volume=opts.get("volume", 0),
            pitch=opts.get("pitch", 0),
            emotion=opts.get("emotion"),
            duration_seconds=duration_seconds,
            poll_interval=opts.get("poll_interval", self.poll_interval),
            poll_max_wait=opts.get("poll_max_wait", 120.0),
        )

    # ------------------------------------------------------------------
    # Extended (Vidu-only capabilities)
    # ------------------------------------------------------------------

    def generate_bgm(
        self,
        prompt: str,
        duration_seconds: int,
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_bgm(
            self.config,
            prompt,
            duration_seconds,
            seed=opts.get("seed", 0),
            poll_interval=opts.get("poll_interval", self.poll_interval),
            poll_max_wait=opts.get("poll_max_wait", 120.0),
        )

    def generate_timed_audio(
        self,
        timing_prompts: list[dict[str, Any]],
        duration_seconds: int,
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_timed_audio(
            self.config,
            timing_prompts,
            duration_seconds,
            seed=opts.get("seed", 0),
            poll_interval=opts.get("poll_interval", self.poll_interval),
            poll_max_wait=opts.get("poll_max_wait", 120.0),
        )

    def generate_multiframe_video(
        self,
        model: str,
        start_image: str,
        image_settings: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        return _media.generate_multiframe(
            self.config,
            model,
            start_image,
            image_settings,
            resolution=opts.get("resolution", self.default_video_resolution),
            poll_interval=opts.get("poll_interval", self.poll_interval),
            poll_max_wait=opts.get("poll_max_wait", self.poll_max_wait),
        )


def make_vidu_provider(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
) -> ViduProvider:
    """Load ViduProvider from environment / .env file.

    Reads:
      VIDU_API_KEY, VIDU_BASE_URL, VIDU_VOICE_ID, VIDU_VIDEO_RESOLUTION
    """
    import os

    def _dotenv(path: Path) -> dict[str, str]:
        if not path.is_file():
            return {}
        values: dict[str, str] = {}
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            values[k.strip()] = v.strip().strip("'").strip('"')
        return values

    from vidu.client import VIDU_BASE_URL
    resolved_path = env_path or Path(__file__).resolve().parents[2] / ".env"
    env_values = _dotenv(resolved_path)
    env_values.update(env or os.environ)

    config = load_vidu_config(env=env_values, env_path=env_path)
    return ViduProvider(
        config,
        default_voice_id=env_values.get("VIDU_VOICE_ID", ""),
        default_video_resolution=env_values.get("VIDU_VIDEO_RESOLUTION", "720p"),
    )
