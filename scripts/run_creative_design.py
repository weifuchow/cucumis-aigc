#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run integrated creative design stage: brief intake + input parsing."
    )
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--seed-text",
        default=None,
        help="Optional one-line seed text passed to creative brief intake.",
    )
    return parser.parse_args()


def run_step(script_path: pathlib.Path, project_dir: pathlib.Path, seed_text: str | None = None) -> int:
    cmd = [sys.executable, str(script_path), "--project", str(project_dir)]
    if seed_text is not None and script_path.name == "run_creative_brief_intake.py":
        cmd.extend(["--seed-text", seed_text])
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
        elif result.stdout:
            print(result.stdout.strip(), file=sys.stderr)
    return result.returncode


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    scripts_dir = pathlib.Path(__file__).resolve().parent

    intake_script = scripts_dir / "run_creative_brief_intake.py"
    input_script = scripts_dir / "run_input_parser.py"

    intake_code = run_step(intake_script, project_dir, seed_text=args.seed_text)
    if intake_code != 0:
        return intake_code

    parse_code = run_step(input_script, project_dir)
    if parse_code != 0:
        return parse_code

    print(project_dir / "input" / "input.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
