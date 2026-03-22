"""Direct API calls to service.vidu.cn via the browser's authenticated session.

Instead of scraping the DOM, we piggyback on the browser's cookie authentication
to call the same internal API the web UI uses.  The browser handles all auth
transparently — no API keys needed.

Verified API endpoints (captured from live network traffic 2026-03-21):
  POST  service.vidu.cn/vidu/v1/tasks                    → create task, returns {id, state, ...}
  GET   service.vidu.cn/vidu/v1/tasks/{id}               → full task result
  GET   service.vidu.cn/vidu/v1/tasks/state?id={id}      → lightweight state check
  POST  service.vidu.cn/tools/v1/files/uploads            → get presigned PUT URL (body must include scene:"vidu")
  PUT   put.vidu.cn/<path>?<presigned>                   → upload file bytes (no auth, presigned)
  PUT   service.vidu.cn/tools/v1/files/uploads/{id}/finish → commit upload, returns ssupload URI

Task states: created → queueing → preparation → scheduling → processing → success | failed

Image upload flow (for character2video / img2video):
  1. upload_image(page, path) → "ssupload:?id=<upload_id>"
  2. pass URI as {type:"image", content:"ssupload:?id=..."} in prompts
"""
from __future__ import annotations

import json
import time
import uuid
import urllib.request
from pathlib import Path
from typing import Any

_API_BASE = "https://service.vidu.cn"
_TASKS_URL = f"{_API_BASE}/vidu/v1/tasks"
_UPLOADS_URL = f"{_API_BASE}/tools/v1/files/uploads"


# ------------------------------------------------------------------
# Core
# ------------------------------------------------------------------

def create_task(
    page,
    task_type: str,
    prompt_text: str,
    settings: dict[str, Any],
    ref_image_uris: list[str] | None = None,
) -> str:
    """POST /vidu/v1/tasks — returns task_id string.

    ``settings`` keys (all optional, Vidu picks defaults):
      model_version, resolution, aspect_ratio, duration,
      sample_count, schedule_mode, codec, use_trial

    ``ref_image_uris``: list of "ssupload:?id=..." URIs from upload_image().
      Required for character2video; ignored for text2image / text2video.
    """
    prompts: list[dict[str, Any]] = [
        {
            "type": "text",
            "content": prompt_text,
            "negative": False,
            "enhance": True,
        }
    ]
    for i, uri in enumerate(ref_image_uris or []):
        prompts.append({
            "type": "image",
            "content": uri,
            "src_imgs": [],
            "selected_region": None,
            "name": f"图{i + 1}",
            "negative": False,
        })

    body = {
        "type": task_type,
        "input": {
            "prompts": prompts,
            "editor_mode": "normal",
            "enhance": True,
        },
        "settings": {
            "resolution": settings.get("resolution", "1080p"),
            "model_version": settings.get("model_version", "3.1"),
            "sample_count": settings.get("sample_count", 1),
            "schedule_mode": settings.get("schedule_mode", "normal"),
            "codec": settings.get("codec", "h265"),
            "movement_amplitude": settings.get("movement_amplitude", "auto"),
            "duration": settings.get("duration", 0),
            "aspect_ratio": settings.get("aspect_ratio", ""),
            "use_trial": settings.get("use_trial", True),
        },
    }

    # Use parametrized evaluate to avoid f-string / JSON double-encoding issues
    req_headers = {
        "Content-Type": "application/json",
        "x-platform": "web",
        "x-request-id": str(uuid.uuid4()),
        "x-app-version": "-",
    }
    result = page.evaluate(
        """async ([url, headers, body]) => {
            const r = await fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: headers,
                body: JSON.stringify(body)
            });
            return r.json();
        }""",
        [_TASKS_URL, req_headers, body],
    )

    task_id = result.get("id") or result.get("data", {}).get("id")
    if not task_id:
        raise RuntimeError(f"Task creation failed — response: {result}")
    return str(task_id)


def poll_task(
    page,
    task_id: str,
    poll_interval: float = 5.0,
    max_wait: float = 300.0,
) -> dict[str, Any]:
    """Poll GET /vidu/v1/tasks/{id} until state is 'success' or 'failed'.

    Returns the full task dict on success.
    Raises RuntimeError on failure, TimeoutError on timeout.
    """
    url = f"{_TASKS_URL}/{task_id}"
    deadline = time.monotonic() + max_wait

    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        result: dict = page.evaluate(
            f"() => fetch('{url}', {{credentials: 'include'}}).then(r => r.json())"
        )
        state = result.get("state", "unknown")
        print(f"[vidu_web]   task {task_id} → {state}", flush=True)

        if state == "success":
            return result
        if state in ("failed", "error"):
            err = result.get("err_code") or result.get("err_info", {}).get("err_msg", "")
            raise RuntimeError(f"Task {task_id} failed: {err}")

    raise TimeoutError(f"Task {task_id} timed out after {max_wait}s")


# ------------------------------------------------------------------
# Result extraction
# ------------------------------------------------------------------

def extract_media_url(task_result: dict[str, Any]) -> str:
    """Return the best media URL from a completed task result.

    Prefers download_uri (no watermark) over uri (watermarked).
    """
    creations = task_result.get("creations", [])
    if not creations:
        return ""
    c = creations[0]
    # nomark_uri = download_uri for images; download_uri for videos
    return (
        c.get("download_uri")
        or c.get("nomark_uri")
        or c.get("uri")
        or ""
    )


def extract_cover_url(task_result: dict[str, Any]) -> str:
    creations = task_result.get("creations", [])
    return creations[0].get("cover_uri", "") if creations else ""


# ------------------------------------------------------------------
# Image upload (for character2video / img2video)
# ------------------------------------------------------------------

def upload_image(page, image_path: Path) -> str:
    """Upload a local image to Vidu storage and return its ssupload URI.

    Three-step flow (verified from live network capture 2026-03-21):
      1. POST /tools/v1/files/uploads  (browser + cookies) → {id, put_url}
      2. PUT  put_url  (presigned CloudFront, no auth needed) → 200 OK
      3. PUT  /tools/v1/files/uploads/{id}/finish  (browser + cookies)
         → {uri: "ssupload:?id=<id>"}

    Returns: "ssupload:?id=<upload_id>"

    Note: character2video requires a full-resolution face image. Low-quality
    or heavily compressed thumbnails may cause task creation to fail (400).
    """
    import mimetypes, struct
    content_type = mimetypes.guess_type(str(image_path))[0] or "image/jpeg"

    # Read image dimensions — needed by character2video upload endpoint.
    # UI sends {"metadata": {"image-height": "H", "image-width": "W"}, "scene": "vidu"}
    # PNG: width at bytes 16-19, height at 20-23 (IHDR chunk)
    img_w, img_h = 0, 0
    with open(image_path, "rb") as _f:
        header = _f.read(24)
    if header[:4] == b"\x89PNG":
        img_w, img_h = struct.unpack(">II", header[16:24])

    # Step 1 — request presigned upload URL (match UI format exactly)
    upload_info: dict = page.evaluate(
        """async ([url, body]) => {
            const r = await fetch(url, {
                method: 'POST',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            return r.json();
        }""",
        [_UPLOADS_URL, {"metadata": {"image-height": str(img_h), "image-width": str(img_w)}, "scene": "vidu"}],
    )

    upload_id = upload_info.get("id")
    put_url = upload_info.get("put_url")
    if not upload_id or not put_url:
        raise RuntimeError(f"upload_image: failed to get upload URL — {upload_info}")

    print(f"[vidu_web]   upload_id={upload_id}, PUT {put_url[:60]}…", flush=True)

    # Step 2 — PUT file bytes to presigned URL (no auth needed)
    # x-amz-meta-image-* headers are required; ETag from response is needed for finish
    with open(image_path, "rb") as f:
        data = f.read()
    req = urllib.request.Request(put_url, data=data, method="PUT")
    req.add_header("Content-Type", content_type)
    req.add_header("x-amz-meta-image-height", str(img_h))
    req.add_header("x-amz-meta-image-width", str(img_w))
    with urllib.request.urlopen(req, timeout=120) as resp:
        etag = resp.headers.get("ETag", "").strip('"')

    # Step 3 — commit upload; finish body must include etag + id (verified 2026-03-22)
    finish_url = f"{_UPLOADS_URL}/{upload_id}/finish"
    finish_result: dict = page.evaluate(
        """async ([url, body]) => {
            const r = await fetch(url, {
                method: 'PUT',
                credentials: 'include',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
            return r.json();
        }""",
        [finish_url, {"etag": etag, "id": upload_id}],
    )

    uri = finish_result.get("uri") or f"ssupload:?id={upload_id}"
    print(f"[vidu_web]   upload done → {uri}", flush=True)
    return uri


# ------------------------------------------------------------------
# Download
# ------------------------------------------------------------------

def download_media(url: str, dest: Path) -> Path:
    """Download *url* to *dest*, creating parent dirs as needed.

    Returns *dest* on success, raises on error.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
        f.write(resp.read())
    return dest
