#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an emotion-tagged script from input.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    input_payload = json.loads((project_dir / "input" / "input.json").read_text(encoding="utf-8"))
    topic = input_payload["topic"] or "未命名主题"
    music_emotion = str(input_payload["music_emotion"])
    pacing = str(input_payload["pacing_preference"])

    audio_track = [
        f"我们先从 {topic} 的核心矛盾切入。",
        f"前半段情绪保持 {music_emotion.split('，')[0] if '，' in music_emotion else music_emotion}。",
        "随后进入明显的情绪转折和信息抬升。",
        "最后在高能节点完成观点收束。"
    ]
    visual_track = [
        "开场以克制的环境和静态信息呈现问题。",
        "中段逐步抬高画面密度与镜头运动。",
        "转折点使用强烈视觉切换。",
        "结尾以明确行动号召收束。"
    ]
    payload = {
        "title": topic,
        "summary": f"围绕 {topic} 的音频优先脚本，节奏偏好为 {pacing}。",
        "audio_track": audio_track,
        "visual_track": visual_track,
        "beats": [
            {"beat_id": "beat-1", "purpose": "setup"},
            {"beat_id": "beat-2", "purpose": "transition"},
            {"beat_id": "beat-3", "purpose": "payoff"},
        ],
        "emotion_markers": [
            {"marker_id": "emotion-1", "label": "压抑铺垫", "line_index": 1},
            {"marker_id": "emotion-2", "label": "情绪爆发", "line_index": 2}
        ],
        "turning_points": [
            {"point_id": "turn-1", "label": "情绪转折点", "line_index": 2},
            {"point_id": "turn-2", "label": "高潮爆发", "line_index": 3}
        ]
    }
    output_path = project_dir / "script" / "script.json"
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
