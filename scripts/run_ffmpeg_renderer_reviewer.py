#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a deterministic render plan and run baseline checks.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def load_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing required file: {label} ({path})")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid json in {label} ({path}): {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def check_local_media_source(project_dir: pathlib.Path, source: str) -> bool:
    prefixes = ("mock://", "poe://", "http://", "https://")
    if source.startswith(prefixes):
        return True
    source_path = pathlib.Path(source)
    if source_path.is_absolute():
        return source_path.exists()
    return (project_dir / source_path).exists()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    try:
        timeline = load_json(project_dir / "timeline" / "timeline.json", "timeline")
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    def record_check(check_id: str, passed: bool, detail: str) -> None:
        checks.append({"check_id": check_id, "status": "pass" if passed else "fail", "detail": detail})
        if not passed:
            failures.append(detail)

    required_files = [
        "timeline/timeline.json",
        "video/clips.json",
        "audio/voiceover.json",
        "audio/bgm-selection.json",
    ]
    missing_files = [path for path in required_files if not (project_dir / path).is_file()]
    record_check(
        "required_files",
        not missing_files,
        "all required files present" if not missing_files else f"missing required files: {', '.join(missing_files)}",
    )

    tracks = timeline.get("tracks")
    if not isinstance(tracks, list):
        record_check("tracks_structure", False, "timeline.tracks must be an array")
        tracks = []
    else:
        record_check("tracks_structure", True, "timeline.tracks is present")

    track_ids = {str(track.get("track_id")) for track in tracks if isinstance(track, dict)}
    required_track_ids = {"video_main", "audio_voiceover"}
    missing_track_ids = sorted(required_track_ids - track_ids)
    record_check(
        "required_tracks",
        not missing_track_ids,
        "required tracks present"
        if not missing_track_ids
        else f"missing required tracks: {', '.join(missing_track_ids)}",
    )

    segments = timeline.get("segments")
    valid_segments: list[dict[str, Any]] = []
    if not isinstance(segments, list) or not segments:
        record_check("segments", False, "timeline.segments must be a non-empty array")
    else:
        invalid_ranges = []
        for segment in segments:
            if not isinstance(segment, dict):
                invalid_ranges.append("segment must be an object")
                continue
            start = segment.get("start")
            end = segment.get("end")
            if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
                invalid_ranges.append(f"invalid segment range for {segment.get('segment_id', 'unknown')}")
                continue
            valid_segments.append(segment)
        record_check(
            "segment_ranges",
            not invalid_ranges and bool(valid_segments),
            "segment ranges are valid"
            if (not invalid_ranges and valid_segments)
            else "; ".join(invalid_ranges) or "no usable segments",
        )

    total_duration = 0.0
    if valid_segments:
        total_duration = round(max(float(segment["end"]) for segment in valid_segments), 2)
    record_check(
        "timeline_duration",
        total_duration > 0,
        f"timeline duration={total_duration:.2f}s" if total_duration > 0 else "timeline duration must be > 0",
    )

    video_track = next(
        (track for track in tracks if isinstance(track, dict) and track.get("track_id") == "video_main"),
        None,
    )
    missing_media_sources: list[str] = []
    if isinstance(video_track, dict):
        items = video_track.get("items")
        if isinstance(items, list):
            for item in items:
                if not isinstance(item, dict):
                    continue
                source = str(item.get("source", ""))
                if not source or not check_local_media_source(project_dir, source):
                    missing_media_sources.append(source or "<empty>")
    record_check(
        "video_sources",
        not missing_media_sources,
        "video sources are resolvable"
        if not missing_media_sources
        else f"unresolvable video sources: {', '.join(missing_media_sources)}",
    )

    sorted_segments = sorted(
        valid_segments,
        key=lambda segment: (
            float(segment["start"]),
            str(segment.get("scene_id", "")),
            str(segment.get("segment_id", "")),
        ),
    )

    render_plan = {
        "version": "v1",
        "timeline_source": "timeline/timeline.json",
        "duration_seconds": total_duration,
        "inputs": [{"path": path, "required": True} for path in required_files],
        "checks": checks,
        "stages": [
            {
                "stage_id": "prepare_inputs",
                "description": "Resolve timeline and declared media references.",
            },
            {
                "stage_id": "mix_audio",
                "description": "Mix voiceover and bgm tracks into a single master bus.",
            },
            {
                "stage_id": "render_video",
                "description": "Compose scene clips and apply timeline transitions.",
            },
            {
                "stage_id": "quality_review",
                "description": "Verify final duration and mandatory tracks.",
            },
        ],
        "shot_plan": [
            {
                "segment_id": str(segment.get("segment_id", "")),
                "scene_id": str(segment.get("scene_id", "")),
                "start": round(float(segment["start"]), 2),
                "end": round(float(segment["end"]), 2),
                "video_clip_url": str(segment.get("video_clip_url", "")),
            }
            for segment in sorted_segments
        ],
        "ffmpeg": {
            "enabled": False,
            "binary": "ffmpeg",
            "args_template": [
                "-y",
                "-i",
                "{video_input}",
                "-i",
                "{voiceover_input}",
                "-i",
                "{bgm_input}",
                "-filter_complex",
                "{filter_graph}",
                "-map",
                "0:v:0",
                "-map",
                "[mixed_audio]",
                "-c:v",
                "libx264",
                "-c:a",
                "aac",
                "{output_path}",
            ],
            "notes": "Placeholder only; real ffmpeg execution will be added in a later phase.",
        },
        "output": {
            "path": "outputs/final.mp4",
            "container": "mp4",
        },
    }

    output_path = project_dir / "outputs" / "render-plan.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(render_plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    if failures:
        print("; ".join(failures), file=sys.stderr)
        return 1

    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
