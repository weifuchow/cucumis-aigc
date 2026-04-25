#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any


AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}
VISUAL_SUFFIXES = IMAGE_SUFFIXES | VIDEO_SUFFIXES


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: pathlib.Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def slugify(value: str, fallback: str) -> str:
    value = pathlib.Path(value).stem or value
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value[:80] or fallback


def parse_resource_file(path: pathlib.Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"resource list not found: {path}")
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".json":
        payload = json.loads(text)
        items = payload.get("resources", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            raise SystemExit("JSON resource file must be a list or contain a resources list")
        return [normalize_item(item) for item in items]
    resources = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        resources.append(normalize_item(line))
    return resources


def normalize_item(item: Any) -> dict[str, Any]:
    if isinstance(item, str):
        return {"url": item}
    if isinstance(item, dict) and item.get("url"):
        return dict(item)
    raise SystemExit(f"invalid resource item: {item!r}")


def suffix_from_headers(url: str, content_type: str | None) -> str:
    suffix = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(content_type.split(";", 1)[0].strip())
        if guessed:
            return guessed.lower()
    return ".bin"


def media_type_for(suffix: str) -> str:
    if suffix in AUDIO_SUFFIXES:
        return "audio"
    if suffix in IMAGE_SUFFIXES:
        return "image"
    if suffix in VIDEO_SUFFIXES:
        return "video"
    return "unknown"


def expected_suffixes(kind: str) -> set[str]:
    if kind == "audio":
        return AUDIO_SUFFIXES
    if kind == "visual":
        return VISUAL_SUFFIXES
    raise SystemExit(f"unknown kind: {kind}")


def download(url: str, output_path: pathlib.Path, timeout: int) -> tuple[int, str | None]:
    request = urllib.request.Request(url, headers={"User-Agent": "cucumis-resource-downloader/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        content_type = response.headers.get("Content-Type")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    return output_path.stat().st_size, content_type


def probe_media(path: pathlib.Path) -> dict[str, Any]:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration:stream=codec_type,width,height",
        "-of",
        "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return {}
    if result.returncode != 0:
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return {}
    probe: dict[str, Any] = {}
    duration = data.get("format", {}).get("duration")
    if duration is not None:
        try:
            probe["duration_seconds"] = round(float(duration), 2)
        except ValueError:
            pass
    for stream in data.get("streams", []):
        if "width" in stream and "height" in stream:
            probe["width"] = stream["width"]
            probe["height"] = stream["height"]
            break
    return probe


def asset_manifest_path(project_dir: pathlib.Path) -> pathlib.Path:
    return project_dir / "assets" / "manifest.json"


def merge_asset_manifest(project_dir: pathlib.Path, assets: list[dict[str, Any]]) -> None:
    manifest_path = asset_manifest_path(project_dir)
    manifest = read_json(manifest_path, {"images": [], "subtitles": [], "audio": [], "videos": []})
    for key in ("images", "subtitles", "audio", "videos"):
        manifest.setdefault(key, [])

    existing_ids = {
        str(item.get("asset_id"))
        for bucket in ("images", "audio", "videos")
        for item in manifest.get(bucket, [])
        if isinstance(item, dict)
    }
    for asset in assets:
        media_type = asset["media_type"]
        bucket = "audio" if media_type == "audio" else "videos" if media_type == "video" else "images"
        if asset["asset_id"] in existing_ids:
            continue
        manifest[bucket].append(asset)
        existing_ids.add(asset["asset_id"])
    write_json(manifest_path, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download reusable audio, image, or video resources for a project.")
    parser.add_argument("--project", required=True, help="Project directory path, e.g. projects/demo.")
    parser.add_argument("--kind", choices=["audio", "visual"], required=True)
    parser.add_argument("--resources", required=True, help="JSON or txt file containing resource URLs.")
    parser.add_argument("--output-subdir", default=None, help="Override output subdirectory under the project.")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--update-asset-manifest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    resource_path = pathlib.Path(args.resources).resolve()
    if not project_dir.exists():
        raise SystemExit(f"project not found: {project_dir}")

    resources = parse_resource_file(resource_path)
    suffixes = expected_suffixes(args.kind)
    output_subdir = args.output_subdir or ("audio/downloaded" if args.kind == "audio" else "assets/downloaded")
    output_dir = project_dir / output_subdir
    downloaded: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []

    for index, item in enumerate(resources, start=1):
        url = item["url"]
        base_name = slugify(item.get("title") or urllib.parse.unquote(urllib.parse.urlparse(url).path), f"resource-{index:03d}")
        temp_path = output_dir / f".{base_name}.download"
        last_error = ""
        for attempt in range(args.retries + 1):
            try:
                _, content_type = download(url, temp_path, timeout=args.timeout)
                suffix = suffix_from_headers(url, content_type)
                if suffix not in suffixes:
                    media_type = media_type_for(suffix)
                    raise ValueError(f"unexpected {media_type} suffix {suffix} for kind {args.kind}")
                asset_id = item.get("asset_id") or stable_id(args.kind, url)
                final_path = output_dir / f"{asset_id}-{base_name}{suffix}"
                temp_path.replace(final_path)
                stat = final_path.stat()
                media_type = media_type_for(suffix)
                asset = {
                    "asset_id": asset_id,
                    "media_type": media_type,
                    "path": str(final_path.relative_to(project_dir)),
                    "absolute_path": str(final_path),
                    "source_url": url,
                    "title": item.get("title") or base_name,
                    "tags": item.get("tags", []),
                    "license": item.get("license", ""),
                    "source": item.get("source", ""),
                    "size_bytes": stat.st_size,
                    "downloaded_at": now_iso(),
                    "probe": probe_media(final_path),
                }
                downloaded.append(asset)
                print(f"downloaded {asset_id}: {asset['path']}")
                break
            except (OSError, urllib.error.URLError, ValueError) as exc:
                last_error = str(exc)
                if temp_path.exists():
                    temp_path.unlink()
                if attempt < args.retries:
                    time.sleep(1 + attempt)
        else:
            failures.append({"url": url, "error": last_error})
            print(f"failed: {url} ({last_error})", file=sys.stderr)

    manifest_name = "downloaded-audio-manifest.json" if args.kind == "audio" else "downloaded-visual-manifest.json"
    manifest_path = project_dir / "assets" / manifest_name
    manifest = {
        "version": 1,
        "generated_at": now_iso(),
        "kind": args.kind,
        "resource_file": str(resource_path),
        "output_subdir": output_subdir,
        "summary": {
            "requested": len(resources),
            "downloaded": len(downloaded),
            "failed": len(failures),
        },
        "assets": downloaded,
        "failures": failures,
    }
    write_json(manifest_path, manifest)

    if args.update_asset_manifest:
        merge_asset_manifest(project_dir, downloaded)

    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
