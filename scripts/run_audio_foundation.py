#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import re
import shutil
import subprocess
import urllib.request
from urllib.parse import urlparse

from poe.client import PoeConfig, load_poe_config
from poe.media import generate_audio
from poe.usage import append_cost_event, write_usage_json

MAX_SPEEDUP = 1.2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build mock audio foundations from a script.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    return parser.parse_args()


def build_narration_prompt(lines: list[str], duration_seconds: int, language: str) -> str:
    _ = duration_seconds
    _ = language
    return "\n".join(lines)


def _line_weight(text: str) -> float:
    stripped = "".join(ch for ch in text if not ch.isspace())
    punctuation_bonus = sum(1 for ch in text if ch in "，。！？；：、,.;:!?")
    return max(float(len(stripped) + punctuation_bonus * 2), 1.0)


def _weighted_targets(lines: list[str], total_duration: float) -> list[float]:
    safe_duration = max(float(total_duration), 1.0)
    weights = [_line_weight(line) for line in lines]
    total_weight = sum(weights)
    if total_weight <= 0:
        weights = [1.0 for _ in lines]
        total_weight = float(len(lines))
    raw_durations = [safe_duration * (weight / total_weight) for weight in weights]
    targets: list[float] = []
    cursor = 0.0
    for duration in raw_durations[:-1]:
        cursor += duration
        targets.append(round(cursor, 3))
    return targets


def _detect_silence_midpoints(audio_path: pathlib.Path) -> list[float]:
    if not audio_path.is_file() or not shutil.which("ffmpeg"):
        return []
    result = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(audio_path),
            "-af",
            "silencedetect=noise=-35dB:d=0.18",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 and not result.stderr:
        return []

    start_pattern = re.compile(r"silence_start:\s*([0-9.]+)")
    end_pattern = re.compile(r"silence_end:\s*([0-9.]+)")
    starts: list[float] = []
    mids: list[float] = []
    for raw_line in result.stderr.splitlines():
        start_match = start_pattern.search(raw_line)
        if start_match:
            starts.append(float(start_match.group(1)))
            continue
        end_match = end_pattern.search(raw_line)
        if end_match and starts:
            start = starts.pop(0)
            end = float(end_match.group(1))
            if end > start:
                mids.append(round((start + end) / 2.0, 3))
    return sorted(set(mids))


def _snap_targets_to_pauses(
    targets: list[float],
    pause_midpoints: list[float],
    total_duration: float,
) -> list[float]:
    if not targets:
        return []
    if not pause_midpoints:
        return targets

    snapped: list[float] = []
    cursor = 0.0
    for index, target in enumerate(targets, start=1):
        remaining = len(targets) - index
        min_next = cursor + 0.15
        max_next = max(total_duration - (remaining + 1) * 0.15, min_next)
        candidates = [point for point in pause_midpoints if min_next <= point <= max_next]
        if not candidates:
            picked = min(max(target, min_next), max_next)
        else:
            picked = min(candidates, key=lambda point: abs(point - target))
        picked = round(picked, 3)
        if picked <= cursor:
            picked = round(cursor + 0.15, 3)
        snapped.append(picked)
        cursor = picked
    return snapped


def build_weighted_segments(
    lines: list[str],
    total_duration: float,
    pause_aligned_path: pathlib.Path | None = None,
) -> tuple[list[dict[str, float | str]], str]:
    if not lines:
        return [], "empty"
    safe_duration = max(float(total_duration), 1.0)
    targets = _weighted_targets(lines, safe_duration)
    strategy = "weighted_by_text_length_with_punctuation"
    if pause_aligned_path is not None:
        pause_midpoints = _detect_silence_midpoints(pause_aligned_path)
        if pause_midpoints:
            targets = _snap_targets_to_pauses(targets, pause_midpoints, safe_duration)
            strategy = "pause_aligned_weighted"

    segments: list[dict[str, float | str]] = []
    cursor = 0.0
    for index, line in enumerate(lines, start=1):
        start = round(cursor, 2)
        if index == len(lines):
            end = round(safe_duration, 2)
        else:
            end = round(float(targets[index - 1]), 2)
        if index == len(lines):
            end = round(safe_duration, 2)
        if end <= start:
            end = round(start + 0.01, 2)
        cursor = end
        segments.append(
            {
                "segment_id": f"seg-{index}",
                "text": line,
                "start": start,
                "end": end,
            }
        )
    return segments, strategy


def _detect_file_suffix(url: str) -> str:
    path = urlparse(url).path or ""
    suffix = pathlib.Path(path).suffix.lower()
    return suffix if suffix else ".mp3"


def download_audio_to_local(url: str, target_path: pathlib.Path) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "audio/*,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        data = response.read()
    target_path.write_bytes(data)


def probe_duration_seconds(audio_path: pathlib.Path) -> float | None:
    if not audio_path.is_file():
        return None
    if not shutil.which("ffprobe"):
        return None
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    try:
        value = float(result.stdout.strip())
    except ValueError:
        return None
    if value <= 0:
        return None
    return round(value, 2)


def _build_atempo_filters(speed_ratio: float) -> str:
    factors: list[float] = []
    remaining = max(speed_ratio, 0.01)
    while remaining > 2.0:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5:
        factors.append(0.5)
        remaining /= 0.5
    factors.append(remaining)
    return ",".join(f"atempo={factor:.6f}" for factor in factors)


def time_fit_audio_to_duration(
    source_path: pathlib.Path,
    output_path: pathlib.Path,
    duration_seconds: int,
    max_speedup: float = MAX_SPEEDUP,
) -> tuple[bool, float | None, float | None]:
    target = max(duration_seconds, 1)
    source_duration = probe_duration_seconds(source_path)
    if source_duration is None or source_duration <= 0:
        return False, None, None

    required_speed_ratio = source_duration / float(target)
    applied_speed_ratio = required_speed_ratio
    effective_target = float(target)
    if required_speed_ratio > max_speedup:
        applied_speed_ratio = max_speedup
        effective_target = round(source_duration / max_speedup, 2)

    filters = _build_atempo_filters(applied_speed_ratio)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-i",
            str(source_path),
            "-filter:a",
            filters,
            "-t",
            str(effective_target),
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0 or not output_path.is_file():
        return False, None, None
    output_duration = probe_duration_seconds(output_path)
    return True, output_duration, applied_speed_ratio


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    script = json.loads((project_dir / "script" / "script.json").read_text(encoding="utf-8"))
    task_input = json.loads((project_dir / "input" / "input.json").read_text(encoding="utf-8"))
    # Prefer project-local Poe config; fall back to repo-root .env.
    project_env = project_dir / ".env"
    config = load_poe_config(env_path=project_env if project_env.is_file() else None)
    audio_dir = project_dir / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)

    raw_track = script.get("audio_track", [])
    script_lines = []
    for item in raw_track:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
        else:
            text = str(item).strip()
        if text:
            script_lines.append(text)
    if not script_lines:
        raise ValueError("script/audio_track must be a non-empty list")

    requested_duration = int(task_input["duration_seconds"])
    narration_prompt = build_narration_prompt(
        lines=script_lines,
        duration_seconds=requested_duration,
        language=str(task_input["language"]),
    )

    generation_error: str | None = None
    try:
        audio_result = generate_audio(
            config=config,
            model=str(task_input["audio_model"]),
            prompt=narration_prompt,
            duration_seconds=requested_duration,
            language=str(task_input["language"]),
        )
    except Exception as exc:  # pragma: no cover - network/provider edge
        generation_error = str(exc)
        audio_result = generate_audio(
            config=PoeConfig(api_key="", base_url=config.base_url),
            model=str(task_input["audio_model"]),
            prompt=narration_prompt,
            duration_seconds=requested_duration,
            language=str(task_input["language"]),
        )

    local_audio_relpath: str | None = None
    local_audio_duration: float | None = None
    original_audio_relpath: str | None = None
    original_audio_duration: float | None = None
    trim_applied = False
    fit_speed_ratio: float | None = None
    max_speedup_limit: float = MAX_SPEEDUP
    download_error: str | None = None
    audio_url = audio_result.get("audio_url")
    if isinstance(audio_url, str) and audio_url.startswith(("http://", "https://", "file://")):
        try:
            local_audio_name = f"voiceover-source{_detect_file_suffix(audio_url)}"
            local_audio_path = audio_dir / local_audio_name
            download_audio_to_local(audio_url, local_audio_path)
            original_audio_relpath = str(local_audio_path.relative_to(project_dir))
            original_audio_duration = probe_duration_seconds(local_audio_path)

            selected_audio_path = local_audio_path
            selected_audio_duration = original_audio_duration
            if (
                original_audio_duration is not None
                and abs(original_audio_duration - requested_duration) > 1
                and shutil.which("ffmpeg")
            ):
                trimmed_path = audio_dir / "voiceover-main.mp3"
                ok, trimmed_duration, applied_ratio = time_fit_audio_to_duration(
                    local_audio_path,
                    trimmed_path,
                    requested_duration,
                    max_speedup=MAX_SPEEDUP,
                )
                if ok:
                    selected_audio_path = trimmed_path
                    selected_audio_duration = trimmed_duration if trimmed_duration else float(requested_duration)
                    trim_applied = True
                    fit_speed_ratio = applied_ratio

            local_audio_relpath = str(selected_audio_path.relative_to(project_dir))
            local_audio_duration = selected_audio_duration
        except Exception as exc:  # pragma: no cover - network/storage edge
            download_error = str(exc)

    effective_duration = local_audio_duration if local_audio_duration else float(requested_duration)
    pause_source_path = (project_dir / local_audio_relpath) if local_audio_relpath else None
    segments, segment_strategy = build_weighted_segments(
        script_lines,
        effective_duration,
        pause_aligned_path=pause_source_path,
    )

    beat_grid = {
        "beats": [
            {"time": round(segment["start"], 2), "kind": "narration_start"}
            for segment in segments
        ]
        + [{"time": round(float(segments[-1]["end"]), 2), "kind": "climax"}]
    }
    bgm_selection = {
        "track_id": "bgm-audio-first-001",
        "mood": script["emotion_markers"][0]["label"],
    }
    voiceover = {
        "segments": segments,
        "target_duration_seconds": requested_duration,
        "actual_duration_seconds": round(effective_duration, 2),
        "source_url": audio_url,
        "source_path": local_audio_relpath,
        "source_original_path": original_audio_relpath,
        "download_error": download_error,
        "trim_applied": trim_applied,
        "source_original_duration_seconds": original_audio_duration,
        "generation_error": generation_error,
        "segment_strategy": segment_strategy,
        "max_speedup_limit": max_speedup_limit,
        "fit_speed_ratio": fit_speed_ratio,
    }
    tts_response = {
        "provider": "poe",
        "mode": audio_result["mode"],
        "model": audio_result["model"],
        "request_id": audio_result["request_id"],
        "prompt": narration_prompt,
        "target_duration_seconds": requested_duration,
        "actual_duration_seconds": round(effective_duration, 2),
        "source_url": audio_url,
        "source_path": local_audio_relpath,
        "source_original_path": original_audio_relpath,
        "download_error": download_error,
        "trim_applied": trim_applied,
        "source_original_duration_seconds": original_audio_duration,
        "generation_error": generation_error,
        "max_speedup_limit": max_speedup_limit,
        "fit_speed_ratio": fit_speed_ratio,
        "response": audio_result["raw_response"],
    }
    usage = {
        "provider": "poe",
        "mode": audio_result["mode"],
        "model": audio_result["model"],
        "request_id": audio_result["request_id"],
        "cost_points": audio_result["usage"]["cost_points"],
        "target_duration_seconds": requested_duration,
        "actual_duration_seconds": round(effective_duration, 2),
    }

    (audio_dir / "voiceover.json").write_text(json.dumps(voiceover, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "bgm-selection.json").write_text(json.dumps(bgm_selection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "beat-grid.json").write_text(json.dumps(beat_grid, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (audio_dir / "voiceover.prompt.txt").write_text(narration_prompt + "\n", encoding="utf-8")
    write_usage_json(
        audio_dir / "voiceover-request.json",
        {
            "provider": "poe",
            "model": audio_result["model"],
            "request_id": audio_result["request_id"],
            "prompt_path": "audio/voiceover.prompt.txt",
            "target_duration_seconds": requested_duration,
            "source_url": audio_url,
            "source_path": local_audio_relpath,
            "source_original_path": original_audio_relpath,
            "download_error": download_error,
            "trim_applied": trim_applied,
            "source_original_duration_seconds": original_audio_duration,
            "generation_error": generation_error,
            "max_speedup_limit": max_speedup_limit,
            "fit_speed_ratio": fit_speed_ratio,
        },
    )
    write_usage_json(audio_dir / "tts-response.json", tts_response)
    write_usage_json(audio_dir / "usage.json", usage)
    append_cost_event(
        project_dir,
        {
            "skill": "audio_foundation",
            "model": audio_result["model"],
            "request_id": audio_result["request_id"],
            "cost_points": audio_result["usage"]["cost_points"],
            "output_path": "audio/voiceover.json",
        },
    )
    print(audio_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
