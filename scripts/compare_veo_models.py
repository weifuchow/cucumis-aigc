"""Compare Veo 2.0 vs Veo 3.0 video generation quality.

Usage:
    python scripts/compare_veo_models.py
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from google.client import load_google_config
from google.media import generate_video

# ── Test scene (same prompt for fair comparison) ──────────────────────────────
TEST_SCENE = [
    {
        "scene_id": "compare-01",
        "duration_seconds": 6,
        "visual_description": (
            "龙在云雾缭绕的山巅盘旋，鳞片在晨光中闪烁，镜头从远景缓慢推近，"
            "背景是连绵的青山瀑布，光线柔和，史诗感。"
        ),
        "motion_intent": "slow push-in on dragon hovering",
    }
]

MODELS = [
    "veo-2.0-generate-001",
    "veo-3.0-generate-001",
]

ASPECT_RATIO = "9:16"
OUTPUT_DIR = Path("outputs/veo_compare")


def _download(url: str, dest: Path, api_key: str = "") -> None:
    """Download a video URL to a local file.

    Google AI Files API requires ?key=<api_key> for authenticated downloads.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    download_url = url
    if api_key and "generativelanguage.googleapis.com" in url:
        sep = "&" if "?" in url else "?"
        download_url = f"{url}{sep}key={api_key}"
    with urllib.request.urlopen(download_url, timeout=120) as resp, open(dest, "wb") as f:
        f.write(resp.read())


def run_comparison() -> None:
    config = load_google_config()
    if not config.api_key:
        print("[error] GOOGLE_AI_API_KEY not set in .env", flush=True)
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    for model in MODELS:
        print(f"\n{'='*60}", flush=True)
        print(f"  Model: {model}", flush=True)
        print(f"{'='*60}", flush=True)

        t0 = time.time()
        result = generate_video(config, model=model, scenes=TEST_SCENE, aspect_ratio=ASPECT_RATIO)
        elapsed = time.time() - t0

        clip = result["clips"][0] if result.get("clips") else {}
        video_url = clip.get("url", "")
        operation = clip.get("operation_name", "")

        local_path = ""
        if video_url and video_url.startswith("http"):
            fname = model.replace("/", "_") + ".mp4"
            dest = OUTPUT_DIR / fname
            try:
                print(f"[download] saving to {dest} …", flush=True)
                _download(video_url, dest, api_key=config.api_key)
                local_path = str(dest)
                print(f"[download] done → {local_path}", flush=True)
            except Exception as exc:
                print(f"[download] failed: {exc}", flush=True)

        record = {
            "model": model,
            "elapsed_seconds": round(elapsed, 1),
            "video_url": video_url,
            "local_path": local_path,
            "operation_name": operation,
        }
        results.append(record)

        print(f"  elapsed : {record['elapsed_seconds']}s", flush=True)
        print(f"  url     : {video_url or '(empty)'}", flush=True)
        print(f"  local   : {local_path or '(not downloaded)'}", flush=True)

    # ── Summary ───────────────────────────────────────────────────────────────
    summary_path = OUTPUT_DIR / "comparison_result.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2))

    print(f"\n{'='*60}", flush=True)
    print("  SUMMARY", flush=True)
    print(f"{'='*60}", flush=True)
    for r in results:
        status = "✓" if r["local_path"] else ("URL" if r["video_url"] else "✗")
        print(f"  [{status}] {r['model']:40s}  {r['elapsed_seconds']}s", flush=True)
        if r["local_path"]:
            print(f"       → {r['local_path']}", flush=True)
        elif r["video_url"]:
            print(f"       → {r['video_url']}", flush=True)
    print(f"\n  Full result saved: {summary_path}", flush=True)


if __name__ == "__main__":
    run_comparison()