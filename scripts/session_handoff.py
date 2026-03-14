#!/usr/bin/env python3

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a compact session handoff pack for new threads.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--output",
        default="orchestration/session-handoff.md",
        help="Output markdown path relative to project, or absolute path.",
    )
    parser.add_argument(
        "--decisions-tail",
        type=int,
        default=8,
        help="How many recent decisions to include.",
    )
    return parser.parse_args()


def read_json(path: pathlib.Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.is_file():
        return fallback
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback
    if not isinstance(payload, dict):
        return fallback
    return payload


def read_recent_decisions(path: pathlib.Path, max_count: int) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    recent = lines[-max(max_count, 0):] if max_count > 0 else []
    decisions: list[dict[str, Any]] = []
    for line in recent:
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            decisions.append(payload)
    return decisions


def derive_next_actions(
    state: dict[str, Any],
    review: dict[str, Any],
) -> list[str]:
    actions: list[str] = []
    missing_artifacts = review.get("missing_artifacts")
    if isinstance(missing_artifacts, list) and missing_artifacts:
        for artifact in missing_artifacts[:3]:
            if isinstance(artifact, str) and artifact:
                actions.append(f"Restore or regenerate `{artifact}`.")
    next_recommended_action = review.get("next_recommended_action")
    if isinstance(next_recommended_action, str) and next_recommended_action:
        actions.append(next_recommended_action)
    next_stage = state.get("next_stage")
    if isinstance(next_stage, str) and next_stage:
        actions.append(f"Run `{next_stage}` and re-run `review_project.py`.")
    if not actions:
        actions.append("Run creative_design.")
        actions.append("Run review_project.py, then observe_project.py.")
    unique_actions: list[str] = []
    for action in actions:
        if action not in unique_actions:
            unique_actions.append(action)
    return unique_actions


def build_handoff_markdown(
    *,
    project_dir: pathlib.Path,
    state: dict[str, Any],
    plan: dict[str, Any],
    review: dict[str, Any],
    observer_summary: str,
    decisions: list[dict[str, Any]],
) -> str:
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    workflow = str(plan.get("workflow", "video_pipeline"))
    current_stage = str(state.get("current_stage") or "none")
    next_stage = str(state.get("next_stage") or "creative_design")
    completed_stages = state.get("completed_stages", [])
    if not isinstance(completed_stages, list):
        completed_stages = []
    planned_stages = plan.get("planned_stages", [])
    if not isinstance(planned_stages, list):
        planned_stages = []

    decision_lines = ["- none"]
    if decisions:
        decision_lines = []
        for decision in decisions:
            timestamp = str(decision.get("timestamp", ""))
            decision_type = str(decision.get("decision_type", "unknown"))
            reason = str(decision.get("reason", ""))
            suffix = f": {reason}" if reason else ""
            decision_lines.append(f"- `{timestamp}` `{decision_type}`{suffix}")

    observer_section = observer_summary.strip()
    if not observer_section:
        observer_section = "Observer summary missing. Run `observe_project.py` to refresh."

    actions = derive_next_actions(state, review)
    action_lines = [f"{index}. {action}" for index, action in enumerate(actions, start=1)]

    return "\n".join(
        [
            "# Session Handoff Pack",
            "",
            f"- Project: `{project_dir.name}`",
            f"- Generated at (UTC): `{generated_at}`",
            f"- Workflow: `{workflow}`",
            f"- Current stage: `{current_stage}`",
            f"- Next stage: `{next_stage}`",
            f"- Review status: `{review.get('status', 'unknown')}`",
            "",
            "## Stage Snapshot",
            "",
            f"- Completed stages: {', '.join(f'`{stage}`' for stage in completed_stages) or 'none'}",
            f"- Planned stages: {', '.join(f'`{stage}`' for stage in planned_stages) or 'none'}",
            "",
            "## Recent Decisions",
            "",
            *decision_lines,
            "",
            "## Observer Summary",
            "",
            observer_section,
            "",
            "## Next Actions",
            "",
            *action_lines,
            "",
            "## Thread Bootstrap Prompt",
            "",
            (
                "Use this project state as the single source of truth. "
                "Start from `Next Actions` and avoid re-reading old chat history."
            ),
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    state = read_json(
        project_dir / "orchestration" / "state.json",
        {
            "current_stage": None,
            "completed_stages": [],
            "skipped_stages": [],
            "last_failed_stage": None,
            "next_stage": None,
        },
    )
    plan = read_json(
        project_dir / "orchestration" / "plan.json",
        {
            "workflow": "video_pipeline",
            "planned_stages": [],
            "optional_stages": [],
            "disabled_stages": [],
            "metadata": {},
        },
    )
    review = read_json(
        project_dir / "review" / "review-report.json",
        {
            "status": "unknown",
            "missing_artifacts": [],
            "warnings": [],
            "next_recommended_action": "Run creative_design.",
        },
    )
    observer_path = project_dir / "review" / "observer-summary.md"
    observer_summary = observer_path.read_text(encoding="utf-8") if observer_path.is_file() else ""

    decisions = read_recent_decisions(
        project_dir / "orchestration" / "decisions.jsonl",
        max_count=args.decisions_tail,
    )
    markdown = build_handoff_markdown(
        project_dir=project_dir,
        state=state,
        plan=plan,
        review=review,
        observer_summary=observer_summary,
        decisions=decisions,
    )

    output_path = pathlib.Path(args.output)
    if not output_path.is_absolute():
        output_path = project_dir / output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown, encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
