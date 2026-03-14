#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
import time
import urllib.parse
import urllib.request
from typing import Any

from poe.client import load_poe_config
from poe.media import generate_image
from poe.usage import append_cost_event, write_usage_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate image assets from engineered prompts.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument(
        "--refresh-baseline",
        action="store_true",
        help="Force regenerate baseline anchor images even if cached files exist.",
    )
    parser.add_argument(
        "--consistency-min-bytes",
        type=int,
        default=50000,
        help="Minimum image file size threshold used for lightweight consistency checks.",
    )
    return parser.parse_args()


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
    content_type_lower = content_type.lower()
    if "image/png" in content_type_lower:
        return ".png"
    if "image/jpeg" in content_type_lower or "image/jpg" in content_type_lower:
        return ".jpg"
    if "image/webp" in content_type_lower:
        return ".webp"
    if "image/gif" in content_type_lower:
        return ".gif"
    parsed = urllib.parse.urlparse(url)
    suffix = pathlib.Path(parsed.path).suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".webp", ".gif"}:
        return ".jpg" if suffix == ".jpeg" else suffix
    return ".png"


def download_image(url: str, output_stem: pathlib.Path) -> pathlib.Path:
    last_error: Exception | None = None
    data = b""
    content_type = ""
    for attempt in range(1, 4):
        try:
            request = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "image/*",
                },
            )
            with urllib.request.urlopen(request, timeout=120) as response:
                data = response.read()
                content_type = str(response.headers.get("Content-Type", ""))
            break
        except Exception as exc:  # pragma: no cover - network/provider edge
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


def normalize_cost_points(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    return 0


def collect_request_ids(result: dict[str, Any]) -> list[str]:
    request_ids: list[str] = []
    ids = result.get("request_ids")
    if isinstance(ids, list):
        for item in ids:
            if isinstance(item, str) and item:
                request_ids.append(item)
    request_id = result.get("request_id")
    if isinstance(request_id, str) and request_id and request_id not in request_ids:
        request_ids.append(request_id)
    return request_ids


def build_generated_lookup(result: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_prompt_id: dict[str, dict[str, Any]] = {}
    by_scene_id: dict[str, dict[str, Any]] = {}
    for item in result.get("images", []):
        if not isinstance(item, dict):
            continue
        prompt_id = item.get("prompt_id")
        scene_id = item.get("scene_id")
        if isinstance(prompt_id, str) and prompt_id:
            by_prompt_id[prompt_id] = item
        if isinstance(scene_id, str) and scene_id:
            by_scene_id[scene_id] = item
    return by_prompt_id, by_scene_id


def load_script_optional(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def infer_subject(task_input: dict[str, Any], script_payload: dict[str, Any]) -> str:
    title = str(script_payload.get("title", ""))
    topic = str(task_input.get("topic", ""))
    merged = f"{title} {topic}"
    if "屠龙少年" in merged:
        return "屠龙少年"
    if "少年" in merged:
        return "少年主角"
    return "主角人物"


def infer_transition_scene(prompts: list[dict[str, Any]], script_payload: dict[str, Any]) -> int:
    lines = script_payload.get("audio_track")
    if isinstance(lines, list):
        strong_markers = [
            "已成新的恶龙",
            "成新的恶龙",
            "龙的影子",
            "看清自己",
            "不再欢呼",
            "恐惧与沉默",
            "王座前",
        ]
        for index, line in enumerate(lines, start=1):
            text = str(line)
            if any(marker in text for marker in strong_markers):
                return min(max(index, 2), max(2, len(prompts)))
    return max(2, len(prompts) // 2 + 1)


def build_consistency_profile(
    task_input: dict[str, Any],
    script_payload: dict[str, Any],
    prompts: list[dict[str, Any]],
) -> dict[str, Any]:
    subject = infer_subject(task_input, script_payload)
    transition_scene = infer_transition_scene(prompts, script_payload)
    style = str(task_input.get("style", "cinematic realism"))
    aspect_ratio = str(task_input.get("aspect_ratio", "9:16"))
    return {
        "subject": subject,
        "character_id": f"{subject}-v1",
        "hero_state": "hero_v1",
        "dragon_state": "dragonized_v2",
        "transition_scene": transition_scene,
        "immutable_traits": [
            "same face identity",
            "same armor silhouette",
            "same weapon shape",
            "coherent color palette",
        ],
        "style_lock": f"style:{style}; aspect:{aspect_ratio}; high detail cinematic frame",
        "negative_lock": "different character identity, random costume swap, inconsistent face, extra limbs",
    }


def build_anchor_prompt_specs(profile: dict[str, Any]) -> list[dict[str, Any]]:
    subject = str(profile["subject"])
    style_lock = str(profile["style_lock"])
    traits = ", ".join(profile["immutable_traits"])
    return [
        {
            "anchor_id": "anchor-nine-grid",
            "label": "nine-grid emotion sheet",
            "aspect_ratio": "1:1",
            "positive_prompt": (
                f"{subject}, single image 3x3 character reference sheet, nine-panel emotion states "
                f"(neutral, focused, angry, sad, shocked, determined, exhausted, cold, reflective); "
                f"consistent face identity and costume across all nine panels; {style_lock}; {traits}"
            ),
        },
    ]


def load_cached_baselines(baseline_path: pathlib.Path, project_dir: pathlib.Path) -> list[dict[str, Any]]:
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


def infer_scene_state(scene_index: int, profile: dict[str, Any]) -> str:
    transition_scene = int(profile["transition_scene"])
    return str(profile["dragon_state"] if scene_index >= transition_scene else profile["hero_state"])


def lightweight_consistency_check(path: pathlib.Path, min_bytes: int) -> dict[str, Any]:
    size = path.stat().st_size if path.is_file() else 0
    score = round(min(1.0, size / max(1, min_bytes)), 2)
    return {
        "passed": size >= min_bytes,
        "file_size_bytes": size,
        "score": score,
        "min_bytes_threshold": min_bytes,
    }


def build_scene_prompt_record(
    prompt: dict[str, Any],
    profile: dict[str, Any],
    scene_index: int,
    anchor_ids: list[str],
    default_aspect_ratio: str,
) -> dict[str, Any]:
    scene_id = str(prompt.get("scene_id", f"scene-{scene_index}"))
    prompt_id = str(prompt.get("prompt_id", f"prompt-{scene_index}"))
    source_positive = str(prompt.get("positive_prompt", "cinematic shot"))
    source_negative = str(prompt.get("negative_prompt", "blurry, low detail"))
    style = str(prompt.get("style", "cinematic realism"))
    aspect_ratio = str(prompt.get("aspect_ratio", default_aspect_ratio))
    character_state = infer_scene_state(scene_index, profile)
    anchor_list = ", ".join(anchor_ids)
    full_prompt = (
        f"{profile['style_lock']}; subject:{profile['subject']}; character_state:{character_state}; "
        f"anchor_refs:{anchor_list}; reference_anchor:nine_grid_character_sheet; scene_instruction:{source_positive}; "
        f"continuity_rules:{', '.join(profile['immutable_traits'])}"
    )
    final_negative = f"{source_negative}, {profile['negative_lock']}"
    return {
        "scene_id": scene_id,
        "prompt_id": prompt_id,
        "character_state": character_state,
        "full_prompt": full_prompt,
        "negative_prompt": final_negative,
        "style": style,
        "aspect_ratio": aspect_ratio,
        "source_positive_prompt": source_positive,
        "source_negative_prompt": source_negative,
        "anchor_refs": anchor_ids,
    }


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

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

    script_payload = load_script_optional(project_dir / "script" / "script.json")
    profile = build_consistency_profile(task_input, script_payload, prompts)
    default_aspect_ratio = str(task_input.get("aspect_ratio", "9:16"))
    image_model = str(task_input.get("image_model", "flux-schnell"))

    images_dir = project_dir / "assets" / "images"
    baseline_dir = images_dir / "baselines"
    images_dir.mkdir(parents=True, exist_ok=True)
    baseline_dir.mkdir(parents=True, exist_ok=True)

    baseline_path = project_dir / "assets" / "character-baseline.json"
    baselines = [] if args.refresh_baseline else load_cached_baselines(baseline_path, project_dir)

    # Prefer project-local Poe config (projects/<project>/.env) to support per-project keys.
    config = load_poe_config(env_path=project_dir / ".env")

    all_request_ids: list[str] = []
    total_cost_points = 0
    requests_payload: dict[str, Any] = {
        "provider": "poe",
        "model": image_model,
        "baseline": {},
        "scene_generation": {},
        "retries": [],
    }

    if not baselines:
        anchor_specs = build_anchor_prompt_specs(profile)
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
        baseline_result = generate_image(config=config, model=image_model, prompts=anchor_prompts)
        all_request_ids.extend(collect_request_ids(baseline_result))
        total_cost_points += normalize_cost_points((baseline_result.get("usage") or {}).get("cost_points"))
        mode = str(baseline_result.get("mode", "mock"))
        by_prompt_id, by_scene_id = build_generated_lookup(baseline_result)
        baselines = []
        for item in anchor_specs:
            anchor_id = str(item["anchor_id"])
            generated = by_prompt_id.get(anchor_id) or by_scene_id.get(anchor_id) or {}
            source_url = str(generated.get("url", "")).strip()
            if mode == "live":
                if not source_url.startswith(("http://", "https://")):
                    print(f"missing baseline image url for {anchor_id}", file=sys.stderr)
                    return 1
                try:
                    local_path = download_image(source_url, baseline_dir / anchor_id)
                except Exception as exc:
                    print(f"failed to download baseline {anchor_id}: {exc}", file=sys.stderr)
                    return 1
            else:
                local_path = baseline_dir / f"{anchor_id}.prompt.txt"
                local_path.write_text(
                    "\n".join(
                        [
                            f"anchor_id: {anchor_id}",
                            f"positive: {item['positive_prompt']}",
                            f"negative: {profile['negative_lock']}",
                        ]
                    )
                    + "\n",
                    encoding="utf-8",
                )
            baselines.append(
                {
                    "anchor_id": anchor_id,
                    "label": item["label"],
                    "path": str(local_path.relative_to(project_dir)),
                    "full_prompt": item["positive_prompt"],
                    "negative_prompt": str(profile["negative_lock"]),
                    "request_id": str(generated.get("request_id", baseline_result.get("request_id", ""))),
                }
            )
        baseline_payload = {
            "metadata": {
                "subject": profile["subject"],
                "character_id": profile["character_id"],
                "transition_scene": profile["transition_scene"],
                "model": image_model,
                "mode": mode,
            },
            "anchors": baselines,
        }
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(baseline_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        requests_payload["baseline"] = {
            "mode": mode,
            "request_id": baseline_result.get("request_id"),
            "request_ids": baseline_result.get("request_ids"),
            "response": baseline_result.get("raw_response"),
        }
    else:
        requests_payload["baseline"] = {
            "mode": "cached",
            "request_id": None,
            "request_ids": [],
            "response": {"status": "reused_cached_baselines"},
        }

    anchor_ids = [str(item.get("anchor_id", "")) for item in baselines if isinstance(item, dict)]
    scene_prompt_records: list[dict[str, Any]] = []
    scene_generation_prompts: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts, start=1):
        record = build_scene_prompt_record(
            prompt=prompt,
            profile=profile,
            scene_index=index,
            anchor_ids=anchor_ids,
            default_aspect_ratio=default_aspect_ratio,
        )
        scene_prompt_records.append(record)
        scene_generation_prompts.append(
            {
                "scene_id": record["scene_id"],
                "prompt_id": record["prompt_id"],
                "positive_prompt": record["full_prompt"],
                "negative_prompt": record["negative_prompt"],
                "style": record["style"],
                "aspect_ratio": record["aspect_ratio"],
            }
        )

    prompt_manifest_path = project_dir / "assets" / "image-prompts.json"
    prompt_manifest_payload = {
        "metadata": {
            "provider": "poe",
            "model": image_model,
            "subject": profile["subject"],
            "transition_scene": profile["transition_scene"],
            "baseline_source": "assets/character-baseline.json",
            "prompt_count": len(scene_prompt_records),
        },
        "prompts": scene_prompt_records,
    }
    prompt_manifest_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_manifest_path.write_text(
        json.dumps(prompt_manifest_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    scene_result = generate_image(config=config, model=image_model, prompts=scene_generation_prompts)
    scene_mode = str(scene_result.get("mode", "mock"))
    all_request_ids.extend(collect_request_ids(scene_result))
    total_cost_points += normalize_cost_points((scene_result.get("usage") or {}).get("cost_points"))
    requests_payload["scene_generation"] = {
        "mode": scene_mode,
        "request_id": scene_result.get("request_id"),
        "request_ids": scene_result.get("request_ids"),
        "response": scene_result.get("raw_response"),
    }
    by_prompt_id, by_scene_id = build_generated_lookup(scene_result)

    images: list[dict[str, Any]] = []
    for index, record in enumerate(scene_prompt_records, start=1):
        scene_id = str(record["scene_id"])
        prompt_id = str(record["prompt_id"])
        generated = by_prompt_id.get(prompt_id) or by_scene_id.get(scene_id) or {}
        source_url = str(generated.get("url", "")).strip()
        request_id = str(generated.get("request_id", scene_result.get("request_id", "")))

        if scene_mode == "live":
            if not source_url.startswith(("http://", "https://")):
                print(f"missing downloadable image url for {scene_id}", file=sys.stderr)
                return 1
            try:
                local_asset_path = download_image(source_url, images_dir / scene_id)
            except Exception as exc:
                print(f"failed to download image for {scene_id}: {exc}", file=sys.stderr)
                return 1
        else:
            local_asset_path = images_dir / f"{scene_id}.prompt.txt"
            local_asset_path.write_text(
                "\n".join(
                    [
                        f"scene_id: {scene_id}",
                        f"full_prompt: {record['full_prompt']}",
                        f"negative_prompt: {record['negative_prompt']}",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

        consistency = lightweight_consistency_check(local_asset_path, args.consistency_min_bytes)
        retry_count = 0
        if scene_mode == "live" and not consistency["passed"]:
            retry_count = 1
            retry_prompt = dict(record)
            retry_prompt["full_prompt"] = (
                f"{record['full_prompt']}; strict identity lock: keep same face, same armor, same weapon silhouette"
            )
            retry_result = generate_image(
                config=config,
                model=image_model,
                prompts=[
                    {
                        "scene_id": scene_id,
                        "prompt_id": prompt_id,
                        "positive_prompt": retry_prompt["full_prompt"],
                        "negative_prompt": retry_prompt["negative_prompt"],
                        "style": retry_prompt["style"],
                        "aspect_ratio": retry_prompt["aspect_ratio"],
                    }
                ],
            )
            all_request_ids.extend(collect_request_ids(retry_result))
            total_cost_points += normalize_cost_points((retry_result.get("usage") or {}).get("cost_points"))
            retry_by_prompt, retry_by_scene = build_generated_lookup(retry_result)
            retry_generated = retry_by_prompt.get(prompt_id) or retry_by_scene.get(scene_id) or {}
            retry_url = str(retry_generated.get("url", "")).strip()
            if retry_url.startswith(("http://", "https://")):
                try:
                    local_asset_path = download_image(retry_url, images_dir / scene_id)
                    request_id = str(retry_generated.get("request_id", retry_result.get("request_id", request_id)))
                    consistency = lightweight_consistency_check(local_asset_path, args.consistency_min_bytes)
                except Exception:
                    pass
            requests_payload["retries"].append(
                {
                    "scene_id": scene_id,
                    "mode": retry_result.get("mode"),
                    "request_id": retry_result.get("request_id"),
                    "request_ids": retry_result.get("request_ids"),
                    "response": retry_result.get("raw_response"),
                }
            )

        images.append(
            {
                "asset_id": f"image-{index}",
                "scene_id": scene_id,
                "path": str(local_asset_path.relative_to(project_dir)),
                "prompt_id": prompt_id,
                "provider": "poe",
                "model": image_model,
                "request_id": request_id,
                "full_prompt": record["full_prompt"],
                "negative_prompt": record["negative_prompt"],
                "character_state": record["character_state"],
                "anchor_refs": record["anchor_refs"],
                "consistency_check": {
                    **consistency,
                    "retries": retry_count,
                },
            }
        )

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
    if requests_payload["baseline"].get("mode") == "cached" and scene_mode == "mock":
        final_mode = "mock"

    write_usage_json(
        project_dir / "assets" / "image-requests.json",
        {
            "provider": "poe",
            "mode": final_mode,
            "model": image_model,
            "request_id": final_request_id,
            "request_ids": final_request_ids,
            "response": requests_payload,
        },
    )
    write_usage_json(
        project_dir / "assets" / "image-usage.json",
        {
            "provider": "poe",
            "mode": final_mode,
            "model": image_model,
            "request_id": final_request_id,
            "request_ids": final_request_ids,
            "cost_points": total_cost_points,
            "consistency": {
                "min_bytes_threshold": args.consistency_min_bytes,
                "passed_count": sum(
                    1
                    for item in images
                    if isinstance(item.get("consistency_check"), dict) and item["consistency_check"].get("passed")
                ),
                "total_count": len(images),
            },
        },
    )
    append_cost_event(
        project_dir,
        {
            "skill": "image_generator",
            "model": image_model,
            "request_id": final_request_id,
            "cost_points": total_cost_points,
            "output_path": "assets/manifest.json",
        },
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
