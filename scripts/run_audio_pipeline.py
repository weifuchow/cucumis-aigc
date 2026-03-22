#!/usr/bin/env python3
"""audio_pipeline — 串行运行音频阶段：
  audio_foundation → [bgm_generator] → [audio_mixer] → global_timeline_initializer

bgm_generator 和 audio_mixer 仅在 input.json 的 bgm.generate=true 时运行。
遇到第一个失败即停止。

用法：
  python scripts/run_audio_pipeline.py --project projects/<name>
"""

from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys


def _read_bgm_generate(project_dir: pathlib.Path) -> bool:
    input_path = project_dir / "input" / "input.json"
    if not input_path.is_file():
        return False
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
        return bool(data.get("bgm", {}).get("generate", False))
    except Exception:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Run audio pipeline stages in sequence.")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()

    scripts_dir = pathlib.Path(__file__).parent
    project_dir = pathlib.Path(args.project).resolve()

    bgm_enabled = _read_bgm_generate(project_dir)

    stages: list[tuple[str, str]] = [
        ("audio_foundation", "run_audio_foundation.py"),
    ]
    if bgm_enabled:
        stages.append(("bgm_generator", "run_bgm_generator.py"))
        stages.append(("audio_mixer",   "run_audio_mixer.py"))
    stages.append(("global_timeline_initializer", "run_global_timeline_initializer.py"))

    print(f"[audio_pipeline] BGM={'开启' if bgm_enabled else '关闭'}，共 {len(stages)} 个阶段", flush=True)

    for stage, script in stages:
        print(f"\n[audio_pipeline] ▶ {stage}", flush=True)
        result = subprocess.run(
            [sys.executable, str(scripts_dir / script), "--project", str(project_dir)],
            check=False,
        )
        if result.returncode != 0:
            print(f"[audio_pipeline] ✗ {stage} 失败 (exit {result.returncode})", file=sys.stderr)
            return result.returncode
        print(f"[audio_pipeline] ✓ {stage}", flush=True)

    print("\n[audio_pipeline] 所有阶段完成", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
