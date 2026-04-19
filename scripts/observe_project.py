#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys


ARTIFACT_LINES = {
    "video_pipeline": [
        ("brief/creative-brief.md", "Creative brief"),
        ("input/input.json", "Input"),
        ("script/script.json", "Script"),
        ("audio/voiceover.json", "Voiceover"),
        ("audio/bgm-selection.json", "BGM selection"),
        ("audio/beat-grid.json", "Beat grid"),
        ("timeline/global-timeline.json", "Global timeline"),
        ("storyboard/storyboard.json", "Storyboard"),
        ("keyframes/keyframes.json", "Keyframes"),
        ("prompts/prompts.json", "Prompts"),
        ("assets/manifest.json", "Asset manifest"),
        ("assets/image-requests.json", "Image requests"),
        ("assets/image-usage.json", "Image usage"),
        ("subtitles/subtitles.json", "Subtitles"),
        ("video/clips.json", "Video clips"),
        ("timeline/timeline.json", "Timeline"),
        ("outputs/render-plan.json", "Render plan"),
        ("review/review-report.json", "Review report"),
    ],
    "material_editorial": [
        ("assets/source-manifest.json", "Source manifest"),
        ("orchestration/checkpoints.json", "Checkpoints"),
        ("orchestration/subtasks.json", "Subtasks"),
        ("orchestration/context-index.json", "Context index"),
        ("analysis/material-catalog.json", "Material catalog"),
        ("analysis/relationship-graph.json", "Relationship graph"),
        ("analysis/style-report.json", "Style report"),
        ("brief/creative-fit-report.json", "Creative fit report"),
        ("storyboard/storyboard-draft.json", "Storyboard draft"),
        ("adjustments/adjustment-plan.json", "Adjustment plan"),
        ("review/review-report.json", "Review report"),
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a human-readable project observer summary.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def read_json(path: pathlib.Path, fallback: object) -> object:
    if not path.is_file():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def read_recent_decision(path: pathlib.Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


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
    review = read_json(
        project_dir / "review" / "review-report.json",
        {
            "status": "in_progress",
            "checked_at": "",
            "completed_stages": [],
            "missing_artifacts": [],
            "warnings": [],
            "next_recommended_action": "Run creative_design.",
        },
    )
    decision = read_recent_decision(project_dir / "orchestration" / "decisions.jsonl")
    workflow = str(state.get("workflow") or "video_pipeline")

    artifact_lines = []
    for relative_path, label in ARTIFACT_LINES.get(workflow, ARTIFACT_LINES["video_pipeline"]):
        exists = (project_dir / relative_path).is_file()
        status_label = "present" if exists else "missing"
        artifact_lines.append(f"- {label}: `{status_label}` (`{relative_path}`)")

    decision_line = "- Recent decision: none"
    if decision:
        decision_line = (
            f"- Recent decision: `{decision.get('decision_type', 'unknown')}` - "
            f"{decision.get('reason', '')}"
        )

    summary = "\n".join(
        [
            "# Project Overview",
            "",
            f"- Project: `{project_dir.name}`",
            f"- Workflow: `{workflow}`",
            f"- Current stage: `{state.get('current_stage') or 'none'}`",
            f"- Next stage: `{state.get('next_stage') or 'creative_design'}`",
            f"- Review status: `{review.get('status', 'in_progress')}`",
            f"- Last checked: `{review.get('checked_at', '')}`",
            f"- Checkpoint status: `{state.get('checkpoint_status') or 'n/a'}`",
            "",
            "## Stage Progress",
            "",
            f"- Completed stages: {', '.join(f'`{stage}`' for stage in state.get('completed_stages', [])) or 'none'}",
            f"- Skipped stages: {', '.join(f'`{stage}`' for stage in state.get('skipped_stages', [])) or 'none'}",
            f"- Last failed stage: `{state.get('last_failed_stage') or 'none'}`",
            f"- Active batches: {', '.join(f'`{batch_id}`' for batch_id in state.get('active_batch_ids', [])) or 'none'}",
            "",
            "## Key Artifacts",
            "",
            *artifact_lines,
            "",
            "## Recent Decisions",
            "",
            decision_line,
            "",
            "## Review Result",
            "",
            f"- Review status: `{review.get('status', 'in_progress')}`",
            f"- Missing artifacts: {', '.join(f'`{path}`' for path in review.get('missing_artifacts', [])) or 'none'}",
            f"- Warnings: {', '.join(review.get('warnings', [])) or 'none'}",
            "",
            "## Next Step",
            "",
            f"- {review.get('next_recommended_action', 'Run creative_design.')}",
            "",
        ]
    )

    review_dir = project_dir / "review"
    review_dir.mkdir(parents=True, exist_ok=True)
    summary_path = review_dir / "observer-summary.md"
    summary_path.write_text(summary + "\n", encoding="utf-8")

    print(summary_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
