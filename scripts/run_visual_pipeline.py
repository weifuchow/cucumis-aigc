#!/usr/bin/env python3
"""visual_pipeline — batch: asset_planner (validate) → image_generator → constrained_video_generator

Prerequisite: Claude Code skill 'asset_planner' must have already written
assets/asset-plan.json. This script only executes — no LLM calls.

Usage:
  python scripts/run_visual_pipeline.py --project projects/<name>
  python scripts/run_visual_pipeline.py --project projects/<name> --mock        # use mock asset plan
  python scripts/run_visual_pipeline.py --project projects/<name> --skip-video  # images only
  python scripts/run_visual_pipeline.py --project projects/<name> --refresh-baseline  # re-gen char/loc images
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import pathlib


def main() -> int:
    parser = argparse.ArgumentParser(description="Run visual generation pipeline stages in sequence.")
    parser.add_argument("--project", required=True)
    parser.add_argument("--mock", action="store_true", help="Pass --mock to asset_planner (build plan from storyboard).")
    parser.add_argument("--skip-video", action="store_true", help="Stop after image generation, skip video.")
    parser.add_argument("--refresh-baseline", action="store_true", help="Re-generate character/location baseline images.")
    args = parser.parse_args()

    scripts_dir = pathlib.Path(__file__).parent
    project = args.project

    # Stage 1: validate/normalize asset plan
    print("\n[visual_pipeline] ▶ asset_planner (validate)", flush=True)
    cmd = [sys.executable, str(scripts_dir / "run_asset_planner.py"), "--project", project]
    if args.mock:
        cmd.append("--mock")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[visual_pipeline] ✗ asset_planner failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode
    print("[visual_pipeline] ✓ asset_planner", flush=True)

    # Stage 2: image generation
    print("\n[visual_pipeline] ▶ image_generator", flush=True)
    cmd = [sys.executable, str(scripts_dir / "run_image_generator.py"), "--project", project]
    if args.refresh_baseline:
        cmd.append("--refresh-baseline")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        print(f"[visual_pipeline] ✗ image_generator failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode
    print("[visual_pipeline] ✓ image_generator", flush=True)

    if args.skip_video:
        print("\n[visual_pipeline] --skip-video: stopping after image generation", flush=True)
        return 0

    # Stage 3: video generation
    print("\n[visual_pipeline] ▶ constrained_video_generator", flush=True)
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "run_constrained_video_generator.py"), "--project", project],
        check=False,
    )
    if result.returncode != 0:
        print(f"[visual_pipeline] ✗ constrained_video_generator failed (exit {result.returncode})", file=sys.stderr)
        return result.returncode
    print("[visual_pipeline] ✓ constrained_video_generator", flush=True)

    print("\n[visual_pipeline] all stages complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
