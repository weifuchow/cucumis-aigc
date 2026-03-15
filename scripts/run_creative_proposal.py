#!/usr/bin/env python3
"""Generate placeholder creative proposals from brief/intake.json.

In Claude-driven mode this script is not called — Claude generates the proposals
interactively and writes the selected concept after user confirmation.

This script is a fallback for automated/batch pipelines: it generates template
proposals and auto-selects the first one.
"""

from __future__ import annotations

import argparse
import json
import pathlib
from datetime import datetime, timezone


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate creative proposals from brief (auto-select mode)."
    )
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--select",
        default="A",
        choices=["A", "B", "C"],
        help="Which proposal to auto-select (default: A).",
    )
    return parser.parse_args()


def build_proposals(intake: dict) -> list[dict]:
    topic = intake.get("topic", "未命名主题")
    music = intake.get("music_emotion", "平稳推进")
    style = intake.get("style", "专业、克制")
    duration = intake.get("duration_seconds", 30)

    return [
        {
            "concept_id": "A",
            "title": f"{topic}·问题切入",
            "angle": f"以反常识问题开场，引导观众重新审视 {topic}",
            "emotional_arc": "疑问 → 数据冲击 → 洞察落地",
            "opening_line": f"关于 {topic}，你以为你了解——但数据说的是另一回事。",
            "visual_direction": f"{style}、信息图、数字特写",
            "music_direction": f"{music}，前半压抑后半递进",
            "why_this_works": f"适合 {duration}s 以内的快节奏信息传递，钩子明确。",
        },
        {
            "concept_id": "B",
            "title": f"{topic}·场景代入",
            "angle": f"从真实人物或场景切入，用故事承载 {topic} 的核心信息",
            "emotional_arc": "沉浸 → 共鸣 → 转折升华",
            "opening_line": f"有人在 {topic} 上失败了三次，第四次他做对了一件事。",
            "visual_direction": "人物特写、暖色调、手持跟拍",
            "music_direction": "情感铺垫，中段转折，结尾释放",
            "why_this_works": "情感共鸣强，适合强调人的决策和转变的叙事。",
        },
        {
            "concept_id": "C",
            "title": f"{topic}·直接揭示",
            "angle": f"开门见山给出核心结论，用后续内容逐层论证 {topic}",
            "emotional_arc": "直白 → 论证 → 行动号召",
            "opening_line": f"{topic}，真正的关键只有一个。",
            "visual_direction": "信息流、俯视全景、平稳运镜",
            "music_direction": "节奏稳定，克制，结尾强收",
            "why_this_works": "结构清晰，适合强调方法论或可操作建议的内容。",
        },
    ]


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    intake_path = project_dir / "brief" / "intake.json"
    intake = json.loads(intake_path.read_text(encoding="utf-8"))

    proposals = build_proposals(intake)
    brief_dir = project_dir / "brief"

    (brief_dir / "proposals.json").write_text(
        json.dumps({"proposals": proposals}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    selected = next(p for p in proposals if p["concept_id"] == args.select)
    selected_payload = {
        "selected_at": datetime.now(timezone.utc).isoformat(),
        "auto_selected": True,
        **selected,
        "user_notes": "",
    }
    (brief_dir / "selected-concept.json").write_text(
        json.dumps(selected_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(brief_dir / "selected-concept.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
