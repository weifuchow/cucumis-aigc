#!/usr/bin/env python3
"""audio_mixer — FFmpeg 混音：旁白 + BGM（含 ducking）→ audio/mixed-final.mp3

读取 audio/voiceover.json 的 source_path（对白轨）和
audio/bgm-selection.json 的 file_path（BGM 轨），
按 input.json 的 bgm 配置进行混音并输出合并文件。

如果 bgm.generate=false 或 bgm-selection.json 无 file_path，直接跳过（退出 0）。

用法：
  python scripts/run_audio_mixer.py --project projects/<name>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Mix voiceover + BGM for a project.")
    parser.add_argument("--project", required=True)
    return parser.parse_args()


def _ffmpeg_mix_simple(
    voice_path: pathlib.Path,
    bgm_path: pathlib.Path,
    output_path: pathlib.Path,
    bgm_volume_db: float,
) -> bool:
    """简单混音：旁白全量 + BGM 降音量，amix 按旁白时长截断。"""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-i", str(bgm_path),
            "-filter_complex",
            f"[1:a]volume={bgm_volume_db}dB[bgm];"
            "[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[out]",
            "-map", "[out]",
            "-c:a", "libmp3lame", "-q:a", "3",
            str(output_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[audio_mixer] ffmpeg 错误：{result.stderr[-800:]}", flush=True)
    return result.returncode == 0 and output_path.is_file()


def _ffmpeg_mix_ducking(
    voice_path: pathlib.Path,
    bgm_path: pathlib.Path,
    output_path: pathlib.Path,
    bgm_volume_db: float,
) -> bool:
    """Ducking 混音：有人声时 BGM 自动压低，人声结束后恢复。
    sidechaincompress: BGM 作为被压缩信号，旁白作为 sidechain 触发。
    """
    filter_complex = (
        f"[1:a]volume={bgm_volume_db}dB[bgm_vol];"
        # BGM 被旁白 sidechain 压缩
        "[bgm_vol][0:a]sidechaincompress="
        "threshold=0.015:ratio=8:attack=80:release=500:makeup=1[bgm_ducked];"
        # 混合：原始旁白 + 已压缩 BGM
        "[0:a][bgm_ducked]amix=inputs=2:duration=first:dropout_transition=2[out]"
    )
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(voice_path),
            "-i", str(bgm_path),
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-c:a", "libmp3lame", "-q:a", "3",
            str(output_path),
        ],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"[audio_mixer] ducking ffmpeg 错误：{result.stderr[-800:]}", flush=True)
    return result.returncode == 0 and output_path.is_file()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    task_input = json.loads((project_dir / "input" / "input.json").read_text(encoding="utf-8"))
    bgm_cfg: dict = task_input.get("bgm", {})

    if not bgm_cfg.get("generate", False):
        print("[audio_mixer] bgm.generate=false，跳过混音", flush=True)
        return 0

    if not shutil.which("ffmpeg"):
        print("[audio_mixer] 未找到 ffmpeg，跳过混音", flush=True)
        return 0

    audio_dir = project_dir / "audio"

    # 读取旁白文件路径
    voiceover_json = json.loads((audio_dir / "voiceover.json").read_text(encoding="utf-8"))
    voice_relpath: str | None = voiceover_json.get("source_path")
    if not voice_relpath:
        print("[audio_mixer] voiceover.json 无 source_path，跳过", flush=True)
        return 0
    voice_path = project_dir / voice_relpath
    if not voice_path.is_file():
        print(f"[audio_mixer] 旁白文件不存在：{voice_path}，跳过", flush=True)
        return 0

    # 读取 BGM 文件路径
    bgm_json = json.loads((audio_dir / "bgm-selection.json").read_text(encoding="utf-8"))
    bgm_relpath: str | None = bgm_json.get("file_path")
    if not bgm_relpath:
        print("[audio_mixer] bgm-selection.json 无 file_path，跳过混音", flush=True)
        return 0
    bgm_path = project_dir / bgm_relpath
    if not bgm_path.is_file():
        print(f"[audio_mixer] BGM 文件不存在：{bgm_path}，跳过", flush=True)
        return 0

    bgm_volume_db: float = float(bgm_cfg.get("volume_db", -18))
    duck: bool = bgm_cfg.get("duck_during_speech", True)

    output_path = audio_dir / "mixed-final.mp3"

    print(f"[audio_mixer] 旁白={voice_path.name}，BGM={bgm_path.name}", flush=True)
    print(f"[audio_mixer] volume={bgm_volume_db}dB，ducking={duck}", flush=True)

    if duck:
        ok = _ffmpeg_mix_ducking(voice_path, bgm_path, output_path, bgm_volume_db)
        if not ok:
            print("[audio_mixer] ducking 失败，降级为简单混音", flush=True)
            ok = _ffmpeg_mix_simple(voice_path, bgm_path, output_path, bgm_volume_db)
    else:
        ok = _ffmpeg_mix_simple(voice_path, bgm_path, output_path, bgm_volume_db)

    if not ok:
        print("[audio_mixer] 混音失败", flush=True)
        return 1

    # 写入 mix-manifest.json
    mix_manifest = {
        "voice_path": voice_relpath,
        "bgm_path": bgm_relpath,
        "output_path": str(output_path.relative_to(project_dir)),
        "bgm_volume_db": bgm_volume_db,
        "duck_during_speech": duck,
        "mode": "ducking" if duck else "simple",
    }
    (audio_dir / "mix-manifest.json").write_text(
        json.dumps(mix_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[audio_mixer] 完成 → {output_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
