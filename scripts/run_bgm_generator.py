#!/usr/bin/env python3
"""bgm_generator — 调用 Poe 生成 BGM 音频，写入 audio/bgm-main.mp3

读取 input.json 中的 bgm 配置，生成背景音乐并裁剪/循环到目标时长。
如果 bgm.generate=false，直接跳过并退出 0。

用法：
  python scripts/run_bgm_generator.py --project projects/<name>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import urllib.request
from urllib.parse import urlparse

from poe.client import PoeConfig, load_poe_config
from poe.media import generate_audio
from poe.usage import append_cost_event, write_usage_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate BGM audio for a project.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def _detect_file_suffix(url: str) -> str:
    path = urlparse(url).path or ""
    suffix = pathlib.Path(path).suffix.lower()
    return suffix if suffix else ".mp3"


def _probe_duration(path: pathlib.Path) -> float | None:
    if not path.is_file() or not shutil.which("ffprobe"):
        return None
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return None
    try:
        v = float(result.stdout.strip())
        return v if v > 0 else None
    except ValueError:
        return None


def _loop_or_trim(source: pathlib.Path, output: pathlib.Path, target_seconds: float) -> bool:
    """FFmpeg: 如果源比目标短则循环，最终截断到 target_seconds。"""
    if not shutil.which("ffmpeg"):
        shutil.copy2(source, output)
        return True
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-stream_loop", "-1",   # 无限循环输入
            "-i", str(source),
            "-t", str(target_seconds),
            "-vn",
            str(output),
        ],
        capture_output=True, text=True,
    )
    return result.returncode == 0 and output.is_file()


def _download(url: str, dest: pathlib.Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        dest.write_bytes(resp.read())


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    task_input = json.loads((project_dir / "input" / "input.json").read_text(encoding="utf-8"))
    bgm_cfg: dict = task_input.get("bgm", {})

    if not bgm_cfg.get("generate", False):
        print("[bgm_generator] bgm.generate=false，跳过", flush=True)
        return 0

    duration_seconds: int = int(task_input["duration_seconds"])
    bgm_model: str = bgm_cfg.get("bgm_model", "lyria")
    mood: str = bgm_cfg.get("mood") or task_input.get("music_emotion", "cinematic")
    language: str = str(task_input.get("language", "zh"))

    # 构造 BGM 提示词
    prompt = (
        f"纯背景音乐，无人声，风格：{mood}，"
        f"时长约 {duration_seconds} 秒，循环友好，与视频叙事节奏匹配。"
    )
    print(f"[bgm_generator] 模型={bgm_model}，时长={duration_seconds}s", flush=True)
    print(f"[bgm_generator] prompt={prompt}", flush=True)

    audio_dir = project_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    project_env = project_dir / ".env"
    config = load_poe_config(env_path=project_env if project_env.is_file() else None)

    generation_error: str | None = None
    try:
        result = generate_audio(
            config=config,
            model=bgm_model,
            prompt=prompt,
            duration_seconds=duration_seconds,
            language=language,
        )
    except Exception as exc:
        generation_error = str(exc)
        print(f"[bgm_generator] 生成失败：{exc}，使用 mock", flush=True)
        result = generate_audio(
            config=PoeConfig(api_key="", base_url=config.base_url),
            model=bgm_model,
            prompt=prompt,
            duration_seconds=duration_seconds,
            language=language,
        )

    audio_url: str | None = result.get("audio_url")
    source_path: pathlib.Path | None = None
    main_path: pathlib.Path | None = None
    download_error: str | None = None

    if isinstance(audio_url, str) and audio_url.startswith(("http://", "https://")):
        try:
            suffix = _detect_file_suffix(audio_url)
            source_path = audio_dir / f"bgm-source{suffix}"
            _download(audio_url, source_path)
            print(f"[bgm_generator] 已下载 → {source_path.name}", flush=True)

            main_path = audio_dir / "bgm-main.mp3"
            ok = _loop_or_trim(source_path, main_path, float(duration_seconds))
            if not ok:
                # 回退：直接复制
                shutil.copy2(source_path, main_path)
            print(f"[bgm_generator] 已裁剪 → {main_path.name}", flush=True)
        except Exception as exc:
            download_error = str(exc)
            print(f"[bgm_generator] 下载/处理失败：{exc}", flush=True)
    else:
        print("[bgm_generator] 未获得有效 URL（mock 模式）", flush=True)

    # 写入 bgm-selection.json（带真实文件路径）
    bgm_selection = {
        "track_id": f"bgm-generated-{result.get('request_id', 'unknown')}",
        "mood": mood,
        "model": bgm_model,
        "source_url": audio_url,
        "source_path": str(source_path.relative_to(project_dir)) if source_path else None,
        "file_path": str(main_path.relative_to(project_dir)) if main_path else None,
        "target_duration_seconds": duration_seconds,
        "generation_error": generation_error,
        "download_error": download_error,
    }
    (audio_dir / "bgm-selection.json").write_text(
        json.dumps(bgm_selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    write_usage_json(
        audio_dir / "bgm-request.json",
        {
            "provider": "poe",
            "model": bgm_model,
            "request_id": result.get("request_id"),
            "prompt": prompt,
            "target_duration_seconds": duration_seconds,
            "source_url": audio_url,
            "generation_error": generation_error,
            "download_error": download_error,
        },
    )
    append_cost_event(
        project_dir,
        {
            "skill": "bgm_generator",
            "model": bgm_model,
            "request_id": result.get("request_id"),
            "cost_points": (result.get("usage") or {}).get("cost_points"),
            "output_path": "audio/bgm-main.mp3",
        },
    )

    print(f"[bgm_generator] 完成 → {audio_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
