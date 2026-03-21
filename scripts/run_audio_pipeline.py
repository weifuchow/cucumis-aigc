#!/usr/bin/env python3
"""audio_pipeline — batch: audio_foundation → global_timeline_initializer

Runs both pure-execution audio stages in sequence. No LLM calls.
Stop on first failure.

Usage:
  python scripts/run_audio_pipeline.py --project projects/<name>
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import pathlib


_STAGES = [
    ("audio_foundation",          "run_audio_foundation.py"),
    ("global_timeline_initializer", "run_global_timeline_initializer.py"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run audio pipeline stages in sequence.")
    parser.add_argument("--project", required=True)
    args = parser.parse_args()

    scripts_dir = pathlib.Path(__file__).parent
    project = args.project

    for stage, script in _STAGES:
        print(f"\n[audio_pipeline] ▶ {stage}", flush=True)
        result = subprocess.run(
            [sys.executable, str(scripts_dir / script), "--project", project],
            check=False,
        )
        if result.returncode != 0:
            print(f"[audio_pipeline] ✗ {stage} failed (exit {result.returncode})", file=sys.stderr)
            return result.returncode
        print(f"[audio_pipeline] ✓ {stage}", flush=True)

    print("\n[audio_pipeline] all stages complete", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
