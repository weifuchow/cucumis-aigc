#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Any


AUDIO_SUFFIXES = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


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


def pixabay_music_id(source_url: str) -> str | None:
    match = re.search(r"-(\d+)/?$", source_url)
    return match.group(1) if match else None


def slugify(value: str, fallback: str) -> str:
    value = pathlib.Path(value).stem or value
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value[:100] or fallback


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
    return probe


def normalize_tracks(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        tracks = payload
    elif isinstance(payload, dict):
        tracks = payload.get("audio") or payload.get("tracks") or payload.get("resources") or []
    else:
        tracks = []
    if not isinstance(tracks, list):
        raise SystemExit("tracks file must be a list or contain audio/tracks/resources list")
    normalized = []
    for item in tracks:
        if not isinstance(item, dict):
            raise SystemExit(f"invalid track item: {item!r}")
        normalized.append(dict(item))
    return normalized


def source_path_for(track: dict[str, Any], downloads_dir: pathlib.Path) -> pathlib.Path:
    explicit = track.get("local_path") or track.get("source_path")
    if explicit:
        path = pathlib.Path(str(explicit)).expanduser()
        return path if path.is_absolute() else path.resolve()
    filename = track.get("filename") or track.get("downloaded_filename")
    if not filename:
        raise SystemExit(f"track is missing filename/local_path: {track!r}")
    return downloads_dir / str(filename)


def asset_id_for(track: dict[str, Any], source_path: pathlib.Path) -> str:
    if track.get("asset_id"):
        return str(track["asset_id"])
    provider = str(track.get("provider") or "browser-audio").lower().replace("_", "-")
    source_url = str(track.get("source_url") or "")
    if provider == "pixabay" or "pixabay.com/music" in source_url:
        music_id = pixabay_music_id(source_url)
        if music_id:
            return f"pixabay-music-{music_id}"
    seed = source_url or str(source_path)
    return stable_id(provider, seed)


def merge_asset_manifest(project_dir: pathlib.Path, assets: list[dict[str, Any]]) -> None:
    manifest_path = project_dir / "assets" / "manifest.json"
    manifest = read_json(manifest_path, {"images": [], "subtitles": [], "audio": [], "videos": []})
    for key in ("images", "subtitles", "audio", "videos"):
        manifest.setdefault(key, [])
    existing = {
        str(item.get("asset_id")): index
        for index, item in enumerate(manifest.get("audio", []))
        if isinstance(item, dict)
    }
    for asset in assets:
        if asset["asset_id"] in existing:
            manifest["audio"][existing[asset["asset_id"]]] = asset
        else:
            manifest["audio"].append(asset)
    write_json(manifest_path, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import browser-downloaded audio files into a project audio library.")
    parser.add_argument("--project", required=True, help="Project directory path, e.g. projects/demo.")
    parser.add_argument("--tracks", required=True, help="JSON file with downloaded filenames and source metadata.")
    parser.add_argument("--downloads-dir", default="~/Downloads", help="Browser downloads directory.")
    parser.add_argument("--output-subdir", default="audio/downloaded", help="Output subdirectory under the project.")
    parser.add_argument("--update-asset-manifest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = pathlib.Path(args.project).resolve()
    tracks_path = pathlib.Path(args.tracks).resolve()
    downloads_dir = pathlib.Path(args.downloads_dir).expanduser()
    output_dir = project_dir / args.output_subdir
    if not project_dir.exists():
        raise SystemExit(f"project not found: {project_dir}")
    tracks = normalize_tracks(read_json(tracks_path, []))
    imported: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    stamp = now_iso()
    output_dir.mkdir(parents=True, exist_ok=True)

    for index, track in enumerate(tracks, start=1):
        try:
            source_path = source_path_for(track, downloads_dir)
            if not source_path.is_file():
                raise FileNotFoundError(str(source_path))
            suffix = source_path.suffix.lower()
            if suffix not in AUDIO_SUFFIXES:
                raise ValueError(f"unsupported audio suffix: {suffix}")
            asset_id = asset_id_for(track, source_path)
            base = slugify(track.get("title") or source_path.name, f"browser-audio-{index:03d}")
            final_path = output_dir / f"{asset_id}-{base}{suffix}"
            if source_path.resolve() != final_path.resolve():
                shutil.copy2(source_path, final_path)
            stat = final_path.stat()
            probe = probe_media(final_path)
            asset = {
                "asset_id": asset_id,
                "media_type": "audio",
                "role": track.get("role", "bgm"),
                "path": str(final_path.relative_to(project_dir)),
                "absolute_path": str(final_path),
                "source_url": track.get("source_url", ""),
                "download_url": track.get("download_url"),
                "provider": track.get("provider", "browser"),
                "source": track.get("source", "Browser download"),
                "title": track.get("title") or source_path.stem,
                "author": track.get("author", ""),
                "license": track.get("license", ""),
                "query": track.get("query", ""),
                "use_case": track.get("use_case", ""),
                "mood": track.get("mood", []),
                "tags": track.get("tags", []),
                "downloaded_via": "browser",
                "original_download_path": str(source_path),
                "size_bytes": stat.st_size,
                "downloaded_at": track.get("downloaded_at") or stamp,
                "probe": probe,
            }
            if track.get("duration_seconds") is not None:
                asset["duration_seconds"] = track["duration_seconds"]
            elif probe.get("duration_seconds") is not None:
                asset["duration_seconds"] = probe["duration_seconds"]
            imported.append(asset)
            print(f"imported {asset_id}: {asset['path']}")
        except (OSError, ValueError) as exc:
            failures.append({"title": str(track.get("title", "")), "error": str(exc)})
            print(f"failed: {track.get('title') or track} ({exc})")

    manifest = {
        "version": 1,
        "generated_at": stamp,
        "kind": "audio",
        "source": "browser downloads",
        "tracks_file": str(tracks_path),
        "output_subdir": args.output_subdir,
        "summary": {
            "requested": len(tracks),
            "imported": len(imported),
            "failed": len(failures),
        },
        "audio": imported,
        "assets": imported,
        "failures": failures,
    }
    write_json(project_dir / "assets" / "downloaded-audio-manifest.json", manifest)
    if args.update_asset_manifest and imported:
        merge_asset_manifest(project_dir, imported)
    return 2 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
