#!/usr/bin/env python3
"""Render a material-editorial rough cut from local assets.

This renderer is intentionally project-artifact driven: image segments can read
analysis/image-motion-plan.json so material understanding decisions affect the
actual Ken Burns parameters instead of staying as notes.
"""

from __future__ import annotations

import argparse
import json
import math
import pathlib
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

from run_constrained_video_generator import load_image_motion_plan, render_zoom_pan_clip, resolve_image_motion


FPS = 30
WIDTH = 720
HEIGHT = 1280


def read_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: pathlib.Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def rel(project_dir: pathlib.Path, path: pathlib.Path) -> str:
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def resolve_project_path(project_dir: pathlib.Path, value: str) -> pathlib.Path:
    path = pathlib.Path(value)
    return path if path.is_absolute() else project_dir / path


def run(command: list[str], label: str) -> None:
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        detail = stderr[-2500:] if stderr else stdout[-2500:]
        raise RuntimeError(f"{label} failed\n{detail}")


def ffprobe_duration(path: pathlib.Path) -> float | None:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=nw=1:nk=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def shell_quote_for_concat(path: pathlib.Path) -> str:
    escaped = str(path).replace("'", "'\\''")
    return f"file '{escaped}'"


def render_image_segment(
    *,
    ffmpeg: str,
    project_dir: pathlib.Path,
    segment: dict[str, Any],
    output_path: pathlib.Path,
    plan_by_segment: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    direction = str(segment.get("local_render_technique") or segment.get("motion_intent") or "zoom_in")
    motion_intent = str(segment.get("motion_intent", ""))
    ok, result = render_zoom_pan_clip(
        ffmpeg_binary=ffmpeg,
        project_dir=project_dir,
        scene_id=str(segment["segment_id"]),
        image_path=str(segment["source"]),
        duration_seconds=float(segment["duration_seconds"]),
        direction=direction,
        motion_intent=motion_intent,
        image_motion_plan=plan_by_segment,
        output_path=output_path,
    )
    if not ok:
        raise RuntimeError(result)
    motion, motion_source = resolve_image_motion(
        scene_id=str(segment["segment_id"]),
        motion_intent=motion_intent,
        direction=direction,
        image_motion_plan=plan_by_segment,
    )
    duration = float(segment["duration_seconds"])
    return {
        "segment_id": segment["segment_id"],
        "source": segment["source"],
        "source_media_type": "image",
        "output": rel(project_dir, output_path),
        "duration_seconds": duration,
        "frames": max(1, int(round(duration * FPS))),
        "motion_source": motion_source,
        "motion": motion,
    }


def render_video_segment(
    *,
    ffmpeg: str,
    project_dir: pathlib.Path,
    segment: dict[str, Any],
    output_path: pathlib.Path,
) -> dict[str, Any]:
    source = resolve_project_path(project_dir, segment["source"])
    if not source.is_file():
        raise FileNotFoundError(source)
    duration = float(segment["duration_seconds"])
    run(
        [
            ffmpeg,
            "-y",
            "-stream_loop",
            "-1",
            "-i",
            str(source),
            "-t",
            f"{duration:.3f}",
            "-vf",
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,crop={WIDTH}:{HEIGHT},fps={FPS},format=yuv420p,setpts=PTS-STARTPTS",
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        f"render video segment {segment['segment_id']}",
    )
    return {
        "segment_id": segment["segment_id"],
        "source": segment["source"],
        "source_media_type": "video",
        "output": rel(project_dir, output_path),
        "duration_seconds": duration,
        "motion_source": "source_video_motion",
        "motion": {"type": segment.get("motion_intent", "hold_motion")},
    }


def track_by_id(timeline: dict[str, Any], track_id: str) -> dict[str, Any] | None:
    for track in timeline.get("tracks", []):
        if track.get("track_id") == track_id:
            return track
    return None


def render_video_only(
    *,
    ffmpeg: str,
    project_dir: pathlib.Path,
    timeline: dict[str, Any],
    plan_by_segment: dict[str, dict[str, Any]],
    work_dir: pathlib.Path,
) -> tuple[pathlib.Path, list[dict[str, Any]]]:
    video_track = track_by_id(timeline, "video_main")
    if not video_track:
        raise RuntimeError("timeline missing video_main track")
    items = video_track.get("items", [])
    rendered_segments: list[dict[str, Any]] = []
    concat_path = work_dir / "concat.txt"
    concat_lines: list[str] = []

    for index, item in enumerate(items, start=1):
        output_path = work_dir / f"segment-{index:03d}.mp4"
        if item.get("source_media_type") == "image":
            rendered = render_image_segment(
                ffmpeg=ffmpeg,
                project_dir=project_dir,
                segment=item,
                output_path=output_path,
                plan_by_segment=plan_by_segment,
            )
        else:
            rendered = render_video_segment(
                ffmpeg=ffmpeg,
                project_dir=project_dir,
                segment=item,
                output_path=output_path,
            )
        rendered["item_id"] = item.get("item_id")
        rendered["start"] = item.get("start")
        rendered["end"] = item.get("end")
        rendered_segments.append(rendered)
        concat_lines.append(shell_quote_for_concat(output_path))

    concat_path.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    video_only = work_dir / "video-only.mp4"
    run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(video_only),
        ],
        "concat video segments",
    )
    return video_only, rendered_segments


def db_to_volume(db: float) -> float:
    return math.pow(10.0, db / 20.0)


def render_audio_mix(
    *,
    ffmpeg: str,
    project_dir: pathlib.Path,
    timeline: dict[str, Any],
    output_path: pathlib.Path,
    duration: float,
) -> dict[str, Any]:
    inputs: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    input_count = 0

    voiceover_path = project_dir / "audio" / "voiceover-main.mp3"
    if voiceover_path.is_file():
        inputs += ["-i", str(voiceover_path)]
        filters.append(f"[{input_count}:a]loudnorm=I=-17:TP=-1.5:LRA=9,volume=1.0[vo]")
        labels.append("[vo]")
        input_count += 1

    bgm_track = track_by_id(timeline, "audio_bgm")
    if bgm_track and bgm_track.get("source"):
        bgm_path = resolve_project_path(project_dir, bgm_track["source"])
        if bgm_path.is_file():
            input_index = input_count
            inputs += ["-stream_loop", "-1", "-i", str(bgm_path)]
            input_count += 1
            envelope = bgm_track.get("items", [{}])[0].get("volume_envelope", [])
            if envelope:
                points = sorted((float(p["time"]), float(p["db"])) for p in envelope)
                pieces: list[str] = []
                for current, nxt in zip(points, points[1:]):
                    t0, db0 = current
                    t1, db1 = nxt
                    v0 = db_to_volume(db0)
                    v1 = db_to_volume(db1)
                    slope = (v1 - v0) / max(0.001, t1 - t0)
                    pieces.append(f"between(t,{t0},{t1})*({v0}+({slope})*(t-{t0}))")
                first_v = db_to_volume(points[0][1])
                last_v = db_to_volume(points[-1][1])
                volume_expr = f"if(lt(t,{points[0][0]}),{first_v},if(gt(t,{points[-1][0]}),{last_v},{'+'.join(pieces)}))"
                volume_filter = f"volume='{volume_expr}':eval=frame"
            else:
                volume_filter = "volume=0.45"
            filters.append(
                f"[{input_index}:a]atrim=0:{duration},asetpts=PTS-STARTPTS,"
                f"loudnorm=I=-23:TP=-2:LRA=11,{volume_filter}[bgm]"
            )
            labels.append("[bgm]")

    ambience_track = track_by_id(timeline, "audio_ambience")
    ambience_used: list[dict[str, Any]] = []
    if ambience_track:
        for amb_index, item in enumerate(ambience_track.get("items", []), start=1):
            amb_path = resolve_project_path(project_dir, item["source"])
            if not amb_path.is_file():
                continue
            input_index = input_count
            inputs += ["-stream_loop", "-1", "-i", str(amb_path)]
            input_count += 1
            start = float(item.get("start", 0))
            end = float(item.get("end", duration))
            seg_duration = max(0.1, end - start)
            volume = db_to_volume(float(item.get("volume_db", -25)))
            fade_in = float(item.get("fade_in", 0))
            fade_out = float(item.get("fade_out", 0))
            label = f"amb{amb_index}"
            chain = (
                f"[{input_index}:a]atrim=0:{seg_duration},asetpts=PTS-STARTPTS,"
                f"loudnorm=I=-25:TP=-2:LRA=10,volume={volume},"
                f"afade=t=in:st=0:d={fade_in},"
                f"afade=t=out:st={max(0, seg_duration - fade_out)}:d={fade_out},"
                f"adelay={int(start * 1000)}:all=1[{label}]"
            )
            filters.append(chain)
            labels.append(f"[{label}]")
            ambience_used.append(item)

    if not labels:
        raise RuntimeError("no audio sources found to mix")

    if len(labels) == 1:
        mix_filter = "".join(labels) + f"atrim=0:{duration},asetpts=PTS-STARTPTS,alimiter=limit=0.95[aout]"
    else:
        mix_filter = "".join(labels) + f"amix=inputs={len(labels)}:duration=longest:normalize=0,atrim=0:{duration},asetpts=PTS-STARTPTS,alimiter=limit=0.95[aout]"
    filters.append(mix_filter)

    run(
        [
            ffmpeg,
            "-y",
            *inputs,
            "-filter_complex",
            ";".join(filters),
            "-map",
            "[aout]",
            "-t",
            f"{duration:.3f}",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            str(output_path),
        ],
        "render audio mix",
    )
    return {
        "output": rel(project_dir, output_path),
        "voiceover": rel(project_dir, voiceover_path) if voiceover_path.is_file() else None,
        "bgm": bgm_track.get("source") if bgm_track else None,
        "ambience_count": len(ambience_used),
        "mix_mode": "voiceover_bgm_ambience_normalize_0",
    }


def mux_final(
    *,
    ffmpeg: str,
    video_path: pathlib.Path,
    audio_path: pathlib.Path,
    output_path: pathlib.Path,
    duration: float,
) -> None:
    run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-t",
            f"{duration:.3f}",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        "mux final rough cut",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render material rough cut with image motion plan support.")
    parser.add_argument("--project", required=True, help="Project directory, e.g. projects/0425-new")
    parser.add_argument("--timeline", help="Timeline JSON path; defaults to timeline/material-timeline-draft.json")
    parser.add_argument("--image-motion-plan", help="Image motion plan JSON; defaults to analysis/image-motion-plan.json")
    parser.add_argument("--output", help="Output MP4; defaults to outputs/rough-cut.mp4")
    parser.add_argument("--work-dir", help="Work dir; defaults to outputs/rough-cut-work-v3")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()

    project_dir = pathlib.Path(args.project).resolve()
    timeline_path = pathlib.Path(args.timeline).resolve() if args.timeline else project_dir / "timeline" / "material-timeline-draft.json"
    motion_plan_path = pathlib.Path(args.image_motion_plan).resolve() if args.image_motion_plan else None
    output_path = pathlib.Path(args.output).resolve() if args.output else project_dir / "outputs" / "rough-cut.mp4"
    work_dir = pathlib.Path(args.work_dir).resolve() if args.work_dir else project_dir / "outputs" / "rough-cut-work-v3"

    if not project_dir.is_dir():
        raise FileNotFoundError(project_dir)
    if not timeline_path.is_file():
        raise FileNotFoundError(timeline_path)

    timeline = read_json(timeline_path)
    duration = float(timeline.get("metadata", {}).get("duration_seconds", 60))
    plan_by_segment = load_image_motion_plan(project_dir, motion_plan_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.is_file():
        backup = output_path.with_name("rough-cut-before-motion-plan.mp4")
        if not backup.exists():
            shutil.copy2(output_path, backup)

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True, exist_ok=True)

    video_only, rendered_segments = render_video_only(
        ffmpeg=args.ffmpeg,
        project_dir=project_dir,
        timeline=timeline,
        plan_by_segment=plan_by_segment,
        work_dir=work_dir,
    )
    audio_mix = work_dir / "audio-mix.m4a"
    audio_manifest = render_audio_mix(
        ffmpeg=args.ffmpeg,
        project_dir=project_dir,
        timeline=timeline,
        output_path=audio_mix,
        duration=duration,
    )
    mux_final(
        ffmpeg=args.ffmpeg,
        video_path=video_only,
        audio_path=audio_mix,
        output_path=output_path,
        duration=duration,
    )

    manifest = {
        "version": 4,
        "rendered_at": datetime.now(timezone.utc).isoformat(),
        "project": project_dir.name,
        "timeline": rel(project_dir, timeline_path),
        "image_motion_plan": rel(project_dir, motion_plan_path or (project_dir / "analysis" / "image-motion-plan.json")),
        "output": rel(project_dir, output_path),
        "work_dir": rel(project_dir, work_dir),
        "settings": {"width": WIDTH, "height": HEIGHT, "fps": FPS, "duration_seconds": duration},
        "rendered_segments": rendered_segments,
        "audio": audio_manifest,
        "probe": {
            "output_duration_seconds": ffprobe_duration(output_path),
            "video_only_duration_seconds": ffprobe_duration(video_only),
            "audio_mix_duration_seconds": ffprobe_duration(audio_mix),
        },
    }
    write_json(project_dir / "outputs" / "rough-cut-render-manifest.json", manifest)
    print(json.dumps({"ok": True, "output": str(output_path), "manifest": str(project_dir / "outputs" / "rough-cut-render-manifest.json")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)
