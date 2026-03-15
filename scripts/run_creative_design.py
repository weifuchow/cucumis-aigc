#!/usr/bin/env python3
"""Creative design stage: brief intake + concept proposals + cost tier → input.json.

In Claude-driven mode Claude runs this interactively (multi-turn clarification →
3 proposals → user picks concept + cost tier → writes input.json).

This script is the automated fallback for batch/CI pipelines.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import re
from datetime import datetime, timezone
from typing import Any


COST_TIERS: dict[str, dict[str, Any]] = {
    "economy": {
        "label": "省钱模式（全图片）",
        "max_video_calls": 0,
        "image_model": "grok-imagine-image",
        "video_model": "pixverse-v5.6",
        "description": "所有场景用图片合成，不调视频模型，成本最低",
    },
    "standard": {
        "label": "标准模式（最多2次视频）",
        "max_video_calls": 2,
        "image_model": "grok-imagine-image",
        "video_model": "pixverse-v5.6",
        "description": "最多2个场景调视频模型，其余用图片合成",
    },
    "unlimited": {
        "label": "不限制",
        "max_video_calls": 999,
        "image_model": "grok-imagine-image",
        "video_model": "pixverse-v5.6",
        "description": "所有需要动态效果的场景均调视频模型",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Creative design: intake + proposals + cost tier → input.json")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--seed-text", default=None, help="Optional one-line seed text.")
    parser.add_argument("--tier", default="standard", choices=list(COST_TIERS), help="Cost tier.")
    parser.add_argument("--concept", default="A", choices=["A", "B", "C"], help="Auto-select concept.")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Brief parsing (from request.md or seed text)
# ---------------------------------------------------------------------------

def _default_brief() -> dict[str, Any]:
    return {
        "topic": "",
        "goal": "生成一条可用于短视频平台发布的叙事型视频",
        "duration_seconds": 30,
        "style": "专业、克制、情绪递进",
        "language": "中文",
        "aspect_ratio": "9:16",
        "music_emotion": "前半段压抑，后半段燃向",
        "pacing_preference": "前慢后快",
        "audience": "18-35 岁用户",
        "platform": "抖音 / 视频号",
        "voiceover_requirements": "普通话，语速中等，情绪从克制到坚定",
        "subtitle_requirements": "逐句对齐旁白",
        "content_structure": ["开场问题", "冲突与转折", "高潮收束", "行动号召"],
        "visual_preferences": ["前段固定镜头低饱和", "后段运动镜头节奏加快"],
        "constraints": ["旁白字幕转场与节拍对齐", "镜头服从音频时间网格"],
    }


def _parse_brief(text: str) -> dict[str, Any]:
    data = _default_brief()
    stripped = text.strip()
    if not stripped:
        data["topic"] = "未命名主题"
        return data

    mapping = {
        "主题": "topic", "目标": "goal", "时长": "duration_seconds",
        "风格": "style", "语言": "language", "画幅": "aspect_ratio",
        "音乐": "music_emotion", "节奏": "pacing_preference",
        "受众": "audience", "平台": "platform",
    }
    has_kv = False
    for line in stripped.splitlines():
        line = line.strip()
        if "：" not in line:
            continue
        key, value = [p.strip() for p in line.split("：", 1)]
        if key not in mapping:
            continue
        has_kv = True
        field = mapping[key]
        if field == "duration_seconds":
            digits = "".join(c for c in value if c.isdigit())
            data[field] = int(digits or "30")
        else:
            data[field] = value

    if not has_kv:
        data["topic"] = stripped.splitlines()[0]
    if not data["topic"]:
        data["topic"] = "未命名主题"
    return data


# ---------------------------------------------------------------------------
# Concept proposals
# ---------------------------------------------------------------------------

def _build_proposals(intake: dict[str, Any]) -> list[dict[str, Any]]:
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


# ---------------------------------------------------------------------------
# input.json assembly
# ---------------------------------------------------------------------------

def _build_input(intake: dict[str, Any], concept: dict[str, Any], tier: str) -> dict[str, Any]:
    tier_cfg = COST_TIERS[tier]
    result: dict[str, Any] = {
        # Content fields from intake
        "topic": intake.get("topic", ""),
        "goal": intake.get("goal", ""),
        "duration_seconds": intake.get("duration_seconds", 30),
        "language": intake.get("language", "中文"),
        "aspect_ratio": intake.get("aspect_ratio", "9:16"),
        "style": intake.get("style", "专业、克制"),
        "music_emotion": intake.get("music_emotion", "平稳推进"),
        "pacing_preference": intake.get("pacing_preference", "均匀"),
        "audience": intake.get("audience", ""),
        "platform": intake.get("platform", ""),
        "voiceover_requirements": intake.get("voiceover_requirements", ""),
        "subtitle_requirements": intake.get("subtitle_requirements", ""),
        "content_structure": intake.get("content_structure", []),
        "visual_preferences": intake.get("visual_preferences", []),
        "constraints": intake.get("constraints", []),
        # Selected concept overlay
        "creative_angle": concept.get("angle", ""),
        "emotional_arc": concept.get("emotional_arc", ""),
        "opening_line": concept.get("opening_line", ""),
        "visual_direction": concept.get("visual_direction", ""),
        "selected_concept_id": concept.get("concept_id", ""),
        "selected_concept_title": concept.get("title", ""),
        # Cost tier + model config
        "cost_tier": tier,
        "cost_tier_label": tier_cfg["label"],
        "max_video_calls": tier_cfg["max_video_calls"],
        "image_model": tier_cfg["image_model"],
        "video_model": tier_cfg["video_model"],
        "audio_model": "elevenlabs-v3",
        "requires_voiceover": True,
        "requires_subtitles": True,
    }
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    brief_dir = project_dir / "brief"
    brief_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Parse brief
    request_path = project_dir / "request.md"
    raw_text = args.seed_text if args.seed_text is not None else request_path.read_text(encoding="utf-8")
    intake = _parse_brief(raw_text)

    (brief_dir / "intake.json").write_text(
        json.dumps(intake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    # Step 2: Proposals (skip if selected-concept.json already written by Claude)
    concept_path = brief_dir / "selected-concept.json"
    if not concept_path.exists():
        proposals = _build_proposals(intake)
        (brief_dir / "proposals.json").write_text(
            json.dumps({"proposals": proposals}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        selected = next(p for p in proposals if p["concept_id"] == args.concept)
        concept_payload = {
            "selected_at": datetime.now(timezone.utc).isoformat(),
            "auto_selected": True,
            "cost_tier": args.tier,
            **selected,
            "user_notes": "",
        }
        concept_path.write_text(
            json.dumps(concept_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    else:
        concept_payload = json.loads(concept_path.read_text(encoding="utf-8"))
        # Tier may have been set interactively; respect it if present
        if "cost_tier" in concept_payload:
            args.tier = concept_payload["cost_tier"]

    # Step 3: Write input.json
    payload = _build_input(intake, concept_payload, args.tier)
    input_path = project_dir / "input" / "input.json"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(input_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
