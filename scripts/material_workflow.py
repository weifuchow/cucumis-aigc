#!/usr/bin/env python3

from __future__ import annotations

import datetime as dt
import hashlib
import json
import pathlib
import re
from typing import Any


WORKFLOW_NAME = "material_editorial"
WORKFLOW_STAGES = [
    "material_ingest",
    "material_batch_understanding",
    "relationship_mapping",
    "creative_alignment",
    "storyboard_draft",
    "adjustment_planning",
    "human_checkpoints",
    "audio_foundation",
    "timeline_builder",
]

DEFAULT_STATE = {
    "current_stage": None,
    "completed_stages": [],
    "skipped_stages": [],
    "last_failed_stage": None,
    "next_stage": None,
    "workflow": WORKFLOW_NAME,
    "phase": "setup",
    "checkpoint_status": "pending",
    "active_batch_ids": [],
    "resume_from": None,
    "last_handoff_path": "orchestration/session-handoff.md",
}

DEFAULT_PLAN = {
    "workflow": WORKFLOW_NAME,
    "planned_stages": WORKFLOW_STAGES,
    "optional_stages": ["audio_foundation", "timeline_builder"],
    "disabled_stages": [],
    "metadata": {},
}

DEFAULT_CHECKPOINTS = {
    "workflow": WORKFLOW_NAME,
    "updated_at": "",
    "items": [
        {
            "checkpoint_id": "scan_scope_confirmed",
            "label": "素材扫描范围确认",
            "stage": "material_ingest",
            "status": "pending",
            "notes": "确认是否需要排除无关目录、重复文件或临时素材。",
        },
        {
            "checkpoint_id": "catalog_confirmed",
            "label": "素材理解确认",
            "stage": "material_batch_understanding",
            "status": "locked",
            "notes": "确认元数据描述、风格判断和明显误判。",
        },
        {
            "checkpoint_id": "relationship_confirmed",
            "label": "关系链确认",
            "stage": "relationship_mapping",
            "status": "locked",
            "notes": "确认人物/地点/时间线串联是否合理。",
        },
        {
            "checkpoint_id": "storyboard_confirmed",
            "label": "分镜草案确认",
            "stage": "storyboard_draft",
            "status": "locked",
            "notes": "确认故事线、素材缺口和桥接镜头。",
        },
        {
            "checkpoint_id": "adjustment_plan_confirmed",
            "label": "调整方案确认",
            "stage": "adjustment_planning",
            "status": "locked",
            "notes": "确认哪些镜头允许 AI 调整，哪些需要人工补充。",
        },
    ],
}

DEFAULT_SUBTASKS = {
    "workflow": WORKFLOW_NAME,
    "updated_at": "",
    "tasks": [],
}

DEFAULT_CONTEXT_INDEX = {
    "workflow": WORKFLOW_NAME,
    "generated_at": "",
    "control_files": [
        "orchestration/task-card.md",
        "orchestration/state.json",
        "orchestration/checkpoints.json",
        "orchestration/subtasks.json",
    ],
    "summary_files": [
        "analysis/material-catalog.json",
        "analysis/relationship-graph.json",
        "analysis/style-report.json",
        "brief/creative-fit-report.json",
        "storyboard/storyboard-draft.json",
        "adjustments/adjustment-plan.json",
    ],
    "evidence_files": [],
    "handoff_files": ["orchestration/session-handoff.md"],
    "active_context": [
        "orchestration/task-card.md",
        "orchestration/state.json",
        "orchestration/checkpoints.json",
    ],
}


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def read_json(path: pathlib.Path, fallback: Any) -> Any:
    if not path.is_file():
        return fallback
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def write_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def append_jsonl(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def ensure_material_workspace(project_dir: pathlib.Path) -> None:
    for relative in (
        "analysis/batches",
        "assets",
        "brief",
        "storyboard",
        "adjustments",
        "orchestration",
        "events",
        "review",
    ):
        (project_dir / relative).mkdir(parents=True, exist_ok=True)


def load_state(project_dir: pathlib.Path) -> dict[str, Any]:
    payload = read_json(project_dir / "orchestration" / "state.json", DEFAULT_STATE)
    if not isinstance(payload, dict):
        payload = dict(DEFAULT_STATE)
    merged = dict(DEFAULT_STATE)
    merged.update(payload)
    return merged


def load_plan(project_dir: pathlib.Path) -> dict[str, Any]:
    payload = read_json(project_dir / "orchestration" / "plan.json", DEFAULT_PLAN)
    if not isinstance(payload, dict):
        payload = dict(DEFAULT_PLAN)
    merged = dict(DEFAULT_PLAN)
    merged.update(payload)
    metadata = merged.get("metadata")
    if not isinstance(metadata, dict):
        merged["metadata"] = {}
    return merged


def load_checkpoints(project_dir: pathlib.Path) -> dict[str, Any]:
    payload = read_json(project_dir / "orchestration" / "checkpoints.json", DEFAULT_CHECKPOINTS)
    if not isinstance(payload, dict):
        payload = dict(DEFAULT_CHECKPOINTS)
    merged = {
        "workflow": WORKFLOW_NAME,
        "updated_at": payload.get("updated_at", ""),
        "items": payload.get("items", DEFAULT_CHECKPOINTS["items"]),
    }
    if not isinstance(merged["items"], list):
        merged["items"] = list(DEFAULT_CHECKPOINTS["items"])
    return merged


def load_subtasks(project_dir: pathlib.Path) -> dict[str, Any]:
    payload = read_json(project_dir / "orchestration" / "subtasks.json", DEFAULT_SUBTASKS)
    if not isinstance(payload, dict):
        payload = dict(DEFAULT_SUBTASKS)
    merged = {
        "workflow": WORKFLOW_NAME,
        "updated_at": payload.get("updated_at", ""),
        "tasks": payload.get("tasks", []),
    }
    if not isinstance(merged["tasks"], list):
        merged["tasks"] = []
    return merged


def load_context_index(project_dir: pathlib.Path) -> dict[str, Any]:
    payload = read_json(project_dir / "orchestration" / "context-index.json", DEFAULT_CONTEXT_INDEX)
    if not isinstance(payload, dict):
        payload = dict(DEFAULT_CONTEXT_INDEX)
    merged = dict(DEFAULT_CONTEXT_INDEX)
    merged.update(payload)
    return merged


def write_event(project_dir: pathlib.Path, event_type: str, payload: dict[str, Any]) -> None:
    append_jsonl(
        project_dir / "events" / "events.jsonl",
        {
            "event_type": event_type,
            "timestamp": now_iso(),
            "payload": payload,
        },
    )


def append_decision(
    project_dir: pathlib.Path,
    decision_type: str,
    reason: str,
    payload: dict[str, Any] | None = None,
) -> None:
    append_jsonl(
        project_dir / "orchestration" / "decisions.jsonl",
        {
            "timestamp": now_iso(),
            "decision_type": decision_type,
            "reason": reason,
            "payload": payload or {},
        },
    )


def update_checkpoint_status(
    checkpoints: dict[str, Any],
    checkpoint_id: str,
    status: str,
) -> dict[str, Any]:
    items = checkpoints.get("items", [])
    if not isinstance(items, list):
        return checkpoints
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get("checkpoint_id") == checkpoint_id:
            item["status"] = status
    checkpoints["updated_at"] = now_iso()
    return checkpoints


def write_task_card(
    project_dir: pathlib.Path,
    *,
    current_stage: str | None,
    completed_stages: list[str],
    next_step: str,
    waiting_items: list[str] | None = None,
    blockers: list[str] | None = None,
) -> None:
    waiting_line = waiting_items or ["无"]
    blocker_line = blockers or ["无"]
    lines = [
        f"# Task Card — {project_dir.name}",
        f"更新时间：{now_iso()}",
        "",
        "## 当前状态",
        f"- 项目：{project_dir.name}",
        f"- 当前阶段：{current_stage or 'none'}",
        f"- 已完成：{', '.join(completed_stages) if completed_stages else '无'}",
        "",
        "## 下一步（最重要）",
        f"**{next_step}**",
        "",
        "## 等待事项",
    ]
    lines.extend(f"- {item}" for item in waiting_line[:3])
    lines.append("")
    lines.append("## 已知阻塞")
    lines.extend(f"- {item}" for item in blocker_line[:3])
    (project_dir / "orchestration" / "task-card.md").write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8",
    )


def normalize_token(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def tokenize_hint(text: str) -> list[str]:
    tokens = [normalize_token(piece) for piece in re.split(r"[^A-Za-z0-9\u4e00-\u9fff]+", text)]
    deduped: list[str] = []
    for token in tokens:
        if len(token) < 2 or token in deduped:
            continue
        deduped.append(token)
    return deduped[:8]


def stable_id(prefix: str, raw: str) -> str:
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
    return f"{prefix}-{digest}"


def guess_title(path: pathlib.Path) -> str:
    parts = tokenize_hint(path.stem.replace("_", " ").replace("-", " "))
    if not parts:
        return path.stem
    return " ".join(parts[:6])
