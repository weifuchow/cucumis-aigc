#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
from collections import Counter
from typing import Any

from material_workflow import (
    append_decision,
    ensure_material_workspace,
    load_checkpoints,
    load_context_index,
    load_state,
    load_subtasks,
    now_iso,
    read_json,
    update_checkpoint_status,
    write_event,
    write_json,
    write_task_card,
)


STYLE_HINTS = {
    "vintage": ["retro", "film", "old", "archive", "nostalgia", "memory"],
    "cinematic": ["cinematic", "drama", "moody", "epic", "movie"],
    "warm": ["sunset", "golden", "warm", "family", "wedding"],
    "cool": ["night", "blue", "cold", "city", "tech"],
    "documentary": ["interview", "report", "record", "documentary", "speech"],
    "travel": ["trip", "travel", "journey", "road", "vacation"],
}

ROLE_HINTS = {
    "establishing": ["city", "street", "room", "landscape", "travel"],
    "portrait": ["portrait", "selfie", "people", "family", "wedding"],
    "detail": ["close", "product", "food", "detail"],
    "dialogue": ["interview", "speech", "talk", "podcast"],
    "bridge": ["broll", "cutaway", "transition", "journey", "road"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate compact understanding outputs for one or more material batches.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--batch-id", default=None, help="Specific batch id to process.")
    parser.add_argument("--all-pending", action="store_true", help="Process every pending batch.")
    parser.add_argument("--force", action="store_true", help="Re-run even if batch is already completed.")
    return parser.parse_args()


def infer_style_tags(tags: list[str], title: str) -> list[str]:
    haystack = " ".join([title, *tags]).lower()
    found: list[str] = []
    for label, hints in STYLE_HINTS.items():
        if any(hint in haystack for hint in hints):
            found.append(label)
    if not found:
        found.append("neutral")
    return found[:3]


def infer_roles(tags: list[str], title: str, media_type: str) -> list[str]:
    haystack = " ".join([title, *tags]).lower()
    roles: list[str] = []
    for label, hints in ROLE_HINTS.items():
        if any(hint in haystack for hint in hints):
            roles.append(label)
    if media_type == "audio" and "dialogue" not in roles:
        roles.append("voice_reference")
    if media_type == "document" and "bridge" not in roles:
        roles.append("reference")
    if not roles:
        roles.append("supporting")
    return roles[:3]


def infer_treatments(media_type: str, style_tags: list[str]) -> list[str]:
    recommendations = {
        "image": ["crop_reframe", "color_grade", "subtitle_overlay"],
        "video": ["color_grade", "speed_ramp", "stabilize_if_needed"],
        "audio": ["noise_reduce", "trim_silence", "duck_under_narration"],
        "document": ["extract_quotes", "story_reference"],
    }.get(media_type, ["manual_review"])
    if "vintage" in style_tags and "film_grain" not in recommendations:
        recommendations.append("film_grain")
    if "cinematic" in style_tags and "contrast_boost" not in recommendations:
        recommendations.append("contrast_boost")
    return recommendations[:4]


def summarize_asset(asset: dict[str, Any]) -> dict[str, Any]:
    tags = asset.get("tags", [])
    if not isinstance(tags, list):
        tags = []
    title = str(asset.get("title_guess", "")).strip() or pathlib.Path(str(asset.get("relative_path", ""))).stem
    media_type = str(asset.get("media_type", "unknown"))
    style_tags = infer_style_tags(tags, title)
    narrative_roles = infer_roles(tags, title, media_type)
    treatments = infer_treatments(media_type, style_tags)
    probe = asset.get("probe", {})
    if not isinstance(probe, dict):
        probe = {}
    orientation = "unknown"
    width = probe.get("width")
    height = probe.get("height")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        orientation = "portrait" if height > width else "landscape"

    continuity_risks: list[str] = []
    if orientation == "landscape":
        continuity_risks.append("可能需要裁切到竖版时间轴")
    if media_type == "audio":
        continuity_risks.append("需确认是否保留原声或仅作参考")
    if media_type == "document":
        continuity_risks.append("内容需人工确认是否适合作为字幕或旁白依据")

    summary = f"{media_type} asset `{asset.get('relative_path', '')}`，主题偏向 {title or '未命名素材'}。"
    return {
        "asset_id": asset.get("asset_id"),
        "relative_path": asset.get("relative_path"),
        "media_type": media_type,
        "summary": summary,
        "content_tags": tags[:8],
        "style_tags": style_tags,
        "narrative_roles": narrative_roles,
        "recommended_treatments": treatments,
        "continuity_risks": continuity_risks,
        "probe": probe,
    }


def build_relationships(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    edges: list[dict[str, Any]] = []
    for index, left in enumerate(items):
        for right in items[index + 1 :]:
            if left.get("asset_id") == right.get("asset_id"):
                continue
            relation_reasons: list[str] = []
            left_path = pathlib.Path(str(left.get("relative_path", "")))
            right_path = pathlib.Path(str(right.get("relative_path", "")))
            if left_path.parent == right_path.parent and left_path.parent != pathlib.Path("."):
                relation_reasons.append("same_parent_dir")
            shared_tags = set(left.get("content_tags", [])) & set(right.get("content_tags", []))
            if len(shared_tags) >= 2:
                relation_reasons.append("shared_tags")
            shared_styles = set(left.get("style_tags", [])) & set(right.get("style_tags", []))
            if relation_reasons or shared_styles:
                edges.append(
                    {
                        "source": left.get("asset_id"),
                        "target": right.get("asset_id"),
                        "relation": "candidate_sequence" if "same_parent_dir" in relation_reasons else "style_match",
                        "confidence": 0.55 if relation_reasons else 0.35,
                        "reasons": relation_reasons or ["shared_style"],
                    }
                )
    return edges[:200]


def select_tasks(subtasks: dict[str, Any], batch_id: str | None, all_pending: bool, force: bool) -> list[dict[str, Any]]:
    tasks = subtasks.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    selected: list[dict[str, Any]] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = str(task.get("status", "pending"))
        if batch_id and task.get("task_id") != batch_id:
            continue
        if not force and status == "completed" and not batch_id:
            continue
        if not force and status == "completed" and batch_id:
            selected.append(task)
            break
        if batch_id:
            selected.append(task)
            break
        if all_pending:
            if status in {"pending", "failed", "in_progress"}:
                selected.append(task)
        elif status in {"pending", "failed", "in_progress"}:
            selected.append(task)
            break
    return selected


def consolidate_outputs(project_dir: pathlib.Path, tasks: list[dict[str, Any]]) -> None:
    catalogs: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    for task in tasks:
        if str(task.get("status")) != "completed":
            continue
        batch_id = str(task.get("task_id"))
        catalog = read_json(project_dir / "analysis" / "batches" / f"{batch_id}.catalog.json", {})
        relationships = read_json(project_dir / "analysis" / "batches" / f"{batch_id}.relationships.json", {})
        if isinstance(catalog, dict):
            assets = catalog.get("assets", [])
            if isinstance(assets, list):
                catalogs.extend(asset for asset in assets if isinstance(asset, dict))
        if isinstance(relationships, dict):
            rel_edges = relationships.get("edges", [])
            if isinstance(rel_edges, list):
                edges.extend(edge for edge in rel_edges if isinstance(edge, dict))

    style_counter: Counter[str] = Counter()
    media_counter: Counter[str] = Counter()
    for asset in catalogs:
        media_counter.update([str(asset.get("media_type", "unknown"))])
        style_counter.update(str(tag) for tag in asset.get("style_tags", []) if isinstance(tag, str))

    catalog_payload = {
        "version": 1,
        "generated_at": now_iso(),
        "workflow": "material_editorial",
        "assets": catalogs,
        "summary": {
            "asset_count": len(catalogs),
            "media_breakdown": dict(media_counter),
            "top_style_tags": [style for style, _count in style_counter.most_common(8)],
        },
    }
    graph_payload = {
        "version": 1,
        "generated_at": now_iso(),
        "nodes": [
            {
                "asset_id": asset.get("asset_id"),
                "label": asset.get("relative_path"),
                "media_type": asset.get("media_type"),
            }
            for asset in catalogs
        ],
        "edges": edges,
        "summary": {
            "edge_count": len(edges),
            "top_relation_types": Counter(str(edge.get("relation", "unknown")) for edge in edges).most_common(6),
        },
    }
    style_report = {
        "version": 1,
        "generated_at": now_iso(),
        "dominant_styles": [style for style, _count in style_counter.most_common(8)],
        "media_breakdown": dict(media_counter),
        "risks": [
            "混合横竖素材时需在分镜阶段统一裁切策略。",
            "涉及 AI 调整的镜头应先记录 prompt 和允许修改边界。",
        ],
    }
    write_json(project_dir / "analysis" / "material-catalog.json", catalog_payload)
    write_json(project_dir / "analysis" / "relationship-graph.json", graph_payload)
    write_json(project_dir / "analysis" / "style-report.json", style_report)


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    if not project_dir.exists():
        raise SystemExit(f"project not found: {project_dir}")

    ensure_material_workspace(project_dir)
    subtasks = load_subtasks(project_dir)
    selected_tasks = select_tasks(subtasks, args.batch_id, args.all_pending, args.force)
    if not selected_tasks:
        raise SystemExit("no matching batch tasks found")

    write_event(
        project_dir,
        "workflow.stage.started",
        {
            "stage": "material_batch_understanding",
            "batch_ids": [task.get("task_id") for task in selected_tasks],
        },
    )

    for task in selected_tasks:
        batch_id = str(task.get("task_id"))
        task["status"] = "in_progress"
        task["attempts"] = int(task.get("attempts", 0)) + 1
        batch_manifest = read_json(project_dir / "analysis" / "batches" / f"{batch_id}.manifest.json", {})
        if not isinstance(batch_manifest, dict):
            task["status"] = "failed"
            task["notes"] = "batch manifest missing or invalid"
            continue
        assets = batch_manifest.get("assets", [])
        if not isinstance(assets, list):
            assets = []
        summaries = [summarize_asset(asset) for asset in assets if isinstance(asset, dict)]
        relationships = build_relationships(summaries)
        batch_catalog = {
            "batch_id": batch_id,
            "generated_at": now_iso(),
            "group_key": batch_manifest.get("group_key", "."),
            "assets": summaries,
            "batch_summary": {
                "asset_count": len(summaries),
                "style_tags": Counter(
                    tag
                    for item in summaries
                    for tag in item.get("style_tags", [])
                    if isinstance(tag, str)
                ).most_common(6),
            },
        }
        batch_relationships = {
            "batch_id": batch_id,
            "generated_at": now_iso(),
            "edges": relationships,
        }
        write_json(project_dir / "analysis" / "batches" / f"{batch_id}.catalog.json", batch_catalog)
        write_json(project_dir / "analysis" / "batches" / f"{batch_id}.relationships.json", batch_relationships)
        task["status"] = "completed"
        task["notes"] = f"Generated catalog and relationship drafts for {len(summaries)} assets."

    subtasks["updated_at"] = now_iso()
    write_json(project_dir / "orchestration" / "subtasks.json", subtasks)

    consolidate_outputs(project_dir, subtasks.get("tasks", []))

    remaining = [
        task for task in subtasks.get("tasks", []) if isinstance(task, dict) and task.get("status") != "completed"
    ]
    checkpoints = load_checkpoints(project_dir)
    if remaining:
        checkpoints = update_checkpoint_status(checkpoints, "catalog_confirmed", "locked")
        next_step = (
            "继续处理剩余批次，直到生成完整的素材目录和关系图。"
        )
        waiting_items = [f"剩余待处理批次：{', '.join(str(task.get('task_id')) for task in remaining[:3])}"]
    else:
        checkpoints = update_checkpoint_status(checkpoints, "catalog_confirmed", "pending")
        checkpoints = update_checkpoint_status(checkpoints, "relationship_confirmed", "pending")
        next_step = "人工复核素材目录与关系图，确认后再进入 creative_alignment。"
        waiting_items = [
            "确认 analysis/material-catalog.json 的描述是否准确。",
            "确认 analysis/relationship-graph.json 的串联关系是否合理。",
        ]
    write_json(project_dir / "orchestration" / "checkpoints.json", checkpoints)

    state = load_state(project_dir)
    completed = list(state.get("completed_stages", []))
    if "material_ingest" not in completed:
        completed.append("material_ingest")
    if not remaining and "material_batch_understanding" not in completed:
        completed.append("material_batch_understanding")
    state.update(
        {
            "current_stage": "material_batch_understanding",
            "completed_stages": completed,
            "next_stage": "material_batch_understanding" if remaining else "relationship_mapping",
            "workflow": "material_editorial",
            "phase": "analysis" if remaining else "review",
            "checkpoint_status": "pending",
            "active_batch_ids": [str(task.get("task_id")) for task in remaining[:3]],
            "resume_from": (
                f"analysis/batches/{remaining[0].get('task_id')}.manifest.json"
                if remaining
                else "analysis/material-catalog.json"
            ),
        }
    )
    write_json(project_dir / "orchestration" / "state.json", state)

    context_index = load_context_index(project_dir)
    context_index["generated_at"] = now_iso()
    context_index["active_context"] = [
        "orchestration/task-card.md",
        "orchestration/state.json",
        "orchestration/checkpoints.json",
        "analysis/material-catalog.json",
        "analysis/relationship-graph.json",
    ]
    write_json(project_dir / "orchestration" / "context-index.json", context_index)

    append_decision(
        project_dir,
        "material_batch_understanding.progressed",
        "Updated batch understanding outputs and refreshed consolidated context files.",
        {
            "processed_batches": [task.get("task_id") for task in selected_tasks],
            "remaining_batches": [task.get("task_id") for task in remaining],
        },
    )
    write_task_card(
        project_dir,
        current_stage="material_batch_understanding",
        completed_stages=completed,
        next_step=next_step,
        waiting_items=waiting_items,
        blockers=["无"],
    )
    write_event(
        project_dir,
        "workflow.stage.completed",
        {
            "stage": "material_batch_understanding",
            "processed_batches": [task.get("task_id") for task in selected_tasks],
            "remaining_batches": [task.get("task_id") for task in remaining],
        },
    )
    print(project_dir / "analysis" / "material-catalog.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
