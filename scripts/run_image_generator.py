#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from poe.client import load_poe_config
from poe.media import generate_image
from poe.usage import append_cost_event, write_usage_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate image assets from engineered prompts.")
    parser.add_argument("--project", required=True, help="Project directory path.")
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


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()

    try:
        prompts_payload = read_json(project_dir / "prompts" / "prompts.json", "prompts")
        task_input = read_json(project_dir / "input" / "input.json", "input")
    except (ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    prompts = prompts_payload.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        print("prompts list must be a non-empty array", file=sys.stderr)
        return 1

    images_dir = project_dir / "assets" / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    config = load_poe_config()
    image_result = generate_image(
        config=config,
        model=str(task_input.get("image_model", "flux-schnell")),
        prompts=[prompt for prompt in prompts if isinstance(prompt, dict)],
    )
    generated_images = image_result.get("images", [])
    image_by_prompt_id: dict[str, dict[str, Any]] = {}
    image_by_scene_id: dict[str, dict[str, Any]] = {}
    for item in generated_images:
        if not isinstance(item, dict):
            continue
        prompt_id = item.get("prompt_id")
        scene_id = item.get("scene_id")
        if isinstance(prompt_id, str) and prompt_id:
            image_by_prompt_id[prompt_id] = item
        if isinstance(scene_id, str) and scene_id:
            image_by_scene_id[scene_id] = item

    images: list[dict[str, Any]] = []
    for index, prompt in enumerate(prompts, start=1):
        if not isinstance(prompt, dict):
            continue
        scene_id = str(prompt.get("scene_id", f"scene-{index}"))
        prompt_id = str(prompt.get("prompt_id", f"prompt-{index}"))
        generated = image_by_prompt_id.get(prompt_id) or image_by_scene_id.get(scene_id) or {}
        prompt_path = images_dir / f"{scene_id}.prompt.txt"
        prompt_path.write_text(
            "\n".join(
                [
                    f"scene_id: {scene_id}",
                    f"positive: {prompt.get('positive_prompt', '')}",
                    f"negative: {prompt.get('negative_prompt', '')}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        images.append(
            {
                "asset_id": f"image-{index}",
                "scene_id": scene_id,
                "path": str(prompt_path.relative_to(project_dir)),
                "preview_url": str(generated.get("url", f"mock://image/{scene_id}.png")),
                "prompt_id": prompt_id,
                "provider": "poe",
                "model": image_result.get("model"),
                "request_id": image_result.get("request_id"),
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
    write_usage_json(
        project_dir / "assets" / "image-requests.json",
        {
            "provider": "poe",
            "mode": image_result.get("mode"),
            "model": image_result.get("model"),
            "request_id": image_result.get("request_id"),
            "response": image_result.get("raw_response"),
        },
    )
    write_usage_json(
        project_dir / "assets" / "image-usage.json",
        {
            "provider": "poe",
            "mode": image_result.get("mode"),
            "model": image_result.get("model"),
            "request_id": image_result.get("request_id"),
            "cost_points": ((image_result.get("usage") or {}).get("cost_points")),
        },
    )
    append_cost_event(
        project_dir,
        {
            "skill": "image_generator",
            "model": image_result.get("model"),
            "request_id": image_result.get("request_id"),
            "cost_points": ((image_result.get("usage") or {}).get("cost_points")),
            "output_path": "assets/manifest.json",
        },
    )
    print(manifest_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
