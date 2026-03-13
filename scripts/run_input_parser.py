#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Parse a project request into structured input.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def parse_request(text: str) -> dict[str, object]:
    mapping = {
        "主题": "topic",
        "时长": "duration_seconds",
        "风格": "style",
        "语言": "language",
        "画幅": "aspect_ratio",
        "音乐": "music_emotion",
        "节奏": "pacing_preference",
    }
    result: dict[str, object] = {
        "topic": "",
        "goal": "生成一条音频优先的 AI 视频",
        "duration_seconds": 30,
        "language": "中文",
        "aspect_ratio": "9:16",
        "style": "",
        "music_emotion": "",
        "pacing_preference": "",
        "requires_voiceover": True,
        "requires_subtitles": True,
    }
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "：" not in line:
            continue
        key, value = [part.strip() for part in line.split("：", 1)]
        if key not in mapping:
            continue
        field = mapping[key]
        if field == "duration_seconds":
            digits = "".join(ch for ch in value if ch.isdigit())
            result[field] = int(digits or "30")
        else:
            result[field] = value
    if not result["style"]:
        result["style"] = "专业、克制"
    if not result["music_emotion"]:
        result["music_emotion"] = "平稳推进"
    if not result["pacing_preference"]:
        result["pacing_preference"] = "均匀"
    return result


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    request_path = project_dir / "request.md"
    output_path = project_dir / "input" / "input.json"
    payload = parse_request(request_path.read_text(encoding="utf-8"))
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
