#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a deterministic render plan and run baseline checks.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--enable-ffmpeg-export",
        action="store_true",
        help="Enable optional real ffmpeg export to outputs/final.mp4.",
    )
    parser.add_argument(
        "--ffmpeg-binary",
        default="ffmpeg",
        help="ffmpeg binary path or command name.",
    )
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


def resolve_local_video_source(project_dir: pathlib.Path, tracks: list[dict[str, Any]]) -> pathlib.Path | None:
    for track in tracks:
        if not isinstance(track, dict) or track.get("track_id") != "video_main":
            continue
        items = track.get("items")
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", ""))
            if not source or source.startswith(("mock://", "poe://", "http://", "https://")):
                continue
            source_path = pathlib.Path(source)
            if not source_path.is_absolute():
                source_path = project_dir / source_path
            if source_path.exists():
                return source_path
    return None


def _format_ass_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds % 1) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def find_cjk_font() -> str:
    candidates = [
        "/System/Library/Fonts/STHeiti Medium.ttc",
        "/System/Library/Fonts/PingFang.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
    ]
    for path in candidates:
        if pathlib.Path(path).exists():
            return path
    return "STHeiti Medium"


def write_ass(project_dir: pathlib.Path) -> pathlib.Path | None:
    sub_path = project_dir / "subtitles" / "subtitles.json"
    if not sub_path.is_file():
        return None
    try:
        payload = json.loads(sub_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    entries = payload.get("entries") if isinstance(payload, dict) else None
    if not isinstance(entries, list) or not entries:
        return None

    font_path = find_cjk_font()
    font_name = pathlib.Path(font_path).stem if pathlib.Path(font_path).exists() else font_path

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 720\n"
        "PlayResY: 1280\n"
        "WrapStyle: 1\n\n"
        "[V4+ Styles]\n"
        "Format: Name,Fontname,Fontsize,PrimaryColour,SecondaryColour,OutlineColour,BackColour,"
        "Bold,Italic,Underline,StrikeOut,ScaleX,ScaleY,Spacing,Angle,BorderStyle,Outline,Shadow,"
        "Alignment,MarginL,MarginR,MarginV,Encoding\n"
        f"Style: Default,{font_name},32,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,"
        "0,0,0,0,100,100,0,0,1,2,1,2,10,10,150,1\n\n"
        "[Events]\n"
        "Format: Layer,Start,End,Style,Name,MarginL,MarginR,MarginV,Effect,Text\n"
    )
    dialogue_lines: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        start = _format_ass_time(float(entry.get("start", 0)))
        end = _format_ass_time(float(entry.get("end", 0)))
        text = str(entry.get("text", "")).strip().replace("\n", "\\N")
        if text:
            dialogue_lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    if not dialogue_lines:
        return None

    ass_path = project_dir / "subtitles" / "subtitles.ass"
    ass_path.write_text(header + "\n".join(dialogue_lines) + "\n", encoding="utf-8")
    return ass_path


def resolve_video_clips(project_dir: pathlib.Path, tracks: list[dict[str, Any]]) -> list[pathlib.Path]:
    """Return ordered list of local video clip paths from video_main track."""
    for track in tracks:
        if not isinstance(track, dict) or track.get("track_id") != "video_main":
            continue
        items = track.get("items")
        if not isinstance(items, list):
            continue
        sorted_items = sorted(items, key=lambda x: float(x.get("start", 0)) if isinstance(x, dict) else 0)
        clips: list[pathlib.Path] = []
        for item in sorted_items:
            if not isinstance(item, dict):
                continue
            source = str(item.get("source", ""))
            if not source or source.startswith(("mock://", "poe://", "http://", "https://")):
                continue
            p = pathlib.Path(source) if pathlib.Path(source).is_absolute() else project_dir / source
            if p.exists():
                clips.append(p)
        return clips
    return []


FFMPEG_FULL = "/opt/homebrew/opt/ffmpeg-full/bin/ffmpeg"


def find_voiceover(project_dir: pathlib.Path) -> pathlib.Path | None:
    for candidate in ["audio/voiceover-main.mp3", "audio/voiceover.mp3", "audio/voiceover-source.mp3"]:
        p = project_dir / candidate
        if p.exists():
            return p
    return None


def run_ffmpeg_export(
    *,
    project_dir: pathlib.Path,
    ffmpeg_binary: str,
    duration_seconds: float,
    tracks: list[dict[str, Any]],
) -> tuple[bool, dict[str, Any], list[str]]:
    output_path = project_dir / "outputs" / "final.mp4"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    safe_duration = max(round(duration_seconds, 2), 1.0)

    clips = resolve_video_clips(project_dir, tracks)
    voiceover = find_voiceover(project_dir)
    ass_path = write_ass(project_dir)

    if not clips:
        # Fallback: silent black video
        command = [
            ffmpeg_binary, "-y",
            "-f", "lavfi", "-i", f"color=c=black:s=720x1280:r=30",
            "-f", "lavfi", "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
            "-t", str(safe_duration), "-shortest",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
            str(output_path),
        ]
        mode = "synthetic"
    else:
        # Build concat filter for all clips, normalize to 720x1280 30fps
        n = len(clips)
        command = [ffmpeg_binary, "-y"]
        for clip in clips:
            command += ["-i", str(clip)]
        if voiceover:
            command += ["-i", str(voiceover)]

        # Scale each clip to 720x1280 with letterbox, then concat
        filter_parts = []
        for i in range(n):
            filter_parts.append(
                f"[{i}:v]scale=720:1280:force_original_aspect_ratio=decrease,"
                f"pad=720:1280:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[v{i}]"
            )
        concat_inputs = "".join(f"[v{i}]" for i in range(n))
        # concat only; subtitles are burned in a separate pass to avoid filter_complex escaping issues
        filter_parts.append(f"{concat_inputs}concat=n={n}:v=1:a=0[outv]")

        if voiceover:
            # pan mono to stereo so all players output both channels
            filter_parts.append(f"[{n}:a]pan=stereo|c0=c0|c1=c0[outa]")
            command += ["-filter_complex", ";".join(filter_parts), "-map", "[outv]", "-map", "[outa]", "-c:a", "aac", "-shortest"]
        else:
            command += ["-filter_complex", ";".join(filter_parts), "-map", "[outv]", "-an"]
        command += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", str(safe_duration), str(output_path)]
        mode = f"concat_{n}_clips" + ("_with_voiceover_stereo" if voiceover else "")

    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        return (
            False,
            {
                "status": "failed",
                "mode": mode,
                "returncode": result.returncode,
                "stderr": result.stderr[-2000:],
                "output_path": str(output_path.relative_to(project_dir)),
            },
            command,
        )

    # Pass 2: burn subtitles with a separate command (avoids filter_complex escaping issues)
    sub_burned = False
    if ass_path and output_path.exists():
        sub_output = output_path.with_stem(output_path.stem + "_sub")
        # Use ffmpeg-full which has libass support
        sub_ffmpeg = FFMPEG_FULL if pathlib.Path(FFMPEG_FULL).exists() else ffmpeg_binary
        sub_command = [
            sub_ffmpeg, "-y",
            "-i", str(output_path),
            "-vf", f"ass={ass_path}",
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-c:a", "copy",
            str(sub_output),
        ]
        sub_result = subprocess.run(sub_command, capture_output=True, text=True)
        if sub_result.returncode == 0 and sub_output.exists():
            sub_output.replace(output_path)  # overwrite original with subtitled version
            sub_burned = True
        else:
            print(f"[subtitle] burn failed, keeping video without subtitles: {sub_result.stderr[-500:]}", flush=True)

    return (
        True,
        {
            "status": "success",
            "mode": mode + ("_subtitled" if sub_burned else ""),
            "clips_count": len(clips),
            "voiceover": str(voiceover.relative_to(project_dir)) if voiceover else None,
            "subtitles": str(ass_path.relative_to(project_dir)) if sub_burned and ass_path else None,
            "output_path": str(output_path.relative_to(project_dir)),
            "file_size_bytes": output_path.stat().st_size if output_path.exists() else 0,
        },
        command,
    )


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

    ffmpeg_enabled = bool(args.enable_ffmpeg_export)
    ffmpeg_execution: dict[str, Any] = {
        "status": "skipped",
        "reason": "ffmpeg export disabled",
    }
    ffmpeg_command_preview: list[str] = []
    ffmpeg_binary_path = shutil.which(args.ffmpeg_binary) if ffmpeg_enabled else None
    if ffmpeg_enabled:
        if ffmpeg_binary_path is None:
            failures.append(f"ffmpeg binary not found: {args.ffmpeg_binary}")
            ffmpeg_execution = {
                "status": "failed",
                "reason": f"ffmpeg binary not found: {args.ffmpeg_binary}",
            }
        else:
            export_ok, export_execution, command = run_ffmpeg_export(
                project_dir=project_dir,
                ffmpeg_binary=ffmpeg_binary_path,
                duration_seconds=total_duration,
                tracks=[track for track in tracks if isinstance(track, dict)],
            )
            ffmpeg_execution = export_execution
            ffmpeg_command_preview = command
            if not export_ok:
                failures.append(
                    f"ffmpeg export failed: {export_execution.get('stderr', 'unknown error')}"
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
            "enabled": ffmpeg_enabled,
            "binary": ffmpeg_binary_path or args.ffmpeg_binary,
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
            "notes": "Optional real export. Falls back to synthetic source when local video media is unavailable.",
            "execution": ffmpeg_execution,
            "command_preview": ffmpeg_command_preview,
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
