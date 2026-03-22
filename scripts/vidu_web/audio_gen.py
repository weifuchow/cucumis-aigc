"""Audio (TTS + BGM) generation automation for Vidu web.

Drives Vidu's audio creation pages and intercepts the internal API calls
to capture task IDs and result URLs — same pattern as video_gen.py.

Note: If Vidu's consumer web UI does not expose TTS/BGM generation,
these functions raise ``NotImplementedError``. The ViduWebProvider will
surface this cleanly so callers can fall back to another provider.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from .interceptor import ResponseCapture

VIDU_ORIGIN = "https://www.vidu.cn"
PAGE_AUDIO = f"{VIDU_ORIGIN}/create/audio"  # adjust if URL differs
PAGE_BGM = f"{VIDU_ORIGIN}/create/bgm"  # adjust if URL differs

_API_PATTERN = "https://service.vidu.cn/vidu/v1/tasks*"

_SEL = {
    "text_input": "textarea, .text-input textarea",
    "generate_btn": "button:has-text('生成'), button:has-text('Generate'), button[type='submit']",
    "result_audio": "audio[src], [data-testid='result-audio']",
    "result_download": "a[download][href*='audio'], a[href*='.mp3'], a[href*='.wav']",
}

_TASK_ID_PATHS: list[list[str]] = [
    ["id"],           # top-level id (verified from live capture)
    ["data", "id"],
    ["result", "id"],
]


def generate_tts(
    session,
    text: str,
    voice_id: str = "",
    duration_seconds: int = 0,
    poll_interval: float = 5.0,
    poll_max_wait: float = 120.0,
    **opts: Any,
) -> dict[str, Any]:
    """Generate TTS audio via Vidu web UI.

    Returns unified provider audio response.
    """
    _assert_audio_page_available(session)

    page = session.page
    print(f"[vidu_web] Generating TTS ({len(text)} chars) …", flush=True)

    page.goto(PAGE_AUDIO)
    page.wait_for_load_state("networkidle", timeout=30_000)

    with ResponseCapture(page, url_pattern=_API_PATTERN) as capture:
        _fill_text(page, _SEL["text_input"], text)
        _click(page, _SEL["generate_btn"])
        task_id = _wait_for_task_id(capture, timeout=30.0)

    audio_url = ""
    if task_id:
        print(f"[vidu_web]   TTS task_id={task_id}, polling …", flush=True)
        audio_url = _poll_for_audio(page, task_id, poll_interval, poll_max_wait) or ""
    else:
        audio_url = _dom_poll_for_audio(page, poll_interval, poll_max_wait) or ""

    return {
        "mode": "live",
        "model": "tts",
        "request_id": str(uuid.uuid4()),
        "audio_url": audio_url,
        "segments": [],  # segment timing not available from web UI
        "usage": {"credits": 0},
        "raw_response": {},
    }


def generate_bgm(
    session,
    prompt: str,
    duration_seconds: int,
    poll_interval: float = 5.0,
    poll_max_wait: float = 120.0,
    **opts: Any,
) -> dict[str, Any]:
    """Generate background music via Vidu web UI."""
    _assert_bgm_page_available(session)

    page = session.page
    print(f"[vidu_web] Generating BGM ({duration_seconds}s) …", flush=True)

    page.goto(PAGE_BGM)
    page.wait_for_load_state("networkidle", timeout=30_000)

    with ResponseCapture(page, url_pattern=_API_PATTERN) as capture:
        _fill_text(page, _SEL["text_input"], prompt)
        _click(page, _SEL["generate_btn"])
        task_id = _wait_for_task_id(capture, timeout=30.0)

    audio_url = ""
    if task_id:
        print(f"[vidu_web]   BGM task_id={task_id}, polling …", flush=True)
        audio_url = _poll_for_audio(page, task_id, poll_interval, poll_max_wait) or ""
    else:
        audio_url = _dom_poll_for_audio(page, poll_interval, poll_max_wait) or ""

    return {
        "mode": "live",
        "model": "bgm",
        "request_id": str(uuid.uuid4()),
        "audio_url": audio_url,
        "duration_seconds": duration_seconds,
        "usage": {"credits": 0},
        "raw_response": {},
    }


# ------------------------------------------------------------------
# Shared helpers
# ------------------------------------------------------------------

def _assert_audio_page_available(session) -> None:
    """Raise if Vidu's web UI doesn't have a TTS creation page."""
    # We attempt a HEAD request to check existence
    page = session.page
    try:
        resp = page.request.head(PAGE_AUDIO, timeout=5_000)
        if resp.status == 404:
            raise NotImplementedError(
                f"Vidu consumer web UI does not expose a TTS page at {PAGE_AUDIO}. "
                "Audio generation is not available via ViduWebProvider. "
                "Use MEDIA_PROVIDER=vidu (API) or MEDIA_PROVIDER=poe instead."
            )
    except NotImplementedError:
        raise
    except Exception:
        pass  # network errors are non-fatal here; will surface during actual generation


def _assert_bgm_page_available(session) -> None:
    page = session.page
    try:
        resp = page.request.head(PAGE_BGM, timeout=5_000)
        if resp.status == 404:
            raise NotImplementedError(
                f"Vidu consumer web UI does not expose a BGM page at {PAGE_BGM}. "
                "BGM generation is not available via ViduWebProvider."
            )
    except NotImplementedError:
        raise
    except Exception:
        pass


def _fill_text(page, selector: str, text: str) -> None:
    try:
        el = page.wait_for_selector(selector, timeout=10_000)
        el.click()
        el.fill(text)
    except Exception as exc:
        print(f"[vidu_web]   Warning: fill failed: {exc}", flush=True)


def _click(page, selector: str) -> None:
    try:
        btn = page.wait_for_selector(selector, timeout=10_000)
        btn.click()
    except Exception as exc:
        print(f"[vidu_web]   Warning: click failed: {exc}", flush=True)


def _wait_for_task_id(capture: ResponseCapture, timeout: float) -> str | None:
    resp = capture.wait_for(lambda b: _extract_task_id(b) is not None, timeout=timeout)
    return _extract_task_id(resp["body"]) if resp else None


def _extract_task_id(body: dict) -> str | None:
    for path in _TASK_ID_PATHS:
        val = body
        for key in path:
            if not isinstance(val, dict):
                val = None
                break
            val = val.get(key)
        if val and isinstance(val, str):
            return val
    return None


def _poll_for_audio(page, task_id: str, poll_interval: float, max_wait: float) -> str | None:
    deadline = time.monotonic() + max_wait
    with ResponseCapture(page, url_pattern=_API_PATTERN) as capture:
        while time.monotonic() < deadline:
            time.sleep(poll_interval)
            for body in capture.all_bodies():
                url = _find_audio_url(body, task_id)
                if url:
                    return url
            capture.clear()
    return None


def _dom_poll_for_audio(page, poll_interval: float, max_wait: float) -> str | None:
    deadline = time.monotonic() + max_wait
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        try:
            el = page.query_selector(_SEL["result_audio"])
            if el:
                src = el.get_attribute("src") or ""
                if src:
                    return src
            el = page.query_selector(_SEL["result_download"])
            if el:
                href = el.get_attribute("href") or ""
                if href:
                    return href
        except Exception:
            pass
    return None


def _find_audio_url(body: dict, task_id: str) -> str | None:
    if not isinstance(body, dict):
        return None
    tid = _extract_task_id(body)
    if tid and tid != task_id:
        return None
    for key in ("url", "audio_url", "output_url", "result_url"):
        val = body.get(key, "")
        if val and isinstance(val, str) and any(ext in val for ext in (".mp3", ".wav", ".aac", ".ogg", "audio")):
            return val
    for v in body.values():
        if isinstance(v, dict):
            found = _find_audio_url(v, task_id)
            if found:
                return found
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    found = _find_audio_url(item, task_id)
                    if found:
                        return found
    return None
