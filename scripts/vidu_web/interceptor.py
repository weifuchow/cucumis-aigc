"""Network response interceptor for Vidu web automation.

The Vidu web app is a React SPA that communicates with its backend via XHR/fetch.
Rather than scraping the DOM for results, we intercept those internal network calls
to get clean structured JSON — much more reliable than DOM selectors.

Usage::

    with ResponseCapture(session.page, url_pattern="**/api/**") as capture:
        # ... trigger page action (click Generate, etc.) ...
        task_response = capture.wait_for(lambda r: "id" in r.get("data", {}))
        task_id = task_response["data"]["id"]
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable


class ResponseCapture:
    """Collects JSON responses from page network calls matching *url_pattern*.

    Can be used as a context manager (automatically starts/stops) or manually
    via :meth:`start` / :meth:`stop`.
    """

    def __init__(self, page, url_pattern: str = "**/*") -> None:
        self._page = page
        self._url_pattern = url_pattern
        self._responses: list[dict[str, Any]] = []
        self._lock = threading.Lock()
        self._handler: Callable | None = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "ResponseCapture":
        self.start()
        return self

    def __exit__(self, *_: Any) -> None:
        self.stop()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin recording responses."""

        def _on_response(response) -> None:
            try:
                if not _url_matches(response.url, self._url_pattern):
                    return
                if response.status < 200 or response.status >= 300:
                    return
                body = response.json()
                with self._lock:
                    self._responses.append(
                        {"url": response.url, "status": response.status, "body": body}
                    )
            except Exception:
                pass  # ignore non-JSON or network errors

        self._handler = _on_response
        self._page.on("response", self._handler)

    def stop(self) -> None:
        """Stop recording responses."""
        if self._handler:
            try:
                self._page.remove_listener("response", self._handler)
            except Exception:
                pass
            self._handler = None

    def wait_for(
        self,
        predicate: Callable[[dict[str, Any]], bool],
        timeout: float = 60.0,
        poll_interval: float = 0.5,
    ) -> dict[str, Any] | None:
        """Block until a captured response body satisfies *predicate*.

        Returns the matching response dict ``{"url", "status", "body"}``,
        or ``None`` if *timeout* is reached.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._lock:
                for r in self._responses:
                    if predicate(r["body"]):
                        return r
            time.sleep(poll_interval)
        return None

    def all_bodies(self) -> list[dict[str, Any]]:
        """Return all captured response bodies (shallow copy)."""
        with self._lock:
            return [r["body"] for r in self._responses]

    def clear(self) -> None:
        """Discard all accumulated responses."""
        with self._lock:
            self._responses.clear()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _url_matches(url: str, pattern: str) -> bool:
    """Simple glob-style URL matching (supports ** and *)."""
    import fnmatch

    return fnmatch.fnmatch(url, pattern)
