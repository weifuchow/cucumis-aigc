"""ViduWebProvider — MultimodalProvider backed by Playwright browser automation.

Drop-in replacement for ViduProvider when you have a Vidu consumer membership
(no API access). Uses the Vidu web UI + network interception instead of direct
API calls. The ``MultimodalProvider`` interface is identical.

Configure via .env::

    MEDIA_PROVIDER=vidu_web
    VIDU_WEB_HEADLESS=true          # default: true (set false to watch the browser)
    VIDU_WEB_COOKIES_PATH=/path/...  # default: ~/.config/cucumis/vidu_web_session.json
    VIDU_WEB_POLL_INTERVAL=5.0
    VIDU_WEB_POLL_MAX_WAIT=600.0

First run:
    The browser opens a visible window (regardless of VIDU_WEB_HEADLESS) so you
    can log in manually. Cookies are saved and reused in subsequent runs.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import MultimodalProvider


class ViduWebProvider(MultimodalProvider):
    """Multimodal provider using Playwright to drive the Vidu web UI.

    Each generation call opens / reuses a browser session, navigates to the
    appropriate page, triggers generation, intercepts the internal API
    response, and returns a result dict in the standard provider format.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        cookies_path: Path | None = None,
        output_dir: Path | None = None,
        poll_interval: float = 5.0,
        poll_max_wait: float = 600.0,
        default_video_resolution: str = "720p",
    ) -> None:
        self.headless = headless
        self.cookies_path = cookies_path
        self.output_dir = output_dir
        self.poll_interval = poll_interval
        self.poll_max_wait = poll_max_wait
        self.default_video_resolution = default_video_resolution

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------

    def generate_image(
        self,
        model: str,
        prompts: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        from vidu_web.image_gen import generate_image
        from vidu_web.session import ViduWebSession

        output_dir = opts.get("output_dir", self.output_dir)
        with ViduWebSession(headless=self.headless, cookies_path=self.cookies_path) as session:
            return generate_image(
                session,
                model,
                prompts,
                output_dir=output_dir,
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
        from vidu_web.video_gen import generate_video
        from vidu_web.session import ViduWebSession

        output_dir = opts.get("output_dir", self.output_dir)
        with ViduWebSession(headless=self.headless, cookies_path=self.cookies_path) as session:
            return generate_video(
                session,
                model,
                scenes,
                aspect_ratio,
                resolution=opts.get("resolution", self.default_video_resolution),
                output_dir=output_dir,
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
        from vidu_web.audio_gen import generate_tts
        from vidu_web.session import ViduWebSession

        with ViduWebSession(headless=self.headless, cookies_path=self.cookies_path) as session:
            return generate_tts(
                session,
                prompt,
                voice_id=opts.get("voice_id", ""),
                duration_seconds=duration_seconds,
                poll_interval=opts.get("poll_interval", self.poll_interval),
                poll_max_wait=opts.get("poll_max_wait", 120.0),
            )

    # ------------------------------------------------------------------
    # Extended (Vidu-only)
    # ------------------------------------------------------------------

    def generate_bgm(
        self,
        prompt: str,
        duration_seconds: int,
        **opts: Any,
    ) -> dict[str, Any]:
        from vidu_web.audio_gen import generate_bgm
        from vidu_web.session import ViduWebSession

        with ViduWebSession(headless=self.headless, cookies_path=self.cookies_path) as session:
            return generate_bgm(
                session,
                prompt,
                duration_seconds,
                poll_interval=opts.get("poll_interval", self.poll_interval),
                poll_max_wait=opts.get("poll_max_wait", 120.0),
            )


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------

def make_vidu_web_provider(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
) -> ViduWebProvider:
    """Load ViduWebProvider from environment / .env file.

    Reads:
      VIDU_WEB_HEADLESS, VIDU_WEB_COOKIES_PATH,
      VIDU_WEB_POLL_INTERVAL, VIDU_WEB_POLL_MAX_WAIT,
      VIDU_VIDEO_RESOLUTION
    """

    def _bool(val: str) -> bool:
        return val.strip().lower() not in ("0", "false", "no", "off")

    cfg = dict(env or {})

    cookies_raw = cfg.get("VIDU_WEB_COOKIES_PATH", "").strip()
    cookies_path = Path(cookies_raw) if cookies_raw else None

    output_raw = cfg.get("VIDU_WEB_OUTPUT_DIR", "").strip()
    output_dir = Path(output_raw) if output_raw else None

    return ViduWebProvider(
        headless=_bool(cfg.get("VIDU_WEB_HEADLESS", "true")),
        cookies_path=cookies_path,
        output_dir=output_dir,
        poll_interval=float(cfg.get("VIDU_WEB_POLL_INTERVAL", "5.0")),
        poll_max_wait=float(cfg.get("VIDU_WEB_POLL_MAX_WAIT", "600.0")),
        default_video_resolution=cfg.get("VIDU_VIDEO_RESOLUTION", "720p"),
    )
