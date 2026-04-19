#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
import subprocess
from collections import OrderedDict
from typing import Any

from material_workflow import (
    DEFAULT_PLAN,
    WORKFLOW_NAME,
    WORKFLOW_STAGES,
    append_decision,
    ensure_material_workspace,
    guess_title,
    load_checkpoints,
    load_context_index,
    load_plan,
    load_state,
    now_iso,
    stable_id,
    tokenize_hint,
    update_checkpoint_status,
    write_event,
    write_json,
    write_task_card,
)


SUPPORTED_TYPES = {
    "image": {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".heic", ".tiff"},
    "video": {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"},
    "audio": {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"},
    "document": {".txt", ".md", ".pdf", ".docx", ".srt"},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan a raw material folder and create resumable batches.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--source-dir", required=True, help="Folder that contains user materials.")
    parser.add_argument("--batch-size", type=int, default=24, help="Maximum assets per batch.")
    parser.add_argument(
        "--recursive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Recursively scan subdirectories.",
    )
    return parser.parse_args()


def media_type_for(path: pathlib.Path) -> str | None:
    suffix = path.suffix.lower()
    for media_type, suffixes in SUPPORTED_TYPES.items():
        if suffix in suffixes:
            return media_type
    return None


def probe_media(path: pathlib.Path, media_type: str) -> dict[str, Any]:
    if media_type not in {"image", "video", "audio"}:
        return {}
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "default=noprint_wrappers=1:nokey=0",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if result.returncode != 0:
        return {}
    payload: dict[str, Any] = {}
    for raw_line in result.stdout.splitlines():
        if "=" not in raw_line:
            continue
        key, value = raw_line.split("=", 1)
        if key == "duration":
            try:
                payload["duration_seconds"] = round(float(value), 2)
            except ValueError:
                continue
        elif key in {"width", "height"}:
            try:
                payload[key] = int(value)
            except ValueError:
                continue
    return payload


def collect_assets(source_dir: pathlib.Path, recursive: bool) -> list[dict[str, Any]]:
    assets: list[dict[str, Any]] = []
    iterator = source_dir.rglob("*") if recursive else source_dir.glob("*")
    for path in sorted(iterator):
        if not path.is_file():
            continue
        media_type = media_type_for(path)
        if media_type is None:
            continue
        stat = path.stat()
        relative = path.relative_to(source_dir)
        asset_id = stable_id("asset", str(relative))
        title_guess = guess_title(path)
        tags = tokenize_hint(" ".join(relative.parts))
        assets.append(
            {
                "asset_id": asset_id,
                "path": str(path.resolve()),
                "relative_path": str(relative),
                "parent_dir": str(relative.parent) if str(relative.parent) != "." else "",
                "media_type": media_type,
                "extension": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
                "title_guess": title_guess,
                "description_hint": f"{media_type} asset from {relative.parent or source_dir.name}",
                "tags": tags,
                "probe": probe_media(path, media_type),
            }
        )
    return assets


def build_batches(assets: list[dict[str, Any]], batch_size: int) -> list[dict[str, Any]]:
    grouped: OrderedDict[tuple[str, str], list[dict[str, Any]]] = OrderedDict()
    for asset in assets:
        group_key = (str(asset.get("parent_dir", "")), str(asset.get("media_type", "unknown")))
        grouped.setdefault(group_key, []).append(asset)

    batches: list[dict[str, Any]] = []
    batch_index = 1
    for (parent_dir, media_type), items in grouped.items():
        for offset in range(0, len(items), batch_size):
            chunk = items[offset : offset + batch_size]
            batch_id = f"batch-{batch_index:03d}"
            batches.append(
                {
                    "batch_id": batch_id,
                    "group_key": parent_dir or ".",
                    "media_type": media_type,
                    "asset_ids": [asset["asset_id"] for asset in chunk],
                    "assets": chunk,
                }
            )
            batch_index += 1
    return batches


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    source_dir = pathlib.Path(args.source_dir).resolve()

    if not project_dir.exists():
        raise SystemExit(f"project not found: {project_dir}")
    if not source_dir.exists():
        raise SystemExit(f"source directory not found: {source_dir}")

    ensure_material_workspace(project_dir)
    write_event(project_dir, "workflow.stage.started", {"stage": "material_ingest", "source_dir": str(source_dir)})

    assets = collect_assets(source_dir, recursive=args.recursive)
    batches = build_batches(assets, batch_size=max(args.batch_size, 1))

    manifest = {
        "version": 1,
        "generated_at": now_iso(),
        "source_root": str(source_dir),
        "scan": {
            "recursive": args.recursive,
            "batch_size": max(args.batch_size, 1),
            "total_assets": len(assets),
            "total_batches": len(batches),
        },
        "assets": assets,
    }
    write_json(project_dir / "assets" / "source-manifest.json", manifest)

    subtask_items: list[dict[str, Any]] = []
    evidence_files: list[str] = ["assets/source-manifest.json"]
    for batch in batches:
        batch_path = project_dir / "analysis" / "batches" / f"{batch['batch_id']}.manifest.json"
        batch_payload = {
            "batch_id": batch["batch_id"],
            "generated_at": now_iso(),
            "group_key": batch["group_key"],
            "media_type": batch["media_type"],
            "asset_ids": batch["asset_ids"],
            "assets": batch["assets"],
        }
        write_json(batch_path, batch_payload)
        evidence_files.append(str(batch_path.relative_to(project_dir)))
        subtask_items.append(
            {
                "task_id": batch["batch_id"],
                "stage": "material_batch_understanding",
                "status": "pending",
                "asset_count": len(batch["assets"]),
                "asset_ids": batch["asset_ids"],
                "input_paths": [str(batch_path.relative_to(project_dir))],
                "output_paths": [
                    f"analysis/batches/{batch['batch_id']}.catalog.json",
                    f"analysis/batches/{batch['batch_id']}.relationships.json",
                ],
                "attempts": 0,
                "notes": "",
            }
        )

    checkpoints = load_checkpoints(project_dir)
    checkpoints = update_checkpoint_status(checkpoints, "scan_scope_confirmed", "pending")
    checkpoints = update_checkpoint_status(checkpoints, "catalog_confirmed", "locked")
    checkpoints = update_checkpoint_status(checkpoints, "relationship_confirmed", "locked")
    checkpoints = update_checkpoint_status(checkpoints, "storyboard_confirmed", "locked")
    checkpoints = update_checkpoint_status(checkpoints, "adjustment_plan_confirmed", "locked")
    write_json(project_dir / "orchestration" / "checkpoints.json", checkpoints)

    subtasks = {"workflow": WORKFLOW_NAME, "updated_at": now_iso(), "tasks": subtask_items}
    write_json(project_dir / "orchestration" / "subtasks.json", subtasks)

    context_index = load_context_index(project_dir)
    context_index["generated_at"] = now_iso()
    context_index["evidence_files"] = evidence_files
    context_index["active_context"] = [
        "orchestration/task-card.md",
        "orchestration/state.json",
        "orchestration/checkpoints.json",
        "assets/source-manifest.json",
    ]
    write_json(project_dir / "orchestration" / "context-index.json", context_index)

    plan = load_plan(project_dir)
    plan["workflow"] = WORKFLOW_NAME
    plan["planned_stages"] = list(WORKFLOW_STAGES)
    plan["optional_stages"] = ["audio_foundation", "timeline_builder"]
    plan["disabled_stages"] = []
    metadata = plan.setdefault("metadata", {})
    metadata["source_dir"] = str(source_dir)
    metadata["total_assets"] = len(assets)
    metadata["total_batches"] = len(batches)
    write_json(project_dir / "orchestration" / "plan.json", plan)

    state = load_state(project_dir)
    completed = list(dict.fromkeys([*(state.get("completed_stages", [])), "material_ingest"]))
    state.update(
        {
            "current_stage": "material_ingest",
            "completed_stages": completed,
            "next_stage": "material_batch_understanding",
            "workflow": WORKFLOW_NAME,
            "phase": "analysis",
            "checkpoint_status": "pending",
            "active_batch_ids": [batch["batch_id"] for batch in batches[:3]],
            "resume_from": "assets/source-manifest.json",
            "last_handoff_path": "orchestration/session-handoff.md",
        }
    )
    write_json(project_dir / "orchestration" / "state.json", state)

    append_decision(
        project_dir,
        "material_ingest.initialized",
        "Scanned source directory and split materials into resumable analysis batches.",
        {
            "source_dir": str(source_dir),
            "asset_count": len(assets),
            "batch_count": len(batches),
        },
    )
    write_task_card(
        project_dir,
        current_stage="material_ingest",
        completed_stages=completed,
        next_step=(
            "先确认素材扫描范围，再从待处理批次开始运行 "
            "`python3 scripts/run_material_batch_understanding.py --project <name>`。"
        ),
        waiting_items=[
            "确认是否需要排除无关目录、重复素材或临时文件。",
            f"待分析批次：{', '.join(batch['batch_id'] for batch in batches[:3]) or '无'}",
        ],
        blockers=["无"],
    )
    write_event(
        project_dir,
        "workflow.stage.completed",
        {
            "stage": "material_ingest",
            "asset_count": len(assets),
            "batch_count": len(batches),
        },
    )
    print(project_dir / "assets" / "source-manifest.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
