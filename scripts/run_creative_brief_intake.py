#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Normalize a rough idea into a standard creative brief markdown file."
    )
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--seed-text",
        default=None,
        help="Optional one-line seed text. If omitted, reads project request.md.",
    )
    return parser.parse_args()


def default_brief() -> dict[str, Any]:
    return {
        "topic": "",
        "goal": "生成一条可用于短视频平台发布的叙事型视频",
        "duration_seconds": 30,
        "style": "纪实、克制、情绪递进",
        "language": "中文",
        "aspect_ratio": "9:16",
        "music_emotion": "前半段压抑，后半段燃向",
        "pacing_preference": "前慢后快",
        "audience": "18-35 岁关注社会议题与城市生活的人群",
        "platform": "抖音 / 视频号",
        "voiceover_requirements": "普通话，语速中等，情绪从克制到坚定",
        "subtitle_requirements": "逐句对齐旁白，关键词可强调",
        "content_structure": [
            "开场问题（提出矛盾）",
            "冲突与转折（信息抬升）",
            "高潮与收束（观点落地）",
            "结尾行动号召（明确下一步）",
        ],
        "visual_preferences": [
            "前半段：固定镜头、低饱和、慢推进",
            "后半段：运动镜头增多、对比提升、节奏加快",
            "禁止：夸张特效、卡通风、过度炫技转场",
        ],
        "constraints": [
            "必须保证旁白、字幕、转场与节拍对齐",
            "镜头时长必须服从音频时间网格",
            "输出需可回放、可复现、可继续二次编辑",
        ],
    }


def parse_seed(text: str) -> dict[str, Any]:
    data = default_brief()
    stripped = text.strip()
    if not stripped:
        data["topic"] = "未命名主题"
        return data
    if stripped.startswith("# Creative Brief"):
        # Already normalized, keep it as raw reference and avoid aggressive parsing.
        topic_match = re.search(r"主题：(.+)", stripped)
        data["topic"] = topic_match.group(1).strip() if topic_match else "未命名主题"
        return data

    mapping = {
        "主题": "topic",
        "目标": "goal",
        "时长": "duration_seconds",
        "风格": "style",
        "语言": "language",
        "画幅": "aspect_ratio",
        "音乐": "music_emotion",
        "节奏": "pacing_preference",
        "受众": "audience",
        "平台": "platform",
        "旁白要求": "voiceover_requirements",
        "字幕要求": "subtitle_requirements",
    }

    has_kv = False
    for raw_line in stripped.splitlines():
        line = raw_line.strip()
        if "：" not in line:
            continue
        key, value = [part.strip() for part in line.split("：", 1)]
        if key not in mapping:
            continue
        has_kv = True
        field = mapping[key]
        if field == "duration_seconds":
            digits = "".join(ch for ch in value if ch.isdigit())
            data[field] = int(digits or "30")
        else:
            data[field] = value

    if not has_kv:
        # One-line rough request.
        first_line = stripped.splitlines()[0]
        data["topic"] = first_line

    if not data["topic"]:
        data["topic"] = "未命名主题"
    return data


def render_brief(data: dict[str, Any]) -> str:
    content_structure = data.get("content_structure", [])
    visual_preferences = data.get("visual_preferences", [])
    constraints = data.get("constraints", [])
    if not isinstance(content_structure, list):
        content_structure = []
    if not isinstance(visual_preferences, list):
        visual_preferences = []
    if not isinstance(constraints, list):
        constraints = []

    return "\n".join(
        [
            "# Creative Brief",
            "",
            f"主题：{data.get('topic', '')}",
            f"目标：{data.get('goal', '')}",
            f"时长：{data.get('duration_seconds', 30)} 秒",
            f"风格：{data.get('style', '')}",
            f"语言：{data.get('language', '')}",
            f"画幅：{data.get('aspect_ratio', '')}",
            f"音乐：{data.get('music_emotion', '')}",
            f"节奏：{data.get('pacing_preference', '')}",
            "",
            f"受众：{data.get('audience', '')}",
            f"平台：{data.get('platform', '')}",
            f"旁白要求：{data.get('voiceover_requirements', '')}",
            f"字幕要求：{data.get('subtitle_requirements', '')}",
            "",
            "内容结构：",
            *[f"{index}. {item}" for index, item in enumerate(content_structure, start=1)],
            "",
            "视觉偏好：",
            *[f"- {item}" for item in visual_preferences],
            "",
            "约束：",
            *[f"- {item}" for item in constraints],
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    if not project_dir.exists():
        print(f"project not found: {project_dir}", file=sys.stderr)
        return 1

    request_path = project_dir / "request.md"
    raw_text = args.seed_text if args.seed_text is not None else request_path.read_text(encoding="utf-8")
    brief_data = parse_seed(raw_text)
    brief_markdown = render_brief(brief_data)

    brief_dir = project_dir / "brief"
    brief_dir.mkdir(parents=True, exist_ok=True)
    (brief_dir / "raw-request.txt").write_text(raw_text + ("\n" if not raw_text.endswith("\n") else ""), encoding="utf-8")
    (brief_dir / "intake.json").write_text(json.dumps(brief_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (brief_dir / "creative-brief.md").write_text(brief_markdown, encoding="utf-8")
    request_path.write_text(brief_markdown, encoding="utf-8")

    print(brief_dir / "creative-brief.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
