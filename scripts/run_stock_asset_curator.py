#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import pathlib
import re
import shutil
import subprocess
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError
from datetime import datetime, timezone
from typing import Any


USER_AGENT = "cucumis-stock-asset-curator/1.0"


def load_env_file(path: pathlib.Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        value = value.strip().strip('"').strip("'")
        os.environ[key] = value


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
    return f"{prefix}-{hashlib.sha1(value.encode('utf-8')).hexdigest()[:12]}"


def slugify(value: str, fallback: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-._")
    return value[:80] or fallback


def request_json(url: str, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    with urllib.request.urlopen(request, timeout=45) as response:
        return json.loads(response.read().decode("utf-8"))


def api_query(value: str, limit: int | None = None) -> str:
    value = " ".join(value.split())
    if limit and len(value) > limit:
        return value[:limit].rsplit(" ", 1)[0] or value[:limit]
    return value


def download_file(url: str, path: pathlib.Path) -> tuple[int, str]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=90) as response:
        content_type = response.headers.get("Content-Type", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as fh:
            shutil.copyfileobj(response, fh)
    return path.stat().st_size, content_type


def suffix_for(url: str, content_type: str, fallback: str) -> str:
    suffix = pathlib.Path(urllib.parse.urlparse(url).path).suffix.lower()
    if suffix:
        return suffix.split("?", 1)[0]
    guessed = mimetypes.guess_extension(content_type.split(";", 1)[0]) if content_type else None
    return guessed or fallback


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


def merge_asset_manifest(project_dir: pathlib.Path, assets: list[dict[str, Any]]) -> None:
    manifest_path = project_dir / "assets" / "manifest.json"
    manifest = read_json(manifest_path, {"images": [], "subtitles": [], "audio": [], "videos": []})
    for key in ("images", "subtitles", "audio", "videos"):
        manifest.setdefault(key, [])
    existing = {
        str(item.get("asset_id"))
        for bucket in ("images", "audio", "videos")
        for item in manifest.get(bucket, [])
        if isinstance(item, dict)
    }
    for asset in assets:
        bucket = "audio" if asset["media_type"] == "audio" else "videos" if asset["media_type"] == "video" else "images"
        if asset["asset_id"] not in existing:
            manifest[bucket].append(asset)
            existing.add(asset["asset_id"])
    write_json(manifest_path, manifest)


def load_queries(path: pathlib.Path) -> dict[str, Any]:
    payload = read_json(path, None)
    if not isinstance(payload, dict):
        raise SystemExit("request file must be a JSON object")
    queries = payload.get("queries")
    if not isinstance(queries, list) or not queries:
        raise SystemExit("request file must contain a non-empty queries list")
    return payload


def query_text(item: dict[str, Any], defaults: dict[str, Any]) -> str:
    terms = []
    for key in ("scene", "query", "keywords", "mood", "style"):
        value = item.get(key) or defaults.get(key)
        if isinstance(value, list):
            terms.extend(str(part) for part in value)
        elif value:
            terms.append(str(value))
    return " ".join(terms).strip()


def media_query_text(item: dict[str, Any], defaults: dict[str, Any], media_type: str) -> str:
    if media_type == "audio":
        terms = []
        for key in ("audio_query", "sound", "scene", "query", "keywords", "mood"):
            value = item.get(key) or defaults.get(key)
            if isinstance(value, list):
                terms.extend(str(part) for part in value)
            elif value:
                terms.append(str(value))
        return api_query(" ".join(terms), 80)
    return query_text(item, defaults)


def orientation_for(provider: str, defaults: dict[str, Any], item: dict[str, Any]) -> str:
    orientation = str(item.get("orientation") or defaults.get("orientation") or "").lower()
    aspect_ratio = str(item.get("aspect_ratio") or defaults.get("aspect_ratio") or "").lower()
    if not orientation and aspect_ratio:
        if aspect_ratio in {"9:16", "3:4", "vertical", "portrait"}:
            orientation = "portrait"
        elif aspect_ratio in {"1:1", "square"}:
            orientation = "square"
        else:
            orientation = "landscape"
    if provider == "pixabay":
        return "vertical" if orientation == "portrait" else "horizontal"
    return orientation if orientation in {"landscape", "portrait", "square"} else "landscape"


def min_dimensions(defaults: dict[str, Any], item: dict[str, Any]) -> tuple[int | None, int | None]:
    size = item.get("target_size") or defaults.get("target_size") or {}
    if not isinstance(size, dict):
        return None, None
    width = size.get("width") or size.get("min_width")
    height = size.get("height") or size.get("min_height")
    try:
        return int(width) if width else None, int(height) if height else None
    except (TypeError, ValueError):
        return None, None


def search_pexels(query: str, media_type: str, per_page: int, orientation: str) -> list[dict[str, Any]]:
    key = os.getenv("PEXELS_API_KEY")
    if not key or media_type not in {"image", "video"}:
        return []
    endpoint = "https://api.pexels.com/v1/search" if media_type == "image" else "https://api.pexels.com/v1/videos/search"
    url = f"{endpoint}?{urllib.parse.urlencode({'query': query, 'per_page': per_page, 'orientation': orientation})}"
    data = request_json(url, {"Authorization": key})
    items = data.get("photos", []) if media_type == "image" else data.get("videos", [])
    results = []
    for item in items:
        if media_type == "image":
            download_url = item.get("src", {}).get("large2x") or item.get("src", {}).get("original")
            width = item.get("width")
            height = item.get("height")
            title = item.get("alt") or f"pexels-photo-{item.get('id')}"
        else:
            files = sorted(item.get("video_files", []), key=lambda file: file.get("width", 0), reverse=True)
            download_url = next((file.get("link") for file in files if file.get("file_type") == "video/mp4"), None)
            width = item.get("width")
            height = item.get("height")
            title = f"pexels-video-{item.get('id')}"
        if not download_url:
            continue
        results.append(
            {
                "provider": "pexels",
                "media_type": media_type,
                "title": title,
                "download_url": download_url,
                "source_url": item.get("url", ""),
                "author": item.get("photographer") or item.get("user", {}).get("name", ""),
                "license": "Pexels License",
                "width": width,
                "height": height,
            }
        )
    return results


def search_pixabay(
    query: str,
    media_type: str,
    per_page: int,
    orientation: str,
    min_width: int | None,
    min_height: int | None,
) -> list[dict[str, Any]]:
    key = os.getenv("PIXABAY_API_KEY")
    if not key or media_type not in {"image", "video"}:
        return []
    endpoint = "https://pixabay.com/api/" if media_type == "image" else "https://pixabay.com/api/videos/"
    params: dict[str, Any] = {
        "key": key,
        "q": api_query(query, 100),
        "per_page": per_page,
        "safesearch": "true",
        "orientation": orientation,
    }
    if min_width:
        params["min_width"] = min_width
    if min_height:
        params["min_height"] = min_height
    data = request_json(f"{endpoint}?{urllib.parse.urlencode(params)}")
    results = []
    for item in data.get("hits", []):
        if media_type == "image":
            download_url = item.get("largeImageURL") or item.get("webformatURL")
            width = item.get("imageWidth")
            height = item.get("imageHeight")
        else:
            videos = item.get("videos", {})
            selected = videos.get("large") or videos.get("medium") or videos.get("small")
            download_url = selected.get("url") if selected else None
            width = selected.get("width") if selected else None
            height = selected.get("height") if selected else None
        if not download_url:
            continue
        results.append(
            {
                "provider": "pixabay",
                "media_type": media_type,
                "title": f"pixabay-{media_type}-{item.get('id')}",
                "download_url": download_url,
                "source_url": item.get("pageURL", ""),
                "author": item.get("user", ""),
                "license": "Pixabay Content License",
                "width": width,
                "height": height,
                "tags": [tag.strip() for tag in str(item.get("tags", "")).split(",") if tag.strip()],
            }
        )
    return results


def search_freesound(query: str, per_page: int) -> list[dict[str, Any]]:
    key = os.getenv("FREESOUND_API_KEY")
    if not key:
        return []
    params = {
        "query": query,
        "page_size": per_page,
        "fields": "id,name,url,username,license,tags,duration,previews",
    }
    url = f"https://freesound.org/apiv2/search/text/?{urllib.parse.urlencode(params)}"
    data = request_json(url, {"Authorization": f"Token {key}"})
    results = []
    for item in data.get("results", []):
        previews = item.get("previews", {})
        download_url = previews.get("preview-hq-mp3") or previews.get("preview-lq-mp3")
        if not download_url:
            continue
        results.append(
            {
                "provider": "freesound",
                "media_type": "audio",
                "title": item.get("name") or f"freesound-{item.get('id')}",
                "download_url": download_url,
                "source_url": item.get("url", ""),
                "author": item.get("username", ""),
                "license": item.get("license", ""),
                "duration_seconds": item.get("duration"),
                "tags": item.get("tags", []),
            }
        )
    return results


def fallback_search_urls(query: str, media_types: list[str]) -> list[dict[str, str]]:
    encoded = urllib.parse.quote_plus(query)
    urls = []
    if any(kind in media_types for kind in ("image", "video")):
        urls.extend(
            [
                {"source": "Pexels", "url": f"https://www.pexels.com/search/{encoded}/"},
                {"source": "Pixabay", "url": f"https://pixabay.com/images/search/{encoded}/"},
                {"source": "Mixkit video", "url": f"https://mixkit.co/free-stock-video/{encoded}/"},
            ]
        )
    if "audio" in media_types:
        urls.extend(
            [
                {"source": "Pixabay music", "url": f"https://pixabay.com/music/search/{encoded}/"},
                {"source": "Pixabay sound effects", "url": f"https://pixabay.com/sound-effects/search/{encoded}/"},
                {"source": "Freesound", "url": f"https://freesound.org/search/?q={encoded}"},
                {"source": "Mixkit music", "url": f"https://mixkit.co/free-stock-music/{encoded}/"},
            ]
        )
    return urls


def collect_candidates(
    query: str,
    media_type: str,
    providers: list[str],
    per_provider: int,
    defaults: dict[str, Any],
    query_item: dict[str, Any],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    min_width, min_height = min_dimensions(defaults, query_item)
    if "pexels" in providers:
        try:
            candidates.extend(search_pexels(query, media_type, per_provider, orientation_for("pexels", defaults, query_item)))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            candidates.append(provider_failure("pexels", media_type, exc))
    if "pixabay" in providers:
        try:
            candidates.extend(
                search_pixabay(
                    query,
                    media_type,
                    per_provider,
                    orientation_for("pixabay", defaults, query_item),
                    min_width,
                    min_height,
                )
            )
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            candidates.append(provider_failure("pixabay", media_type, exc))
    if "freesound" in providers and media_type == "audio":
        try:
            candidates.extend(search_freesound(query, per_provider))
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            candidates.append(provider_failure("freesound", media_type, exc))
    return candidates


def provider_failure(provider: str, media_type: str, exc: Exception) -> dict[str, Any]:
    error = str(exc)
    if isinstance(exc, HTTPError):
        error = f"HTTP {exc.code}: {exc.reason}"
    return {
        "provider": provider,
        "media_type": media_type,
        "error": error,
        "candidate_error": True,
    }


def save_candidate(project_dir: pathlib.Path, candidate: dict[str, Any], query: str, index: int) -> dict[str, Any]:
    media_type = candidate["media_type"]
    provider = candidate["provider"]
    base = slugify(candidate.get("title") or query, f"asset-{index:03d}")
    asset_id = stable_id(provider, f"{candidate['download_url']}|{query}")
    subdir = "audio/curated" if media_type == "audio" else "assets/curated/videos" if media_type == "video" else "assets/curated/images"
    temp_path = project_dir / subdir / f".{asset_id}.download"
    size_bytes, content_type = download_file(candidate["download_url"], temp_path)
    suffix = suffix_for(candidate["download_url"], content_type, ".mp3" if media_type == "audio" else ".mp4" if media_type == "video" else ".jpg")
    final_path = project_dir / subdir / f"{asset_id}-{base}{suffix}"
    temp_path.replace(final_path)
    asset = {
        "asset_id": asset_id,
        "media_type": media_type,
        "path": str(final_path.relative_to(project_dir)),
        "absolute_path": str(final_path),
        "source_url": candidate.get("source_url", ""),
        "download_url": candidate.get("download_url", ""),
        "provider": provider,
        "title": candidate.get("title", base),
        "query": query,
        "author": candidate.get("author", ""),
        "license": candidate.get("license", ""),
        "tags": candidate.get("tags", []),
        "size_bytes": size_bytes,
        "downloaded_at": now_iso(),
        "probe": probe_media(final_path),
    }
    for key in ("width", "height", "duration_seconds"):
        if candidate.get(key) is not None:
            asset[key] = candidate[key]
    return asset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Search and download matching stock assets for a video project.")
    parser.add_argument("--project", required=True, help="Project directory path.")
    parser.add_argument("--request", required=True, help="JSON request with topic and queries.")
    parser.add_argument("--env-file", default=".env", help="Env file to load API keys from before reading the process environment.")
    parser.add_argument("--providers", default="pexels,pixabay,freesound", help="Comma-separated provider list.")
    parser.add_argument("--per-query", type=int, default=2, help="Assets to download per query/media type.")
    parser.add_argument("--per-provider", type=int, default=6, help="Candidates to fetch per provider.")
    parser.add_argument("--dry-run", action="store_true", help="Only write candidate/search manifest; do not download.")
    parser.add_argument("--update-asset-manifest", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    env_path = pathlib.Path(args.env_file)
    if not env_path.is_absolute():
        env_path = pathlib.Path.cwd() / env_path
    load_env_file(env_path)
    project_dir = pathlib.Path(args.project).resolve()
    request_path = pathlib.Path(args.request).resolve()
    if not project_dir.exists():
        raise SystemExit(f"project not found: {project_dir}")
    request = load_queries(request_path)
    defaults = {key: value for key, value in request.items() if key != "queries"}
    providers = [provider.strip().lower() for provider in args.providers.split(",") if provider.strip()]

    query_reports = []
    downloaded_assets = []
    for query_item in request["queries"]:
        if not isinstance(query_item, dict):
            raise SystemExit("each query item must be an object")
        query = query_text(query_item, defaults)
        if not query:
            continue
        media_types = query_item.get("media_types") or query_item.get("types") or ["image", "video", "audio"]
        if isinstance(media_types, str):
            media_types = [media_types]
        report = {
            "scene_id": query_item.get("scene_id"),
            "scene": query_item.get("scene"),
            "query": query,
            "media_types": media_types,
            "style": query_item.get("style") or defaults.get("style"),
            "aspect_ratio": query_item.get("aspect_ratio") or defaults.get("aspect_ratio"),
            "target_size": query_item.get("target_size") or defaults.get("target_size"),
            "candidates": [],
            "downloaded_asset_ids": [],
        }
        for media_type in media_types:
            media_query = media_query_text(query_item, defaults, media_type)
            candidates = collect_candidates(media_query, media_type, providers, max(args.per_provider, args.per_query), defaults, query_item)
            report["candidates"].extend(candidates)
            downloadable = [candidate for candidate in candidates if not candidate.get("candidate_error")]
            for candidate in downloadable[: max(args.per_query, 0)]:
                if args.dry_run:
                    continue
                try:
                    asset = save_candidate(project_dir, candidate, media_query, len(downloaded_assets) + 1)
                    downloaded_assets.append(asset)
                    report["downloaded_asset_ids"].append(asset["asset_id"])
                    print(f"downloaded {asset['asset_id']}: {asset['path']}")
                except OSError as exc:
                    report.setdefault("failures", []).append({"candidate": candidate, "error": str(exc)})
        if not report["candidates"]:
            report["manual_search_urls"] = fallback_search_urls(query, media_types)
        query_reports.append(report)

    manifest = {
        "version": 1,
        "generated_at": now_iso(),
        "request_file": str(request_path),
        "providers": providers,
        "dry_run": args.dry_run,
        "summary": {
            "queries": len(query_reports),
            "downloaded": len(downloaded_assets),
        },
        "assets": downloaded_assets,
        "queries": query_reports,
    }
    write_json(project_dir / "assets" / "stock-curation-manifest.json", manifest)
    if args.update_asset_manifest and downloaded_assets:
        merge_asset_manifest(project_dir, downloaded_assets)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
