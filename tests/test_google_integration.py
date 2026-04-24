"""Google AI + ElevenLabs integration tests.

Mock 测试（无需 API key，始终运行）:
  python -m pytest tests/test_google_integration.py -v

Live demo（需要在 .env 配置 GOOGLE_AI_API_KEY）:
  python tests/test_google_integration.py --live
  python tests/test_google_integration.py --live --skip-video  # 跳过慢速视频测试
"""

from __future__ import annotations

import argparse
import os
import pathlib
import sys
import tempfile
import time
import unittest
from unittest import mock

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from google.client import GoogleConfig, load_google_config
from google.media import generate_image, generate_video, generate_audio
from elevenlabs.client import ElevenLabsConfig, load_elevenlabs_config
from elevenlabs.media import generate_tts
from providers.codex import make_codex_provider
from providers.google import make_google_provider
from providers.factory import load_provider
from run_image_generator import download_image


# ---------------------------------------------------------------------------
# Mock-mode unit tests (always run, no API key required)
# ---------------------------------------------------------------------------

class TestGoogleMockMode(unittest.TestCase):
    """Verify mock responses when api_key is empty."""

    def _config(self) -> GoogleConfig:
        return GoogleConfig(api_key="")

    def test_generate_image_mock_returns_correct_shape(self) -> None:
        result = generate_image(
            self._config(),
            model="gemini-3.1-flash-image-preview",
            prompts=[
                {
                    "scene_id": "scene-1",
                    "prompt_id": "p-1",
                    "positive_prompt": "一座古老的中国城楼，夜晚，霓虹灯光",
                    "aspect_ratio": "9:16",
                }
            ],
        )
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(len(result["images"]), 1)
        self.assertEqual(result["images"][0]["scene_id"], "scene-1")
        self.assertIn("url", result["images"][0])

    def test_generate_image_mock_multiple_scenes(self) -> None:
        prompts = [
            {"scene_id": f"s{i}", "prompt_id": f"p{i}", "positive_prompt": f"场景{i}"} for i in range(3)
        ]
        result = generate_image(self._config(), "gemini-3.1-flash-image-preview", prompts)
        self.assertEqual(len(result["images"]), 3)
        self.assertEqual(result["images"][2]["scene_id"], "s2")

    def test_generate_video_mock_returns_clips(self) -> None:
        scenes = [
            {
                "scene_id": "scene-1",
                "visual_description": "主角奔跑穿越废墟，镜头跟随",
                "motion_intent": "tracking_shot",
                "duration_seconds": 5,
            },
            {
                "scene_id": "scene-2",
                "visual_description": "俯拍城市全景，缓慢旋转",
                "motion_intent": "aerial_rotation",
                "duration_seconds": 6,
            },
        ]
        result = generate_video(self._config(), "veo-3.1-lite-generate-preview", scenes, "9:16")
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["model"], "veo-3.1-lite-generate-preview")
        self.assertEqual(len(result["clips"]), 2)
        self.assertEqual(result["clips"][0]["scene_id"], "scene-1")
        self.assertEqual(result["clips"][1]["duration_seconds"], 6)

    def test_generate_audio_mock_gemini_tts(self) -> None:
        result = generate_audio(
            self._config(),
            model="gemini-2.5-flash-preview-tts",
            prompt="在遥远的东方，有一座被遗忘的城市。",
            duration_seconds=8,
            language="zh",
        )
        self.assertEqual(result["mode"], "mock")
        self.assertIn("segments", result)
        self.assertEqual(result["segments"][0]["segment_id"], "seg-1")

    def test_generate_tts_mock_elevenlabs(self) -> None:
        config = ElevenLabsConfig(api_key="")
        result = generate_tts(config, prompt="Hello world", duration_seconds=4, language="en")
        self.assertEqual(result["mode"], "mock")
        self.assertIsNone(result["audio_url"])

    def test_load_google_config_env_override(self) -> None:
        # Pass env_path to a nonexistent path to isolate from real .env file
        config = load_google_config(
            env={
                "GOOGLE_AI_API_KEY": "test-key-123",
                "GOOGLE_IMAGE_MODEL": "gemini-3.1-flash-image-preview",
                "GOOGLE_VIDEO_MODEL": "veo-3.1-lite-generate-preview",
            },
            env_path=pathlib.Path("/nonexistent/.env"),
        )
        self.assertEqual(config.api_key, "test-key-123")
        self.assertEqual(config.image_model, "gemini-3.1-flash-image-preview")
        self.assertEqual(config.video_model, "veo-3.1-lite-generate-preview")

    def test_load_google_config_model_override(self) -> None:
        config = load_google_config(env={
            "GOOGLE_AI_API_KEY": "x",
            "GOOGLE_VIDEO_MODEL": "veo-3.1-lite-generate-preview",
        })
        self.assertEqual(config.video_model, "veo-3.1-lite-generate-preview")

    def test_provider_factory_registers_google(self) -> None:
        provider = load_provider(env={"MEDIA_PROVIDER": "google", "GOOGLE_AI_API_KEY": ""})
        self.assertEqual(type(provider).__name__, "GoogleProvider")

    def test_provider_factory_registers_elevenlabs(self) -> None:
        provider = load_provider(env={"MEDIA_PROVIDER": "elevenlabs", "ELEVENLABS_API_KEY": ""})
        self.assertEqual(type(provider).__name__, "ElevenLabsProvider")

    def test_provider_factory_registers_codex(self) -> None:
        provider = load_provider(env={"MEDIA_PROVIDER": "codex", "CODEX_IMAGE_MODEL": "image-2.0"})
        self.assertEqual(type(provider).__name__, "CodexProvider")

    def test_provider_factory_defaults_to_codex(self) -> None:
        with mock.patch.dict(os.environ, {"PATH": os.environ.get("PATH", "")}, clear=True):
            provider = load_provider(env={"CODEX_IMAGE_MODEL": "image-2.0"}, env_path=pathlib.Path("/nonexistent/.env"))
        self.assertEqual(type(provider).__name__, "CodexProvider")

    def test_codex_provider_generate_image_via_interface(self) -> None:
        provider = make_codex_provider(env={"CODEX_IMAGE_MODEL": "image-2.0"})

        with tempfile.TemporaryDirectory() as tmp:
            generated = pathlib.Path(tmp) / "codex-scene-1.png"
            generated.write_bytes(b"fake-image")

            completed = mock.Mock()
            completed.stdout = f"{generated}\n"

            with mock.patch("providers.codex.subprocess.run", return_value=completed) as run_mock:
                result = provider.generate_image(
                    provider.default_image_model,
                    [{"scene_id": "scene-1", "prompt_id": "p1", "positive_prompt": "test prompt"}],
                )

        self.assertEqual(result["mode"], "live")
        self.assertEqual(result["model"], "image-2.0")
        self.assertEqual(result["images"][0]["scene_id"], "scene-1")
        self.assertTrue(result["images"][0]["url"].startswith("file://"))
        self.assertEqual(result["images"][0]["prompt_id"], "p1")
        self.assertIn("codex exec", result["raw_response"]["command"])
        run_mock.assert_called_once()

    def test_codex_provider_passes_reference_images_to_cli(self) -> None:
        provider = make_codex_provider(env={"CODEX_IMAGE_MODEL": "image-2.0"})

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            generated = tmp_path / "codex-scene-2.png"
            generated.write_bytes(b"fake-image")
            ref_image = tmp_path / "ref-1.png"
            ref_image.write_bytes(b"fake-ref")

            completed = mock.Mock()
            completed.stdout = f"{generated}\n"

            with mock.patch("providers.codex.subprocess.run", return_value=completed) as run_mock:
                provider.generate_image(
                    provider.default_image_model,
                    [
                        {
                            "scene_id": "scene-2",
                            "prompt_id": "p2",
                            "positive_prompt": "make a portrait",
                            "_ref_images": [{"path": str(ref_image), "role": "character"}],
                        }
                    ],
                )

        command = run_mock.call_args.args[0]
        self.assertIn("--image", command)
        self.assertIn(str(ref_image), command)
        self.assertIn("Reference images", command[-1])

    def test_codex_provider_includes_reference_roles_in_prompt(self) -> None:
        provider = make_codex_provider(env={"CODEX_IMAGE_MODEL": "image-2.0"})

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            generated = tmp_path / "codex-scene-3.png"
            generated.write_bytes(b"fake-image")
            char_ref = tmp_path / "char.png"
            char_ref.write_bytes(b"char-ref")
            style_ref = tmp_path / "style.png"
            style_ref.write_bytes(b"style-ref")

            completed = mock.Mock()
            completed.stdout = f"{generated}\n"

            with mock.patch("providers.codex.subprocess.run", return_value=completed) as run_mock:
                provider.generate_image(
                    provider.default_image_model,
                    [
                        {
                            "scene_id": "scene-3",
                            "prompt_id": "p3",
                            "positive_prompt": "make a cinematic portrait",
                            "_ref_images": [
                                {"path": str(char_ref), "role": "character"},
                                {"path": str(style_ref), "role": "style"},
                            ],
                        }
                    ],
                )

        prompt = run_mock.call_args.args[0][-1]
        self.assertIn("character", prompt)
        self.assertIn("style", prompt)
        self.assertIn(str(char_ref), prompt)
        self.assertIn(str(style_ref), prompt)
        self.assertIn("preserve the subject identity", prompt)
        self.assertIn("borrow the visual style", prompt)

    def test_download_image_supports_file_url(self) -> None:
        png_bytes = (
            b"\x89PNG\r\n\x1a\n"
            b"\x00\x00\x00\rIHDR"
            b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00"
            b"\x90wS\xde"
            b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
            b"\x0b\xe7\x02\x9d"
            b"\x00\x00\x00\x00IEND\xaeB`\x82"
        )

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            source = tmp_path / "source.png"
            source.write_bytes(png_bytes)

            copied = download_image(source.as_uri(), tmp_path / "copied-image")

            self.assertTrue(copied.is_file())
            self.assertEqual(copied.suffix, ".png")
            self.assertEqual(copied.read_bytes(), png_bytes)

    def test_google_provider_mock_image_via_interface(self) -> None:
        provider = make_google_provider(env={"GOOGLE_AI_API_KEY": "", "ELEVENLABS_API_KEY": ""})
        result = provider.generate_image(
            provider.default_image_model,
            [{"scene_id": "s1", "prompt_id": "p1", "positive_prompt": "test"}],
        )
        self.assertEqual(result["mode"], "mock")

    def test_google_provider_mock_video_via_interface(self) -> None:
        provider = make_google_provider(env={"GOOGLE_AI_API_KEY": "", "ELEVENLABS_API_KEY": ""})
        result = provider.generate_video(
            provider.default_video_model,
            [{"scene_id": "s1", "visual_description": "test", "duration_seconds": 5}],
            "9:16",
        )
        self.assertEqual(result["mode"], "mock")
        self.assertEqual(result["clips"][0]["scene_id"], "s1")

    def test_google_provider_audio_routes_to_elevenlabs_when_key_present(self) -> None:
        provider = make_google_provider(env={"GOOGLE_AI_API_KEY": "", "ELEVENLABS_API_KEY": "fake"})
        # Verify routing decision: default_audio_model should point to ElevenLabs
        self.assertEqual(provider.default_audio_model, "eleven_multilingual_v2")
        # Verify ElevenLabs config was picked up
        self.assertEqual(provider.el_config.api_key, "fake")

    def test_google_provider_audio_routes_to_gemini_tts_without_el_key(self) -> None:
        provider = make_google_provider(env={"GOOGLE_AI_API_KEY": "", "ELEVENLABS_API_KEY": ""})
        result = provider.generate_audio("gemini-2.5-flash-preview-tts", "测试旁白", 5, "zh")
        self.assertEqual(result["mode"], "mock")


# ---------------------------------------------------------------------------
# Live integration demo (only runs via --live flag or when called directly)
# ---------------------------------------------------------------------------

def _hr(title: str = "") -> None:
    print(f"\n{'─' * 60}")
    if title:
        print(f"  {title}")
    print()


def _check(label: str, condition: bool, detail: str = "") -> None:
    mark = "✓" if condition else "✗"
    print(f"  [{mark}] {label}" + (f"  — {detail}" if detail else ""))
    if not condition:
        raise AssertionError(f"FAIL: {label}")


def demo_image(config: GoogleConfig) -> None:
    _hr("图片生成  Gemini image generation")
    model = config.image_model
    print(f"  model : {model}")
    print(f"  prompt: 一座被晨雾笼罩的中国古代城楼，电影感光线，9:16 竖版")

    t0 = time.time()
    result = generate_image(
        config,
        model=model,
        prompts=[
            {
                "scene_id": "demo-scene-1",
                "prompt_id": "demo-p-1",
                "positive_prompt": (
                    "一座被晨雾笼罩的中国古代城楼，远处山脉，金色晨光穿透雾气，"
                    "电影感光线，超写实，竖版构图"
                ),
                "negative_prompt": "blurry, cartoon, watermark",
                "aspect_ratio": "9:16",
            }
        ],
    )
    elapsed = round(time.time() - t0, 1)

    _check("mode == live", result["mode"] == "live", result["mode"])
    _check("images 不为空", bool(result.get("images")))
    url = result["images"][0].get("url", "")
    _check("image URL 已返回", bool(url), url[:80] if url else "(empty)")
    print(f"\n  耗时 {elapsed}s   url → {url[:100]}")


def demo_video(config: GoogleConfig) -> None:
    _hr("视频生成  Veo 2 (long-running, 约 2-5 分钟)")
    model = config.video_model
    print(f"  model : {model}")
    print("  提示：Veo 2 每个场景单独提交 operation，请耐心等待…\n")

    scenes = [
        {
            "scene_id": "demo-scene-1",
            "visual_description": (
                "主角在废弃的霓虹街道行走，低角度跟拍，慢动作，赛博朋克风格"
            ),
            "motion_intent": "tracking_shot",
            "duration_seconds": 5,
        }
    ]
    t0 = time.time()
    result = generate_video(config, model=model, scenes=scenes, aspect_ratio="9:16")
    elapsed = round(time.time() - t0, 1)

    _check("mode == live", result["mode"] == "live", result["mode"])
    _check("clips 不为空", bool(result.get("clips")))
    url = result["clips"][0].get("url", "")
    _check("video URL 已返回", bool(url), url[:80] if url else "(empty — operation 可能仍在处理)")
    print(f"\n  耗时 {elapsed}s   url → {url[:100] or '(empty)'}")


def demo_audio_gemini(config: GoogleConfig) -> None:
    _hr("音频生成  Gemini TTS")
    model = config.tts_model
    prompt = "在遥远的东方，有一座被时间遗忘的城市，它的秘密深埋在每一块古老的青石之下。"
    print(f"  model : {model}")
    print(f"  text  : {prompt[:40]}…")

    t0 = time.time()
    result = generate_audio(config, model=model, prompt=prompt, duration_seconds=10, language="zh")
    elapsed = round(time.time() - t0, 1)

    _check("mode == live", result["mode"] == "live", result["mode"])
    _check("audio_url 已返回", bool(result.get("audio_url")), str(result.get("audio_url", "")))
    print(f"\n  耗时 {elapsed}s   file → {result.get('audio_url', '')}")


def demo_audio_elevenlabs(el_config: ElevenLabsConfig) -> None:
    _hr("音频生成  ElevenLabs TTS")
    prompt = "在遥远的东方，有一座被时间遗忘的城市，它的秘密深埋在每一块古老的青石之下。"
    print(f"  voice : 中文 Lily  model: eleven_multilingual_v2")
    print(f"  text  : {prompt[:40]}…")

    t0 = time.time()
    result = generate_tts(
        el_config,
        prompt=prompt,
        duration_seconds=10,
        language="zh",
    )
    elapsed = round(time.time() - t0, 1)

    _check("mode == live", result["mode"] == "live", result["mode"])
    _check("audio_url 已返回", bool(result.get("audio_url")), str(result.get("audio_url", "")))
    print(f"\n  耗时 {elapsed}s   file → {result.get('audio_url', '')}")


def run_live_demo(skip_video: bool = False) -> None:
    print("=" * 60)
    print("  Google AI + ElevenLabs  Live Integration Demo")
    print("=" * 60)

    g_config = load_google_config()
    el_config = load_elevenlabs_config()

    if not g_config.api_key:
        print("\n❌  GOOGLE_AI_API_KEY 未设置，请先配置 .env")
        sys.exit(1)

    print(f"\n  GOOGLE_AI_API_KEY : …{g_config.api_key[-6:]}")
    print(f"  ELEVENLABS_API_KEY: {'已配置 …' + el_config.api_key[-6:] if el_config.api_key else '未配置（将使用 Gemini TTS）'}")
    print(f"  image model : {g_config.image_model}")
    print(f"  video model : {g_config.video_model}")
    print(f"  tts model   : {g_config.tts_model}")

    failures: list[str] = []

    # --- Image ---
    try:
        demo_image(g_config)
    except AssertionError as e:
        failures.append(f"image: {e}")

    # --- Audio ---
    if el_config.api_key:
        try:
            demo_audio_elevenlabs(el_config)
        except AssertionError as e:
            failures.append(f"elevenlabs-audio: {e}")
    else:
        try:
            demo_audio_gemini(g_config)
        except AssertionError as e:
            failures.append(f"gemini-audio: {e}")

    # --- Video (slow, optional) ---
    if skip_video:
        _hr()
        print("  [跳过] 视频生成（--skip-video）")
    else:
        try:
            demo_video(g_config)
        except AssertionError as e:
            failures.append(f"video: {e}")

    # --- Summary ---
    _hr("结果汇总")
    if failures:
        for f in failures:
            print(f"  ✗ {f}")
        print(f"\n共 {len(failures)} 项失败")
        sys.exit(1)
    else:
        print("  全部通过 ✓")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Google AI integration test/demo")
    parser.add_argument("--live", action="store_true", help="Run live API demo (requires GOOGLE_AI_API_KEY)")
    parser.add_argument("--skip-video", action="store_true", help="Skip video generation (slow, ~2-5 min)")
    args = parser.parse_args()

    if args.live:
        run_live_demo(skip_video=args.skip_video)
    else:
        # Default: run unittest mock tests
        unittest.main(argv=[sys.argv[0], "-v"])
