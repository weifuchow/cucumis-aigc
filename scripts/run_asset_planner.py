#!/usr/bin/env python3
"""asset_planner — validator and folder initializer.

This script does NOT call any LLM. Claude Code (the skill) is responsible
for analyzing script.json + storyboard.json and writing assets/asset-plan.json
directly as its reasoning output.

This script's sole job:
  1. Verify assets/asset-plan.json exists (error if not — run the skill first)
  2. Validate required fields and structure
  3. Normalize defaults (aspect_ratio, char_refs, loc_ref, keyframe floor)
  4. Create output folder structure for image generator phases
  5. Write normalized plan back to disk

Usage:
  python scripts/run_asset_planner.py --project <path>
  python scripts/run_asset_planner.py --project <path> --mock  # build minimal plan from storyboard
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate and normalize assets/asset-plan.json written by Claude Code skill."
    )
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Build a minimal mock plan from storyboard (for testing without a real skill run).",
    )
    return parser.parse_args()


def _read_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object, got {type(payload).__name__}")
    return payload


def _validate_and_normalize(plan: dict[str, Any], aspect_ratio: str) -> dict[str, Any]:
    """Validate required keys, fill defaults, enforce keyframe floor of 3.

    The model (Claude Code skill) decides whether characters/locations are needed.
    Empty arrays are valid. Keyframe counts are respected (3–7), padded to 3 if fewer.
    """
    if not isinstance(plan.get("characters"), list):
        raise ValueError("asset-plan.json missing 'characters' array")
    if not isinstance(plan.get("locations"), list):
        raise ValueError("asset-plan.json missing 'locations' array")
    if not isinstance(plan.get("scenes"), list):
        raise ValueError("asset-plan.json missing 'scenes' array")

    # Normalize decisions block (infer from arrays if absent)
    decisions = plan.get("decisions")
    if not isinstance(decisions, dict):
        decisions = {
            "has_characters": len(plan["characters"]) > 0,
            "character_reason": "inferred from characters array",
            "has_locations": len(plan["locations"]) > 0,
            "location_reason": "inferred from locations array",
        }
        plan["decisions"] = decisions

    # Per-scene normalization
    for scene in plan["scenes"]:
        if not isinstance(scene, dict):
            continue
        keyframes = scene.get("keyframes", [])
        if not isinstance(keyframes, list):
            scene["keyframes"] = []
            keyframes = []

        # Pad to minimum 3 keyframes only if fewer than 3
        MIN_KF = 3
        if len(keyframes) < MIN_KF:
            duration = float(scene.get("duration_seconds", 5.0))
            scene_id = str(scene.get("scene_id", "scene"))
            step = duration / max(1, MIN_KF - 1)
            existing_ts = {round(kf.get("timestamp", 0), 2) for kf in keyframes if isinstance(kf, dict)}
            base_prompt = keyframes[0].get("prompt", "cinematic shot") if keyframes else "cinematic shot"
            while len(keyframes) < MIN_KF:
                i = len(keyframes)
                ts = round(step * i, 2)
                while ts in existing_ts:
                    ts = round(ts + 0.1, 2)
                existing_ts.add(ts)
                keyframes.append({
                    "keyframe_id": f"{scene_id}-kf-{i + 1:02d}",
                    "timestamp": ts,
                    "frame_type": "action",
                    "description": f"自动补充关键帧 {i + 1}",
                    "prompt": base_prompt,
                    "negative_prompt": "blurry, low detail",
                    "aspect_ratio": aspect_ratio,
                })
            scene["keyframes"] = keyframes

        # Fill aspect_ratio on keyframes
        for kf in scene["keyframes"]:
            if isinstance(kf, dict):
                kf.setdefault("aspect_ratio", aspect_ratio)

        scene.setdefault("char_refs", [])
        scene.setdefault("loc_ref", "")

    # Fill defaults on character views
    for char in plan.get("characters", []):
        if isinstance(char, dict):
            for view in char.get("views", []):
                if isinstance(view, dict):
                    view.setdefault("aspect_ratio", "1:1")

    # Fill defaults on locations
    for loc in plan.get("locations", []):
        if isinstance(loc, dict):
            loc.setdefault("aspect_ratio", aspect_ratio)

    return plan


def _create_folder_structure(project_dir: pathlib.Path, plan: dict[str, Any]) -> None:
    """Pre-create image output folders so the image generator doesn't need to."""
    base = project_dir / "assets" / "images"
    for char in plan.get("characters", []):
        if isinstance(char, dict) and char.get("char_id"):
            (base / "characters" / char["char_id"]).mkdir(parents=True, exist_ok=True)
    for loc in plan.get("locations", []):
        if isinstance(loc, dict) and loc.get("loc_id"):
            (base / "locations" / loc["loc_id"]).mkdir(parents=True, exist_ok=True)
    for scene in plan.get("scenes", []):
        if isinstance(scene, dict) and scene.get("scene_id"):
            (base / "scenes" / scene["scene_id"]).mkdir(parents=True, exist_ok=True)


def _build_mock_plan(storyboard: dict[str, Any], aspect_ratio: str, style: str) -> dict[str, Any]:
    """Minimal mock plan from storyboard for testing only."""
    scenes_out: list[dict[str, Any]] = []
    for scene in storyboard.get("scenes", []):
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", "scene"))
        start = float(scene.get("start_time", 0))
        end = float(scene.get("end_time", start + 5))
        duration = end - start
        desc = str(scene.get("visual_description", "cinematic shot"))
        n_kf = 5
        step = duration / max(1, n_kf - 1)
        keyframes = [
            {
                "keyframe_id": f"{scene_id}-kf-{i + 1:02d}",
                "timestamp": round(step * i, 2),
                "frame_type": "establishing" if i == 0 else "action",
                "description": f"{desc} (frame {i + 1})",
                "prompt": f"{desc}; {style}; frame {i + 1}/{n_kf}",
                "negative_prompt": "blurry, low detail, bad anatomy",
                "aspect_ratio": aspect_ratio,
            }
            for i in range(n_kf)
        ]
        scenes_out.append({
            "scene_id": scene_id,
            "start_time": start,
            "end_time": end,
            "duration_seconds": duration,
            "char_refs": ["char-main"],
            "loc_ref": "loc-main",
            "keyframes": keyframes,
        })

    return {
        "decisions": {
            "has_characters": True,
            "character_reason": "mock模式默认生成主角占位符",
            "has_locations": True,
            "location_reason": "mock模式默认生成场景占位符",
        },
        "characters": [
            {
                "char_id": "char-main",
                "name": "主角",
                "description": "主角人物占位符",
                "style_lock": style,
                "negative_lock": "different character, inconsistent face",
                "views": [
                    {"view_id": "char-main-front", "view_type": "front", "prompt": f"main character, front view, {style}", "negative_prompt": "blurry", "aspect_ratio": "1:1"},
                    {"view_id": "char-main-34", "view_type": "three_quarter", "prompt": f"main character, three quarter view, {style}", "negative_prompt": "blurry", "aspect_ratio": "1:1"},
                    {"view_id": "char-main-closeup", "view_type": "closeup", "prompt": f"main character, face closeup, {style}", "negative_prompt": "blurry", "aspect_ratio": "1:1"},
                ],
            }
        ],
        "locations": [
            {
                "loc_id": "loc-main",
                "name": "主场景",
                "description": "主要场景占位符",
                "atmosphere": "cinematic",
                "prompt": f"establishing shot, cinematic environment, {style}",
                "negative_prompt": "blurry, low detail",
                "aspect_ratio": aspect_ratio,
            }
        ],
        "scenes": scenes_out,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    args = _parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    output_path = project_dir / "assets" / "asset-plan.json"

    # Read input.json for aspect_ratio / style defaults
    try:
        task_input = _read_json(project_dir / "input" / "input.json", "input")
    except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    aspect_ratio = str(task_input.get("aspect_ratio", "9:16"))
    style = str(task_input.get("style", "cinematic realism"))

    # --mock: build plan from storyboard and write it (testing only)
    if args.mock:
        try:
            storyboard = _read_json(project_dir / "storyboard" / "storyboard.json", "storyboard")
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        plan = _build_mock_plan(storyboard, aspect_ratio, style)
        print("[asset_planner] --mock: building minimal plan from storyboard", flush=True)
    else:
        # Normal mode: Claude Code skill must have already written asset-plan.json
        if not output_path.is_file():
            print(
                "[asset_planner] ERROR: assets/asset-plan.json not found.\n"
                "  Run the 'asset_planner' Claude Code skill first.\n"
                "  The skill reads script.json + storyboard.json and writes asset-plan.json directly.\n"
                "  Use --mock for a placeholder plan during testing.",
                file=sys.stderr,
            )
            return 1

        try:
            plan = _read_json(output_path, "asset-plan")
        except (json.JSONDecodeError, ValueError) as exc:
            print(f"[asset_planner] invalid asset-plan.json: {exc}", file=sys.stderr)
            return 1

    # Validate and normalize
    try:
        plan = _validate_and_normalize(plan, aspect_ratio)
    except ValueError as exc:
        print(f"[asset_planner] validation failed: {exc}", file=sys.stderr)
        return 1

    # Inject / update metadata
    plan["metadata"] = {
        "schema_version": "1.0",
        "generated_by": "asset_planner",
        "mode": "mock" if args.mock else "skill",
        "source_script": "script/script.json",
        "source_storyboard": "storyboard/storyboard.json",
        "character_count": len(plan.get("characters", [])),
        "location_count": len(plan.get("locations", [])),
        "scene_count": len(plan.get("scenes", [])),
    }

    # Write normalized plan
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Create output folder structure
    _create_folder_structure(project_dir, plan)

    char_count = len(plan.get("characters", []))
    loc_count = len(plan.get("locations", []))
    scene_count = len(plan.get("scenes", []))
    decisions = plan.get("decisions", {})
    print(
        f"[asset_planner] validated: {char_count} characters (needed={decisions.get('has_characters')}), "
        f"{loc_count} locations (needed={decisions.get('has_locations')}), "
        f"{scene_count} scenes",
        flush=True,
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
