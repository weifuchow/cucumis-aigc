import pathlib
import sys
import unittest


REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from poe.catalog import classify_media_models, format_price_display
from poe.client import PoeConfig, load_poe_config
from poe.media import generate_audio, generate_video


class PoeSdkTest(unittest.TestCase):
    def test_load_poe_config_reads_environment_defaults(self) -> None:
        env = {
            "POE_API_KEY": "test-key",
        }
        config = load_poe_config(env=env)
        self.assertEqual(config.api_key, "test-key")
        self.assertEqual(config.base_url, "https://api.poe.com/v1")

    def test_classify_media_models_sorts_recommended_entries_first(self) -> None:
        models = [
            {
                "id": "kling-2.1-pro",
                "owned_by": "fal",
                "input_modalities": ["text"],
                "output_modalities": ["video"],
                "pricing": None,
            },
            {
                "id": "unknown-audio",
                "owned_by": "custom",
                "input_modalities": ["text"],
                "output_modalities": ["audio"],
                "pricing": {"request": "0.0040"},
            },
            {
                "id": "elevenlabs-v3",
                "owned_by": "ElevenLabs",
                "input_modalities": ["text"],
                "output_modalities": ["audio"],
                "pricing": None,
            },
        ]

        catalog = classify_media_models(models)
        self.assertEqual(catalog["audio"][0]["id"], "elevenlabs-v3")
        self.assertEqual(catalog["video"][0]["id"], "kling-2.1-pro")
        self.assertEqual(catalog["audio"][1]["price_display"], "Request price: 0.0040")

    def test_format_price_display_handles_missing_and_request_pricing(self) -> None:
        self.assertEqual(format_price_display(None), "Pricing not exposed in catalog")
        self.assertEqual(
            format_price_display({"request": "0.0060"}),
            "Request price: 0.0060",
        )

    def test_generate_audio_without_api_key_returns_mock_response(self) -> None:
        config = PoeConfig(api_key="", base_url="https://api.poe.com/v1")
        result = generate_audio(
            config=config,
            model="elevenlabs-v3",
            prompt="测试旁白",
            duration_seconds=6,
            language="中文",
        )
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["model"], "elevenlabs-v3")
        self.assertTrue(result["segments"])

    def test_generate_video_without_api_key_returns_mock_clips(self) -> None:
        config = PoeConfig(api_key="", base_url="https://api.poe.com/v1")
        result = generate_video(
            config=config,
            model="veo-3.1-fast",
            scenes=[
                {
                    "scene_id": "scene-1",
                    "visual_description": "镜头推进到主角脸部",
                    "duration_seconds": 3.2,
                    "motion_intent": "slow_pan",
                }
            ],
            aspect_ratio="9:16",
        )
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["model"], "veo-3.1-fast")
        self.assertEqual(result["clips"][0]["scene_id"], "scene-1")


if __name__ == "__main__":
    unittest.main()
