#!/usr/bin/env python3
"""post_pipeline — batch: subtitle_asset_manager → timeline_builder → ffmpeg_renderer_reviewer

Assembles subtitles + manifest, builds final timeline, and renders MP4.
No LLM calls — pure deterministic execution.

Usage:
  python scripts/run_post_pipeline.py --project projects/<name>
  python scripts/run_post_pipeline.py --project projects/<name> --skip-render  # stop before FFmpeg
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import pathlib


def main() -> int:
    parser = argparse.ArgumentParser(description="Run post-production pipeline stages in sequence.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--skip-render", action="store_true", help="Stop after timeline_builder, skip FFmpeg render.")
    args = parser.parse_args()

    scripts_dir = pathlib.Path(__file__).parent
    project = args.project

    stages = [
        ("subtitle_asset_manager", "run_subtitle_asset_manager.py", []),
        ("timeline_builder",       "run_timeline_builder.py",       []),
    ]
    if not args.skip_render:
        stages.append(("ffmpeg_renderer_reviewer", "run_ffmpeg_renderer_reviewer.py", []))

    for stage, script, extra_args in stages:
        print(f"\n[post_pipeline] ▶ {stage}", flush=True)
        result = subprocess.run(
            [sys.executable, str(scripts_dir / script), "--project", project] + extra_args,
            check=False,
        )
        if result.returncode != 0:
            print(f"[post_pipeline] ✗ {stage} failed (exit {result.returncode})", file=sys.stderr)
            return result.returncode
        print(f"[post_pipeline] ✓ {stage}", flush=True)

    print("\n[post_pipeline] all stages complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
