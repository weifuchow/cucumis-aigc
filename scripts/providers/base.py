from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class MultimodalProvider(ABC):
    """Abstract base for multimodal generation providers (Poe, Vidu, …).

    All methods return a dict that follows the unified response schema:

    generate_image → {mode, model, request_id, images: [{scene_id, url, ...}], usage}
    generate_video → {mode, model, request_id, clips:  [{scene_id, url, duration_seconds, ...}], usage}
    generate_audio → {mode, model, request_id, audio_url, segments: [{segment_id, text, start, end}], usage}

    The ``usage`` dict always contains at least one cost field:
      - cost_points  (Poe)
      - credits      (Vidu)
    """

    # ------------------------------------------------------------------
    # Core — every provider must implement these three
    # ------------------------------------------------------------------

    @abstractmethod
    def generate_image(
        self,
        model: str,
        prompts: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate images from text prompts with optional reference images.

        ``prompts`` shape (same as poe/media.py):
          [{"scene_id": ..., "prompt_id": ..., "positive_prompt": ...,
            "negative_prompt": ..., "aspect_ratio": ...,
            "_ref_images": [{"path": "..."}]}]
        """

    @abstractmethod
    def generate_video(
        self,
        model: str,
        scenes: list[dict[str, Any]],
        aspect_ratio: str,
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate video clips for a list of scenes.

        ``scenes`` shape (same as poe/media.py):
          [{"scene_id": ..., "duration_seconds": ..., "visual_description": ...,
            "motion_intent": ..., "_ref_images": [...]}]
        """

    @abstractmethod
    def generate_audio(
        self,
        model: str,
        prompt: str,
        duration_seconds: int,
        language: str,
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate a voiceover / narration audio track.

        Returns unified shape:
          {audio_url, segments: [{segment_id, text, start, end}], usage}
        """

    # ------------------------------------------------------------------
    # Extended — providers may override; default raises NotImplementedError
    # ------------------------------------------------------------------

    def generate_bgm(
        self,
        prompt: str,
        duration_seconds: int,
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate background music. Not all providers support this."""
        raise NotImplementedError(f"{type(self).__name__} does not support generate_bgm")

    def generate_timed_audio(
        self,
        timing_prompts: list[dict[str, Any]],
        duration_seconds: int,
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate time-sequenced sound effects. Not all providers support this."""
        raise NotImplementedError(f"{type(self).__name__} does not support generate_timed_audio")

    def generate_multiframe_video(
        self,
        model: str,
        start_image: str,
        image_settings: list[dict[str, Any]],
        **opts: Any,
    ) -> dict[str, Any]:
        """Generate video from ordered keyframes. Not all providers support this."""
        raise NotImplementedError(f"{type(self).__name__} does not support generate_multiframe_video")

    # ------------------------------------------------------------------
    # Capability introspection
    # ------------------------------------------------------------------

    def supports(self, capability: str) -> bool:
        """Return True if this provider supports an extended capability.

        Known capability strings:
          "bgm", "timed_audio", "multiframe_video"
        """
        method_name = {
            "bgm": "generate_bgm",
            "timed_audio": "generate_timed_audio",
            "multiframe_video": "generate_multiframe_video",
        }.get(capability)
        if method_name is None:
            return False
        # Supported if any concrete subclass (not MultimodalProvider itself) overrides the method
        return any(
            method_name in cls.__dict__
            for cls in type(self).__mro__
            if cls is not MultimodalProvider
        )
