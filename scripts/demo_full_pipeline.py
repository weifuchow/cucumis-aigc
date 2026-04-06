"""Full pipeline demo: audio (ElevenLabs vs Google TTS) + 2 images + 1 video.

Usage:
    python3 scripts/demo_full_pipeline.py
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from elevenlabs.client import load_elevenlabs_config
from elevenlabs.media import generate_tts
from google.client import load_google_config
from google.media import generate_audio, generate_image, generate_video

# ── 内容配置 ──────────────────────────────────────────────────────────────────

VOICEOVER_TEXT = (
    "远古的东方，有一条神龙沉睡于云海深处。"
    "它的鳞片如星辰般闪耀，每一次呼吸都掀起山间的云雾。"
    "当晨曦第一缕光穿透云层，神龙缓缓睁开双眼，"
    "翻腾而起，划破长空，守护着这片古老的大地。"
)  # 约 80 字，朗读约 30s

LANGUAGE = "zh-CN"
DURATION_SECONDS = 30

IMAGE_PROMPTS = [
    {
        "scene_id": "scene-01",
        "prompt_id": "img-01",
        "positive_prompt": (
            "中国风水墨画风格，神龙在云雾缭绕的山巅盘旋，"
            "鳞片金色发光，远景青山层叠，晨曦光线，史诗感，高细节"
        ),
        "aspect_ratio": "9:16",
        "style": "ink-painting",
    },
    {
        "scene_id": "scene-02",
        "prompt_id": "img-02",
        "positive_prompt": (
            "中国风写实风格，神龙从云层中俯冲而下，"
            "背景是连绵的山脉与瀑布，暮色橙红，动感十足，电影质感"
        ),
        "aspect_ratio": "9:16",
        "style": "cinematic",
    },
]

VIDEO_SCENE = [
    {
        "scene_id": "video-01",
        "duration_seconds": 6,
        "visual_description": (
            "神龙在云雾缭绕的山巅缓缓盘旋，鳞片在晨光中金色闪耀，"
            "镜头从远景缓慢推近，背景青山层叠，光线柔和，史诗感"
        ),
        "motion_intent": "slow push-in, dragon hovering",
    }
]

OUTPUT_DIR = Path("outputs/demo_pipeline")


# ── 工具函数 ──────────────────────────────────────────────────────────────────

def _copy_file(src_url: str, dest: Path, api_key: str = "") -> str:
    """Copy a file:// or https:// URL to dest, return dest path string."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src_url.startswith("file://"):
        shutil.copy2(src_url[len("file://"):], dest)
        return str(dest)
    if src_url.startswith("http"):
        download_url = src_url
        if api_key and "generativelanguage.googleapis.com" in src_url:
            sep = "&" if "?" in src_url else "?"
            download_url = f"{src_url}{sep}key={api_key}"
        with urllib.request.urlopen(download_url, timeout=120) as resp, open(dest, "wb") as f:
            f.write(resp.read())
        return str(dest)
    return src_url


def _section(title: str) -> None:
    print(f"\n{'='*60}", flush=True)
    print(f"  {title}", flush=True)
    print(f"{'='*60}", flush=True)


# ── 主流程 ────────────────────────────────────────────────────────────────────

def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    g_config = load_google_config()
    el_config = load_elevenlabs_config()
    results: dict = {"audio": {}, "images": [], "video": {}}

    # ── 1. ElevenLabs TTS ────────────────────────────────────────────────────
    _section("1/4  音频 — ElevenLabs TTS (eleven_multilingual_v2)")
    t0 = time.time()
    try:
        el_result = generate_tts(
            el_config,
            prompt=VOICEOVER_TEXT,
            duration_seconds=DURATION_SECONDS,
            language=LANGUAGE,
        )
        el_local = ""
        if el_result.get("audio_url"):
            el_local = _copy_file(el_result["audio_url"], OUTPUT_DIR / "audio_elevenlabs.mp3")
        results["audio"]["elevenlabs"] = {
            "model": el_result.get("model"),
            "elapsed_seconds": round(time.time() - t0, 1),
            "local_path": el_local,
        }
        print(f"  elapsed: {results['audio']['elevenlabs']['elapsed_seconds']}s  →  {el_local or '(failed)'}", flush=True)
    except Exception as exc:
        results["audio"]["elevenlabs"] = {"error": str(exc)}
        print(f"  [错误] {exc}", flush=True)

    # ── 2. Google TTS ────────────────────────────────────────────────────────
    _section("2/4  音频 — Google TTS (gemini-2.5-flash-preview-tts)")
    t0 = time.time()
    try:
        g_audio = generate_audio(
            g_config,
            model=g_config.tts_model,
            prompt=VOICEOVER_TEXT,
            duration_seconds=DURATION_SECONDS,
            language=LANGUAGE,
        )
        g_audio_local = ""
        if g_audio.get("audio_url"):
            g_audio_local = _copy_file(g_audio["audio_url"], OUTPUT_DIR / "audio_google.wav")
        results["audio"]["google"] = {
            "model": g_audio.get("model"),
            "elapsed_seconds": round(time.time() - t0, 1),
            "local_path": g_audio_local,
        }
        print(f"  elapsed: {results['audio']['google']['elapsed_seconds']}s  →  {g_audio_local or '(failed)'}", flush=True)
    except Exception as exc:
        results["audio"]["google"] = {"error": str(exc)}
        print(f"  [错误] {exc}", flush=True)

    # ── 3. 图片生成（每张独立调用，防止单张失败影响其他）────────────────────
    _section(f"3/4  图片 — {g_config.image_model}  ×2")
    for i, prompt_item in enumerate(IMAGE_PROMPTS, start=1):
        t0 = time.time()
        try:
            img_result = generate_image(g_config, model=g_config.image_model, prompts=[prompt_item])
            img = img_result.get("images", [{}])[0]
            url = img.get("url", "")
            local = ""
            if url:
                local = _copy_file(url, OUTPUT_DIR / f"image_{i:02d}.png", api_key=g_config.api_key)
            results["images"].append({"scene_id": img.get("scene_id"), "local_path": local, "url": url})
            print(f"  image-{i}: {local or url or '(failed)'}  {round(time.time()-t0,1)}s", flush=True)
        except Exception as exc:
            results["images"].append({"scene_id": prompt_item["scene_id"], "error": str(exc)})
            print(f"  image-{i}: [错误] {exc}", flush=True)

    # ── 4. 视频生成 ──────────────────────────────────────────────────────────
    _section(f"4/4  视频 — {g_config.video_model}  720p 6s")
    t0 = time.time()
    try:
        vid_result = generate_video(
            g_config,
            model=g_config.video_model,
            scenes=VIDEO_SCENE,
            aspect_ratio="9:16",
        )
        clip = vid_result.get("clips", [{}])[0]
        vid_url = clip.get("url", "")
        vid_local = ""
        if vid_url:
            vid_local = _copy_file(vid_url, OUTPUT_DIR / "video.mp4", api_key=g_config.api_key)
        results["video"] = {
            "model": vid_result.get("model"),
            "elapsed_seconds": round(time.time() - t0, 1),
            "local_path": vid_local,
            "url": vid_url,
        }
        print(f"  elapsed: {results['video']['elapsed_seconds']}s  →  {vid_local or vid_url or '(failed)'}", flush=True)
    except Exception as exc:
        results["video"] = {"error": str(exc)}
        print(f"  [错误] {exc}", flush=True)

    # ── 汇总 ─────────────────────────────────────────────────────────────────
    _section("完成汇总")
    summary = OUTPUT_DIR / "demo_result.json"
    summary.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    def _row(label: str, rec: dict, key: str = "local_path", time_key: str = "elapsed_seconds") -> tuple:
        path = rec.get(key, "")
        err = rec.get("error", "")
        timing = f"{rec[time_key]}s" if time_key in rec else ""
        return (label, path or (f"[错误] {err[:60]}" if err else "(失败)"), timing)

    rows = [
        _row("音频 ElevenLabs", results["audio"].get("elevenlabs", {})),
        _row("音频 Google TTS", results["audio"].get("google", {})),
    ]
    for i, img in enumerate(results["images"], 1):
        rows.append(_row(f"图片 {i}", img))
    rows.append(_row("视频", results.get("video", {})))

    for label, path, elapsed in rows:
        ok = "✓" if path else "✗"
        timing = f"  {elapsed}" if elapsed else ""
        print(f"  [{ok}] {label:20s} {path or '(failed)'}{timing}", flush=True)

    print(f"\n  结果保存：{summary}", flush=True)
    print(f"  输出目录：{OUTPUT_DIR.resolve()}", flush=True)


if __name__ == "__main__":
    main()
