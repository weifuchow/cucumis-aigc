#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update orchestration state for a project.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--current-stage", default=None, help="Current stage name.")
    parser.add_argument("--next-stage", default=None, help="Next stage name.")
    parser.add_argument(
        "--completed-stage",
        action="append",
        default=[],
        help="Completed stage to include in state.",
    )
    parser.add_argument("--workflow", default=None, help="Workflow name for plan output.")
    parser.add_argument(
        "--planned-stage",
        action="append",
        default=[],
        help="Stage to include in the plan.",
    )
    parser.add_argument(
        "--optional-stage",
        action="append",
        default=[],
        help="Stage to include in optional stages.",
    )
    parser.add_argument(
        "--disabled-stage",
        action="append",
        default=[],
        help="Stage to include in disabled stages.",
    )
    parser.add_argument("--decision-type", default=None, help="Decision type to append.")
    parser.add_argument("--decision-reason", default=None, help="Decision reason to append.")
    return parser.parse_args()


def write_json(path: pathlib.Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    orchestration_dir = project_dir / "orchestration"

    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    orchestration_dir.mkdir(parents=True, exist_ok=True)

    state = {
        "current_stage": args.current_stage,
        "completed_stages": args.completed_stage,
        "skipped_stages": [],
        "last_failed_stage": None,
        "next_stage": args.next_stage,
    }
    write_json(orchestration_dir / "state.json", state)

    if args.workflow is not None:
        plan = {
            "workflow": args.workflow,
            "planned_stages": args.planned_stage,
            "optional_stages": args.optional_stage,
            "disabled_stages": args.disabled_stage,
            "metadata": {},
        }
        write_json(orchestration_dir / "plan.json", plan)

    if args.decision_type and args.decision_reason:
        decision = {
            "timestamp": dt.datetime.now(dt.timezone.utc).isoformat(),
            "decision_type": args.decision_type,
            "reason": args.decision_reason,
            "payload": {
                "current_stage": args.current_stage,
                "next_stage": args.next_stage,
            },
        }
        with (orchestration_dir / "decisions.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(decision, ensure_ascii=False) + "\n")

    print(orchestration_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
