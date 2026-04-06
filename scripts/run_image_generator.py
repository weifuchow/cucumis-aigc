#!/usr/bin/env python3
"""image_generator — multi-phase image asset generation.

New phased mode (when assets/asset-plan.json exists):
  Phase 1 — Character base images: multiple views per character
             → assets/images/characters/{char_id}/{view_id}.ext
  Phase 2 — Location establishing shots
             → assets/images/locations/{loc_id}/establishing.ext
  Phase 3 — Scene keyframes (5-7 per scene) using Phase 1+2 as reference images
             → assets/images/scenes/{scene_id}/{keyframe_id}.ext

Legacy mode (no asset-plan.json): original single-baseline + 1-2 frames per scene.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from typing import Any

from providers.factory import load_provider
from providers.base import MultimodalProvider
from poe.usage import append_cost_event, write_usage_json

# Legacy-only imports (fallback path still uses poe directly)
from poe.client import load_poe_config
from poe.media import generate_image as _poe_generate_image


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate image assets from engineered prompts or asset plan.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--refresh-baseline", action="store_true", help="Force regenerate character/location base images even if cached.")
    parser.add_argument("--consistency-min-bytes", type=int, default=50000, help="Minimum image file size for consistency check.")
    parser.add_argument("--max-scenes", type=int, default=0, help="Debug mode: limit generation to first N scenes (0 = no limit).")
    parser.add_argument("--phase", choices=["all", "characters", "locations", "scenes"], default="all", help="Run only a specific phase (phased mode only).")
    return parser.parse_args()


# ---------------------------------------------------------------------------
# Shared utilities (used by both modes)
# ---------------------------------------------------------------------------

def read_json(path: pathlib.Path, label: str) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"missing {label}: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def read_manifest(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {"images": [], "subtitles": [], "audio": [], "videos": []}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"images": [], "subtitles": [], "audio": [], "videos": []}
    return payload


def _file_ext_from_response(url: str, content_type: str) -> str:
    ct = content_type.lower()
    if "image/png" in ct:
        return ".png"
    if "image/jpeg" in ct or "image/jpg" in ct:
        return ".jpg"
    if "image/webp" in ct:
        return ".webp"
    parsed = urllib.parse.urlparse(url)
    suffix = pathlib.Path(parsed.path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".png"


def download_image(url: str, output_stem: pathlib.Path) -> pathlib.Path:
    last_error: Exception | None = None
    data = b""
    content_type = ""
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "image/*"})
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
                content_type = str(response.headers.get("Content-Type", ""))
            break
        except Exception as exc:
            last_error = exc
            if attempt >= 3:
                raise
            time.sleep(attempt * 1.5)
    if not data and last_error is not None:
        raise last_error
    output_path = output_stem.with_suffix(_file_ext_from_response(url, content_type))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(data)
    return output_path


def normalize_cost(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def collect_request_ids(result: dict[str, Any]) -> list[str]:
    ids: list[str] = []
    for id_list in [result.get("request_ids"), result.get("task_ids")]:
        if isinstance(id_list, list):
            for item in id_list:
                if isinstance(item, str) and item and item not in ids:
                    ids.append(item)
    request_id = result.get("request_id")
    if isinstance(request_id, str) and request_id and request_id not in ids:
        ids.append(request_id)
    return ids


def lightweight_consistency_check(path: pathlib.Path, min_bytes: int) -> dict[str, Any]:
    size = path.stat().st_size if path.is_file() else 0
    return {
        "passed": size >= min_bytes,
        "file_size_bytes": size,
        "score": round(min(1.0, size / max(1, min_bytes)), 2),
        "min_bytes_threshold": min_bytes,
    }


def _write_mock_placeholder(path: pathlib.Path, label: str, prompt: str) -> pathlib.Path:
    out = path.with_suffix(".prompt.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(f"{label}\n{prompt}\n", encoding="utf-8")
    return out


# ---------------------------------------------------------------------------
# Phased mode helpers
# ---------------------------------------------------------------------------

def load_asset_plan(project_dir: pathlib.Path) -> dict[str, Any] | None:
    path = project_dir / "assets" / "asset-plan.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _generate_one_image(
    provider: MultimodalProvider,
    model: str,
    scene_id: str,
    prompt_id: str,
    positive_prompt: str,
    negative_prompt: str,
    aspect_ratio: str,
    ref_images: list[dict[str, str]],
) -> dict[str, Any]:
    """Call provider.generate_image() for a single image. Returns the result dict."""
    prompt_spec: dict[str, Any] = {
        "scene_id": scene_id,
        "prompt_id": prompt_id,
        "positive_prompt": positive_prompt,
        "negative_prompt": negative_prompt,
        "aspect_ratio": aspect_ratio,
    }
    if ref_images:
        prompt_spec["_ref_images"] = ref_images
    return provider.generate_image(model, [prompt_spec])


def _save_image_result(
    result: dict[str, Any],
    scene_id: str,
    output_stem: pathlib.Path,
    is_live: bool,
    label: str,
    positive_prompt: str,
) -> pathlib.Path:
    """Download or create placeholder for a generated image. Returns local path."""
    if is_live:
        images = result.get("images", [])
        url = str(images[0].get("url", "")) if images else ""
        if not url.startswith(("http://", "https://", "file://")):
            raise RuntimeError(f"missing image URL for {label} (scene={scene_id})")
        return download_image(url, output_stem)
    return _write_mock_placeholder(output_stem, label, positive_prompt)


# ---------------------------------------------------------------------------
# Phase 1: Character base images
# ---------------------------------------------------------------------------

def _phase1_characters(
    provider: MultimodalProvider,
    model: str,
    asset_plan: dict[str, Any],
    project_dir: pathlib.Path,
    refresh: bool,
    min_bytes: int,
) -> dict[str, list[dict[str, Any]]]:
    """Generate character view images. Returns {char_id: [manifest_entry, ...]}."""
    characters = asset_plan.get("characters", [])
    char_dir = project_dir / "assets" / "images" / "characters"
    char_paths: dict[str, list[dict[str, Any]]] = {}
    total_cost = 0

    for char in characters:
        if not isinstance(char, dict):
            continue
        char_id = str(char.get("char_id", "char"))
        char_name = str(char.get("name", char_id))
        entries: list[dict[str, Any]] = []

        for view in char.get("views", []):
            if not isinstance(view, dict):
                continue
            view_id = str(view.get("view_id", "view"))
            view_type = str(view.get("view_type", "front"))
            positive_prompt = str(view.get("prompt", ""))
            negative_prompt = str(view.get("negative_prompt", "blurry, low detail"))
            aspect_ratio = str(view.get("aspect_ratio", "1:1"))

            output_stem = char_dir / char_id / view_id

            # Cache check
            if not refresh:
                for ext in [".png", ".jpg", ".webp", ".prompt.txt"]:
                    candidate = output_stem.with_suffix(ext)
                    if candidate.is_file():
                        consistency = lightweight_consistency_check(candidate, min_bytes)
                        if consistency["passed"] or ext == ".prompt.txt":
                            print(f"[image] phase1 cache hit: {candidate.name}", flush=True)
                            entries.append({
                                "char_id": char_id,
                                "view_id": view_id,
                                "view_type": view_type,
                                "path": str(candidate.relative_to(project_dir)),
                                "prompt": positive_prompt,
                                "cached": True,
                            })
                            break
                else:
                    pass  # not cached, will generate below
                if entries and entries[-1].get("cached"):
                    continue

            print(f"[image] phase1 generating: {char_name} / {view_type}", flush=True)
            result = _generate_one_image(
                provider, model,
                scene_id=view_id,
                prompt_id=view_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                ref_images=[],
            )
            total_cost += normalize_cost((result.get("usage") or {}).get("cost_points") or (result.get("usage") or {}).get("credits"))
            is_live = result.get("mode") == "live"
            local_path = _save_image_result(result, view_id, output_stem, is_live, f"char:{char_id}/{view_type}", positive_prompt)
            entries.append({
                "char_id": char_id,
                "view_id": view_id,
                "view_type": view_type,
                "path": str(local_path.relative_to(project_dir)),
                "prompt": positive_prompt,
                "cached": False,
            })

        char_paths[char_id] = entries
        print(f"[image] phase1 done: {char_name} ({len(entries)} views)", flush=True)

    # Write character manifest
    char_manifest_path = project_dir / "assets" / "character-manifest.json"
    char_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    char_manifest_path.write_text(
        json.dumps({"characters": [
            {"char_id": cid, "views": entries}
            for cid, entries in char_paths.items()
        ]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_cost_event(project_dir, {"skill": "image_generator.phase1", "model": model, "cost": total_cost})
    return char_paths


# ---------------------------------------------------------------------------
# Phase 2: Location establishing shots
# ---------------------------------------------------------------------------

def _phase2_locations(
    provider: MultimodalProvider,
    model: str,
    asset_plan: dict[str, Any],
    project_dir: pathlib.Path,
    refresh: bool,
    min_bytes: int,
) -> dict[str, dict[str, Any]]:
    """Generate location establishing shots. Returns {loc_id: manifest_entry}."""
    locations = asset_plan.get("locations", [])
    loc_dir = project_dir / "assets" / "images" / "locations"
    loc_paths: dict[str, dict[str, Any]] = {}
    total_cost = 0

    for loc in locations:
        if not isinstance(loc, dict):
            continue
        loc_id = str(loc.get("loc_id", "loc"))
        loc_name = str(loc.get("name", loc_id))
        positive_prompt = str(loc.get("prompt", "establishing shot, cinematic environment"))
        negative_prompt = str(loc.get("negative_prompt", "blurry, low detail, people"))
        aspect_ratio = str(loc.get("aspect_ratio", "9:16"))
        output_stem = loc_dir / loc_id / "establishing"

        if not refresh:
            for ext in [".png", ".jpg", ".webp", ".prompt.txt"]:
                candidate = output_stem.with_suffix(ext)
                if candidate.is_file():
                    print(f"[image] phase2 cache hit: {candidate.name}", flush=True)
                    loc_paths[loc_id] = {
                        "loc_id": loc_id,
                        "path": str(candidate.relative_to(project_dir)),
                        "prompt": positive_prompt,
                        "cached": True,
                    }
                    break
            if loc_id in loc_paths:
                continue

        print(f"[image] phase2 generating: {loc_name}", flush=True)
        result = _generate_one_image(
            provider, model,
            scene_id=loc_id,
            prompt_id=f"{loc_id}-establishing",
            positive_prompt=positive_prompt,
            negative_prompt=negative_prompt,
            aspect_ratio=aspect_ratio,
            ref_images=[],
        )
        total_cost += normalize_cost((result.get("usage") or {}).get("cost_points") or (result.get("usage") or {}).get("credits"))
        is_live = result.get("mode") == "live"
        local_path = _save_image_result(result, loc_id, output_stem, is_live, f"loc:{loc_id}", positive_prompt)
        loc_paths[loc_id] = {
            "loc_id": loc_id,
            "path": str(local_path.relative_to(project_dir)),
            "prompt": positive_prompt,
            "cached": False,
        }
        print(f"[image] phase2 done: {loc_name}", flush=True)

    # Write location manifest
    loc_manifest_path = project_dir / "assets" / "location-manifest.json"
    loc_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    loc_manifest_path.write_text(
        json.dumps({"locations": list(loc_paths.values())}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    append_cost_event(project_dir, {"skill": "image_generator.phase2", "model": model, "cost": total_cost})
    return loc_paths


# ---------------------------------------------------------------------------
# Phase 3: Scene keyframes (5-7 per scene)
# ---------------------------------------------------------------------------

def _build_ref_images(
    char_refs: list[str],
    loc_ref: str,
    char_paths: dict[str, list[dict[str, Any]]],
    loc_paths: dict[str, dict[str, Any]],
    project_dir: pathlib.Path,
    max_refs: int = 5,
) -> list[dict[str, str]]:
    """Build reference image list from character views + location image."""
    refs: list[dict[str, str]] = []

    # Add location establishing shot first (scene context)
    loc_entry = loc_paths.get(loc_ref)
    if loc_entry and loc_entry.get("path"):
        abs_path = str((project_dir / loc_entry["path"]).resolve())
        refs.append({"path": abs_path, "role": "location"})

    # Add character primary views (front + closeup for each character)
    priority_views = ["front", "three_quarter", "closeup"]
    for char_id in char_refs:
        views = char_paths.get(char_id, [])
        view_map = {v.get("view_type"): v for v in views if isinstance(v, dict)}
        for vtype in priority_views:
            entry = view_map.get(vtype)
            if entry and entry.get("path") and len(refs) < max_refs:
                abs_path = str((project_dir / entry["path"]).resolve())
                refs.append({"path": abs_path, "role": f"char_{char_id}_{vtype}"})

    return refs[:max_refs]


def _phase3_scenes(
    provider: MultimodalProvider,
    model: str,
    asset_plan: dict[str, Any],
    project_dir: pathlib.Path,
    char_paths: dict[str, list[dict[str, Any]]],
    loc_paths: dict[str, dict[str, Any]],
    args: argparse.Namespace,
) -> list[dict[str, Any]]:
    """Generate 5-7 keyframe images per scene. Returns flat manifest image list."""
    scenes = asset_plan.get("scenes", [])
    if args.max_scenes:
        scenes = scenes[: args.max_scenes]

    scene_dir = project_dir / "assets" / "images" / "scenes"
    all_images: list[dict[str, Any]] = []
    total_cost = 0
    asset_index = 1

    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        scene_id = str(scene.get("scene_id", "scene"))
        char_refs = [str(c) for c in scene.get("char_refs", [])]
        loc_ref = str(scene.get("loc_ref", ""))
        keyframes = [kf for kf in scene.get("keyframes", []) if isinstance(kf, dict)]

        ref_images = _build_ref_images(char_refs, loc_ref, char_paths, loc_paths, project_dir)

        print(f"[image] phase3 scene={scene_id}: {len(keyframes)} keyframes, {len(ref_images)} refs", flush=True)

        for frame_index, keyframe in enumerate(keyframes, start=1):
            kf_id = str(keyframe.get("keyframe_id", f"{scene_id}-kf-{frame_index:02d}"))
            positive_prompt = str(keyframe.get("prompt", "cinematic shot"))
            negative_prompt = str(keyframe.get("negative_prompt", "blurry, low detail"))
            aspect_ratio = str(keyframe.get("aspect_ratio", "9:16"))
            output_stem = scene_dir / scene_id / kf_id

            # Cache check
            if not args.refresh_baseline:
                for ext in [".png", ".jpg", ".webp", ".prompt.txt"]:
                    candidate = output_stem.with_suffix(ext)
                    if candidate.is_file():
                        consistency = lightweight_consistency_check(candidate, args.consistency_min_bytes)
                        if consistency["passed"] or ext == ".prompt.txt":
                            print(f"[image] phase3 cache hit: {candidate.name}", flush=True)
                            all_images.append({
                                "asset_id": f"image-{asset_index}",
                                "scene_id": scene_id,
                                "keyframe_id": kf_id,
                                "frame_index": frame_index,
                                "frame_count": len(keyframes),
                                "timestamp": keyframe.get("timestamp", 0.0),
                                "path": str(candidate.relative_to(project_dir)),
                                "prompt_id": kf_id,
                                "full_prompt": positive_prompt,
                                "negative_prompt": negative_prompt,
                                "consistency_check": {**consistency, "retries": 0},
                                "cached": True,
                            })
                            asset_index += 1
                            break
                if all_images and all_images[-1].get("cached") and all_images[-1].get("scene_id") == scene_id and all_images[-1].get("frame_index") == frame_index:
                    continue

            result = _generate_one_image(
                provider, model,
                scene_id=scene_id,
                prompt_id=kf_id,
                positive_prompt=positive_prompt,
                negative_prompt=negative_prompt,
                aspect_ratio=aspect_ratio,
                ref_images=ref_images,
            )
            cost = normalize_cost(
                (result.get("usage") or {}).get("cost_points")
                or (result.get("usage") or {}).get("credits")
            )
            total_cost += cost
            is_live = result.get("mode") == "live"

            try:
                local_path = _save_image_result(result, scene_id, output_stem, is_live, f"{scene_id}/{kf_id}", positive_prompt)
            except RuntimeError as exc:
                print(f"[image] WARNING: {exc}", file=sys.stderr)
                local_path = _write_mock_placeholder(output_stem, f"{scene_id}/{kf_id}", positive_prompt)

            consistency = lightweight_consistency_check(local_path, args.consistency_min_bytes)
            all_images.append({
                "asset_id": f"image-{asset_index}",
                "scene_id": scene_id,
                "keyframe_id": kf_id,
                "frame_index": frame_index,
                "frame_count": len(keyframes),
                "timestamp": keyframe.get("timestamp", 0.0),
                "path": str(local_path.relative_to(project_dir)),
                "prompt_id": kf_id,
                "full_prompt": positive_prompt,
                "negative_prompt": negative_prompt,
                "consistency_check": {**consistency, "retries": 0},
                "cached": False,
            })
            asset_index += 1

        print(f"[image] phase3 done: scene={scene_id} ({len(keyframes)} frames)", flush=True)

    append_cost_event(project_dir, {"skill": "image_generator.phase3", "model": model, "cost": total_cost})
    return all_images


# ---------------------------------------------------------------------------
# Phased pipeline entry
# ---------------------------------------------------------------------------

def _run_phased_pipeline(args: argparse.Namespace, project_dir: pathlib.Path, asset_plan: dict[str, Any]) -> int:
    try:
        task_input = read_json(project_dir / "input" / "input.json", "input")
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    image_model = str(task_input.get("image_model", "viduq2"))
    provider = load_provider()
    char_paths: dict[str, list[dict[str, Any]]] = {}
    loc_paths: dict[str, dict[str, Any]] = {}
    all_images: list[dict[str, Any]] = []

    # Read LLM decisions to know which phases are actually needed
    decisions = asset_plan.get("decisions", {})
    has_characters = bool(decisions.get("has_characters", len(asset_plan.get("characters", [])) > 0))
    has_locations = bool(decisions.get("has_locations", len(asset_plan.get("locations", [])) > 0))

    if not has_characters:
        print(f"[image] phase1 SKIPPED — model decision: no characters needed ({decisions.get('character_reason', 'no reason given')})", flush=True)
    if not has_locations:
        print(f"[image] phase2 SKIPPED — model decision: no locations needed ({decisions.get('location_reason', 'no reason given')})", flush=True)

    run_chars = args.phase in ("all", "characters") and has_characters
    run_locs = args.phase in ("all", "locations") and has_locations
    run_scenes = args.phase in ("all", "scenes")

    if run_chars:
        char_paths = _phase1_characters(provider, image_model, asset_plan, project_dir, args.refresh_baseline, args.consistency_min_bytes)
    else:
        char_paths = _load_char_paths_from_cache(project_dir)

    if run_locs:
        loc_paths = _phase2_locations(provider, image_model, asset_plan, project_dir, args.refresh_baseline, args.consistency_min_bytes)
    else:
        loc_paths = _load_loc_paths_from_cache(project_dir)

    if run_scenes:
        all_images = _phase3_scenes(provider, image_model, asset_plan, project_dir, char_paths, loc_paths, args)
    else:
        # Load existing scene images from manifest
        existing = read_manifest(project_dir / "assets" / "manifest.json")
        all_images = [img for img in existing.get("images", []) if isinstance(img, dict)]

    # Update manifest
    manifest_path = project_dir / "assets" / "manifest.json"
    manifest = read_manifest(manifest_path)
    manifest["images"] = all_images
    manifest.setdefault("subtitles", [])
    manifest.setdefault("audio", [])
    manifest.setdefault("videos", [])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    total = len(all_images)
    scenes_count = len({img["scene_id"] for img in all_images})
    print(f"[image] phased pipeline complete: {total} images across {scenes_count} scenes", flush=True)
    print(manifest_path)
    return 0


def _load_char_paths_from_cache(project_dir: pathlib.Path) -> dict[str, list[dict[str, Any]]]:
    path = project_dir / "assets" / "character-manifest.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            char["char_id"]: char.get("views", [])
            for char in payload.get("characters", [])
            if isinstance(char, dict)
        }
    except (json.JSONDecodeError, KeyError):
        return {}


def _load_loc_paths_from_cache(project_dir: pathlib.Path) -> dict[str, dict[str, Any]]:
    path = project_dir / "assets" / "location-manifest.json"
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            loc["loc_id"]: loc
            for loc in payload.get("locations", [])
            if isinstance(loc, dict)
        }
    except (json.JSONDecodeError, KeyError):
        return {}


# ---------------------------------------------------------------------------
# Legacy pipeline (original logic, preserved intact)
# ---------------------------------------------------------------------------

def _run_legacy_pipeline(args: argparse.Namespace, project_dir: pathlib.Path) -> int:
    """Original single-baseline + 1-2 frames per scene pipeline."""
    try:
        prompts_payload = read_json(project_dir / "prompts" / "prompts.json", "prompts")
        task_input = read_json(project_dir / "input" / "input.json", "input")
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    raw_prompts = prompts_payload.get("prompts")
    if not isinstance(raw_prompts, list) or not raw_prompts:
        print("prompts list must be a non-empty array", file=sys.stderr)
        return 1
    prompts = [item for item in raw_prompts if isinstance(item, dict)]
    if not prompts:
        print("prompts list contains no usable prompt objects", file=sys.stderr)
        return 1

    script_payload = _load_script_optional(project_dir / "script" / "script.json")
    consistency_override = _load_consistency_profile_override(project_dir)
    profile = _build_consistency_profile(task_input, script_payload, prompts, override=consistency_override)
    default_aspect_ratio = str(task_input.get("aspect_ratio", "9:16"))
    image_model = str(task_input.get("image_model", "flux-schnell"))

    images_dir = project_dir / "assets" / "images"
    baseline_dir = images_dir / "baselines"
    images_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = project_dir / "assets" / "character-baseline.json"
    baselines = [] if args.refresh_baseline else _load_cached_baselines(baseline_path, project_dir)

    project_env = project_dir / ".env"
    config = load_poe_config(env_path=project_env if project_env.is_file() else None)

    all_request_ids: list[str] = []
    total_cost_points = 0
    requests_payload: dict[str, Any] = {"provider": "poe", "model": image_model, "baseline": {}, "scene_generation": {}, "retries": []}

    if not baselines:
        anchor_specs = _build_anchor_prompt_specs(profile)
        anchor_prompts = [
            {
                "scene_id": item["anchor_id"],
                "prompt_id": item["anchor_id"],
                "positive_prompt": item["positive_prompt"],
                "negative_prompt": str(profile["negative_lock"]),
                "style": "character-sheet",
                "aspect_ratio": str(item.get("aspect_ratio", default_aspect_ratio)),
            }
            for item in anchor_specs
        ]
        baseline_result = _poe_generate_image(config=config, model=image_model, prompts=anchor_prompts)
        all_request_ids.extend(collect_request_ids(baseline_result))
        total_cost_points += normalize_cost((baseline_result.get("usage") or {}).get("cost_points"))
        mode = str(baseline_result.get("mode", "mock"))
        by_prompt_id, by_scene_id = _build_generated_lookup(baseline_result)
        baselines = []
        for item in anchor_specs:
            anchor_id = str(item["anchor_id"])
            generated = by_prompt_id.get(anchor_id) or by_scene_id.get(anchor_id) or {}
            source_url = str(generated.get("url", "")).strip()
            if mode == "live":
                if not source_url.startswith(("http://", "https://", "file://")):
                    print(f"missing baseline image url for {anchor_id}", file=sys.stderr)
                    return 1
                try:
                    local_path = download_image(source_url, baseline_dir / anchor_id)
                except Exception as exc:
                    print(f"failed to download baseline {anchor_id}: {exc}", file=sys.stderr)
                    return 1
            else:
                local_path = baseline_dir / f"{anchor_id}.prompt.txt"
                local_path.write_text(f"anchor_id: {anchor_id}\npositive: {item['positive_prompt']}\nnegative: {profile['negative_lock']}\n", encoding="utf-8")
            baselines.append({
                "anchor_id": anchor_id,
                "label": item["label"],
                "path": str(local_path.relative_to(project_dir)),
                "full_prompt": item["positive_prompt"],
                "negative_prompt": str(profile["negative_lock"]),
                "request_id": str(generated.get("request_id", baseline_result.get("request_id", ""))),
            })
        baseline_payload = {
            "metadata": {"subject": profile["subject"], "character_id": profile["character_id"], "transition_scene": profile["transition_scene"], "model": image_model, "mode": mode},
            "anchors": baselines,
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(baseline_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        requests_payload["baseline"] = {"mode": mode, "request_id": baseline_result.get("request_id"), "request_ids": baseline_result.get("request_ids"), "response": baseline_result.get("raw_response")}
    else:
        requests_payload["baseline"] = {"mode": "cached", "request_id": None, "request_ids": [], "response": {"status": "reused_cached_baselines"}}

    anchor_ids = [str(item.get("anchor_id", "")) for item in baselines if isinstance(item, dict)]
    scene_map = _load_storyboard_scene_map(project_dir / "storyboard" / "storyboard.json")
    scene_prompt_records: list[dict[str, Any]] = []
    scene_generation_prompts: list[dict[str, Any]] = []
    frame_prompt_lookup: dict[str, dict[str, Any]] = {}
    scene_frame_plan: dict[str, int] = {}
    active_prompts = prompts if not args.max_scenes else prompts[: args.max_scenes]
    for index, prompt in enumerate(active_prompts, start=1):
        record = _build_scene_prompt_record(prompt=prompt, profile=profile, scene_index=index, anchor_ids=anchor_ids, default_aspect_ratio=default_aspect_ratio)
        scene_prompt_records.append(record)
        scene_meta = scene_map.get(str(record["scene_id"]), {})
        frame_count = _infer_scene_frame_count(scene_meta)
        scene_frame_plan[str(record["scene_id"])] = frame_count
        for frame_index in range(1, frame_count + 1):
            frame_prompt_id = f"{record['prompt_id']}-f{frame_index}"
            frame_positive_prompt = f"{record['full_prompt']}; montage_frame:{frame_index}/{frame_count}; subtle angle/parallax change while preserving identity"
            frame_entry = {"scene_id": record["scene_id"], "prompt_id": frame_prompt_id, "positive_prompt": frame_positive_prompt, "negative_prompt": record["negative_prompt"], "style": record["style"], "aspect_ratio": record["aspect_ratio"]}
            scene_generation_prompts.append(frame_entry)
            frame_prompt_lookup[frame_prompt_id] = {"scene_prompt_id": record["prompt_id"], "frame_index": frame_index, "frame_count": frame_count, "record": record, "frame_positive_prompt": frame_positive_prompt}

    scene_result = _poe_generate_image(config=config, model=image_model, prompts=scene_generation_prompts)
    scene_mode = str(scene_result.get("mode", "mock"))
    all_request_ids.extend(collect_request_ids(scene_result))
    total_cost_points += normalize_cost((scene_result.get("usage") or {}).get("cost_points"))
    requests_payload["scene_generation"] = {"mode": scene_mode, "request_id": scene_result.get("request_id"), "request_ids": scene_result.get("request_ids"), "response": scene_result.get("raw_response")}
    by_prompt_id, by_scene_id = _build_generated_lookup(scene_result)

    images: list[dict[str, Any]] = []
    for index, frame_prompt in enumerate(scene_generation_prompts, start=1):
        scene_id = str(frame_prompt["scene_id"])
        prompt_id = str(frame_prompt["prompt_id"])
        lookup = frame_prompt_lookup.get(prompt_id, {})
        record = lookup.get("record") if isinstance(lookup, dict) else {}
        if not isinstance(record, dict):
            continue
        scene_prompt_id = str(lookup.get("scene_prompt_id", record.get("prompt_id", prompt_id)))
        frame_index = int(lookup.get("frame_index", 1))
        frame_count = int(lookup.get("frame_count", 1))
        generated = by_prompt_id.get(prompt_id) or (by_scene_id.get(scene_id) if frame_count == 1 else {})
        source_url = str(generated.get("url", "")).strip()
        request_id = str(generated.get("request_id", scene_result.get("request_id", "")))
        output_stem = images_dir / scene_id / f"frame-{frame_index:02d}" if frame_count > 1 else images_dir / scene_id

        if scene_mode == "live":
            if not source_url.startswith(("http://", "https://", "file://")):
                print(f"missing downloadable image url for {scene_id}", file=sys.stderr)
                return 1
            try:
                local_asset_path = download_image(source_url, output_stem)
            except Exception as exc:
                print(f"failed to download image for {scene_id}: {exc}", file=sys.stderr)
                return 1
        else:
            local_asset_path = output_stem.with_suffix(".prompt.txt")
            local_asset_path.parent.mkdir(parents=True, exist_ok=True)
            local_asset_path.write_text(f"scene_id: {scene_id}\nfull_prompt: {lookup.get('frame_positive_prompt', record['full_prompt'])}\nnegative_prompt: {record['negative_prompt']}\n", encoding="utf-8")

        consistency = lightweight_consistency_check(local_asset_path, args.consistency_min_bytes)
        retry_count = 0
        if scene_mode == "live" and not consistency["passed"]:
            retry_count = 1
            retry_prompt = dict(frame_prompt)
            retry_lock = str(profile.get("retry_lock", "strict identity lock: keep same face, same armor, same weapon silhouette"))
            retry_prompt["positive_prompt"] = f"{frame_prompt['positive_prompt']}; {retry_lock}"
            retry_result = _poe_generate_image(config=config, model=image_model, prompts=[{"scene_id": scene_id, "prompt_id": prompt_id, "positive_prompt": retry_prompt["positive_prompt"], "negative_prompt": retry_prompt["negative_prompt"], "style": retry_prompt["style"], "aspect_ratio": retry_prompt["aspect_ratio"]}])
            all_request_ids.extend(collect_request_ids(retry_result))
            total_cost_points += normalize_cost((retry_result.get("usage") or {}).get("cost_points"))
            retry_by_prompt, retry_by_scene = _build_generated_lookup(retry_result)
            retry_generated = retry_by_prompt.get(prompt_id) or retry_by_scene.get(scene_id) or {}
            retry_url = str(retry_generated.get("url", "")).strip()
            if retry_url.startswith(("http://", "https://", "file://")):
                try:
                    local_asset_path = download_image(retry_url, images_dir / scene_id)
                    request_id = str(retry_generated.get("request_id", retry_result.get("request_id", request_id)))
                    consistency = lightweight_consistency_check(local_asset_path, args.consistency_min_bytes)
                except Exception:
                    pass
            requests_payload["retries"].append({"scene_id": scene_id, "mode": retry_result.get("mode"), "request_id": retry_result.get("request_id"), "request_ids": retry_result.get("request_ids"), "response": retry_result.get("raw_response")})

        images.append({
            "asset_id": f"image-{index}",
            "scene_id": scene_id,
            "path": str(local_asset_path.relative_to(project_dir)),
            "prompt_id": prompt_id,
            "scene_prompt_id": scene_prompt_id,
            "frame_index": frame_index,
            "frame_count": frame_count,
            "provider": "poe",
            "model": image_model,
            "request_id": request_id,
            "full_prompt": str(lookup.get("frame_positive_prompt", record["full_prompt"])),
            "negative_prompt": record["negative_prompt"],
            "character_state": record["character_state"],
            "anchor_refs": record["anchor_refs"],
            "consistency_check": {**consistency, "retries": retry_count},
        })

    manifest_path = project_dir / "assets" / "manifest.json"
    manifest = read_manifest(manifest_path)
    manifest["images"] = images
    manifest.setdefault("subtitles", [])
    manifest.setdefault("audio", [])
    manifest.setdefault("videos", [])
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    final_request_ids = [item for item in dict.fromkeys(all_request_ids) if item]
    final_request_id = final_request_ids[-1] if final_request_ids else None
    final_mode = scene_mode

    write_usage_json(project_dir / "assets" / "image-requests.json", {"provider": "poe", "mode": final_mode, "model": image_model, "request_id": final_request_id, "request_ids": final_request_ids, "response": requests_payload})
    write_usage_json(project_dir / "assets" / "image-usage.json", {"provider": "poe", "mode": final_mode, "model": image_model, "request_id": final_request_id, "request_ids": final_request_ids, "cost_points": total_cost_points, "consistency": {"min_bytes_threshold": args.consistency_min_bytes, "passed_count": sum(1 for item in images if isinstance(item.get("consistency_check"), dict) and item["consistency_check"].get("passed")), "total_count": len(images)}})
    append_cost_event(project_dir, {"skill": "image_generator", "model": image_model, "request_id": final_request_id, "cost_points": total_cost_points, "output_path": "assets/manifest.json"})
    print(manifest_path)
    return 0


# ---------------------------------------------------------------------------
# Legacy helpers (only used by legacy pipeline)
# ---------------------------------------------------------------------------

def _load_script_optional(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_storyboard_scene_map(path: pathlib.Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for scene in payload.get("scenes", []):
        if isinstance(scene, dict):
            sid = scene.get("scene_id")
            if isinstance(sid, str) and sid:
                result[sid] = scene
    return result


def _load_consistency_profile_override(project_dir: pathlib.Path) -> dict[str, Any] | None:
    path = project_dir / "assets" / "consistency_profile.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        return None


def _infer_subject(task_input: dict[str, Any], script_payload: dict[str, Any]) -> str:
    title = str(script_payload.get("title", ""))
    topic = str(task_input.get("topic", ""))
    merged = f"{title} {topic}"
    if "屠龙少年" in merged:
        return "屠龙少年"
    if "少年" in merged:
        return "少年主角"
    return "主角人物"


def _infer_transition_scene(prompts: list[dict[str, Any]], script_payload: dict[str, Any]) -> int:
    lines = script_payload.get("audio_track")
    if isinstance(lines, list):
        strong_markers = ["已成新的恶龙", "成新的恶龙", "龙的影子", "看清自己", "不再欢呼", "恐惧与沉默", "王座前"]
        for index, line in enumerate(lines, start=1):
            if any(marker in str(line) for marker in strong_markers):
                return min(max(index, 2), max(2, len(prompts)))
    return max(2, len(prompts) // 2 + 1)


def _build_consistency_profile(task_input: dict[str, Any], script_payload: dict[str, Any], prompts: list[dict[str, Any]], override: dict[str, Any] | None = None) -> dict[str, Any]:
    if override:
        consistency_type = str(override.get("consistency_type", "human"))
        profile = dict(override)
        profile.setdefault("consistency_type", consistency_type)
        profile.setdefault("transition_scene", len(prompts))
        if consistency_type == "mascot":
            profile.setdefault("hero_state", "mascot_v1")
            profile.setdefault("dragon_state", "mascot_v1")
        else:
            profile.setdefault("hero_state", "hero_v1")
            profile.setdefault("dragon_state", "dragonized_v2")
        return profile
    subject = _infer_subject(task_input, script_payload)
    transition_scene = _infer_transition_scene(prompts, script_payload)
    style = str(task_input.get("style", "cinematic realism"))
    aspect_ratio = str(task_input.get("aspect_ratio", "9:16"))
    return {
        "consistency_type": "human",
        "subject": subject,
        "character_id": f"{subject}-v1",
        "hero_state": "hero_v1",
        "dragon_state": "dragonized_v2",
        "transition_scene": transition_scene,
        "immutable_traits": ["same face identity", "same armor silhouette", "same weapon shape", "coherent color palette"],
        "style_lock": f"style:{style}; aspect:{aspect_ratio}; high detail cinematic frame",
        "negative_lock": "different character identity, random costume swap, inconsistent face, extra limbs",
        "retry_lock": "strict identity lock: keep same face, same armor, same weapon silhouette",
    }


def _build_anchor_prompt_specs(profile: dict[str, Any]) -> list[dict[str, Any]]:
    anchor_override = profile.get("anchor")
    if isinstance(anchor_override, dict):
        return [anchor_override]
    subject = str(profile["subject"])
    style_lock = str(profile["style_lock"])
    traits = ", ".join(profile["immutable_traits"])
    return [{"anchor_id": "anchor-nine-grid", "label": "nine-grid emotion sheet", "aspect_ratio": "1:1", "positive_prompt": f"{subject}, single image 3x3 character reference sheet, nine-panel emotion states (neutral, focused, angry, sad, shocked, determined, exhausted, cold, reflective); consistent face identity and costume across all nine panels; {style_lock}; {traits}"}]


def _load_cached_baselines(baseline_path: pathlib.Path, project_dir: pathlib.Path) -> list[dict[str, Any]]:
    if not baseline_path.is_file():
        return []
    try:
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    anchors = payload.get("anchors") if isinstance(payload, dict) else None
    if not isinstance(anchors, list):
        return []
    validated: list[dict[str, Any]] = []
    for anchor in anchors:
        if not isinstance(anchor, dict):
            continue
        rel_path = anchor.get("path")
        if not isinstance(rel_path, str) or not rel_path:
            continue
        if not (project_dir / rel_path).is_file():
            return []
        validated.append(anchor)
    return validated


def _infer_scene_state(scene_index: int, profile: dict[str, Any]) -> str:
    return str(profile["dragon_state"] if scene_index >= int(profile["transition_scene"]) else profile["hero_state"])


def _build_generated_lookup(result: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_prompt_id: dict[str, dict[str, Any]] = {}
    by_scene_id: dict[str, dict[str, Any]] = {}
    for item in result.get("images", []):
        if not isinstance(item, dict):
            continue
        pid = item.get("prompt_id")
        sid = item.get("scene_id")
        if isinstance(pid, str) and pid:
            by_prompt_id[pid] = item
        if isinstance(sid, str) and sid:
            by_scene_id[sid] = item
    return by_prompt_id, by_scene_id


def _infer_scene_frame_count(scene_meta: dict[str, Any]) -> int:
    asset_mode = str(scene_meta.get("asset_mode", "")).lower()
    motion_intent = str(scene_meta.get("motion_intent", "")).lower()
    if asset_mode == "static":
        return 2
    if motion_intent in {"hold", "slow_pan", "locked"}:
        return 2
    if motion_intent in {"mixed", "fast_push", "black_flash", "whip_pan"}:
        return 1
    return 1


def _build_scene_prompt_record(prompt: dict[str, Any], profile: dict[str, Any], scene_index: int, anchor_ids: list[str], default_aspect_ratio: str) -> dict[str, Any]:
    scene_id = str(prompt.get("scene_id", f"scene-{scene_index}"))
    prompt_id = str(prompt.get("prompt_id", f"prompt-{scene_index}"))
    source_positive = str(prompt.get("positive_prompt", "cinematic shot"))
    source_negative = str(prompt.get("negative_prompt", "blurry, low detail"))
    style = str(prompt.get("style", "cinematic realism"))
    aspect_ratio = str(prompt.get("aspect_ratio", default_aspect_ratio))
    character_state = _infer_scene_state(scene_index, profile)
    traits_str = ", ".join(profile.get("immutable_traits", []))
    full_prompt = f"{source_positive}; {traits_str}" if traits_str else source_positive
    final_negative = f"{source_negative}, {profile['negative_lock']}"
    return {"scene_id": scene_id, "prompt_id": prompt_id, "character_state": character_state, "full_prompt": full_prompt, "negative_prompt": final_negative, "style": style, "aspect_ratio": aspect_ratio, "source_positive_prompt": source_positive, "source_negative_prompt": source_negative, "anchor_refs": anchor_ids}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    asset_plan = load_asset_plan(project_dir)

    if asset_plan is not None:
        print(f"[image] asset-plan.json found — running phased pipeline", flush=True)
        return _run_phased_pipeline(args, project_dir, asset_plan)
    else:
        print(f"[image] no asset-plan.json — running legacy pipeline", flush=True)
        return _run_legacy_pipeline(args, project_dir)


if __name__ == "__main__":
    raise SystemExit(main())
