"""Browser session management for Vidu web automation.

First run: opens a visible browser window so the user can log in manually.
Subsequent runs: restores cookies from disk (no re-login needed).

Cookie file location (configurable via VIDU_WEB_COOKIES_PATH env var):
  ~/.config/cucumis/vidu_web_session.json
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

VIDU_ORIGIN = "https://www.vidu.cn"
# Navigate to /create for login check — the homepage doesn't render the user
# avatar (it's a marketing page), but /create redirects logged-in users to
# /home/recommend where the avatar is always rendered.
_VIDU_LOGIN_CHECK_URL = "https://www.vidu.cn/create"

_DEFAULT_COOKIES_PATH = Path.home() / ".config" / "cucumis" / "vidu_web_session.json"

# When logged in, the header shows a user avatar with alt="vidu_<userId>".
# When NOT logged in, the top-right shows a "立即体验" link (public pages)
# or a visible "登录" button (inside the app).
# Checking for the user avatar image is the most reliable logged-in signal.
_SEL_LOGGED_IN = "img[alt^='vidu_']"          # user avatar (only present when logged in)
_SEL_LOGIN_BTN = "a[href='/home']:has-text('立即体验'), header button:has-text('登录')"


class ViduWebSession:
    """Manages a Playwright Chromium browser context for Vidu.

    Usage (context manager)::

        with ViduWebSession() as session:
            page = session.page
            # ... drive the page ...

    The session starts headless by default. On first use (or when cookies
    expire) it re-opens a visible window so you can log in, then saves the
    resulting cookies for future headless runs.
    """

    def __init__(
        self,
        headless: bool = True,
        cookies_path: Path | None = None,
        default_timeout_ms: int = 60_000,
    ) -> None:
        self.headless = headless
        self.cookies_path = cookies_path or _DEFAULT_COOKIES_PATH
        self.default_timeout_ms = default_timeout_ms

        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> "ViduWebSession":
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self._open_browser(headless=self.headless)

        # Pre-warm: visit service.vidu.cn to solve the EdgeOne bot challenge.
        # The challenge page runs JS and sets EO_Bot_Ssid cookie; without this,
        # all subsequent fetch() calls from the page to service.vidu.cn are
        # blocked with bot-detection HTML.
        try:
            self._page.goto(
                "https://service.vidu.cn/vidu/v1/tasks?page=1&limit=1",
                wait_until="domcontentloaded",
                timeout=15_000,
            )
            import time as _time
            _time.sleep(2)  # allow bot-challenge JS to run and set cookie
        except Exception:
            pass

        self._page.goto(_VIDU_LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=60_000)
        # For SPAs, networkidle is unreliable. Wait explicitly for the user
        # avatar element that only appears once the auth state is resolved.
        try:
            self._page.wait_for_selector(_SEL_LOGGED_IN, timeout=15_000)
        except Exception:
            pass  # Not logged in; will be handled below

        if not self._is_logged_in():
            print("[vidu_web] Not logged in — opening browser for manual login …", flush=True)
            self._interactive_login()
        else:
            print("[vidu_web] Session restored from saved cookies.", flush=True)

        return self

    def __exit__(self, *_: Any) -> None:
        self._save_cookies()
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._pw = self._browser = self._context = self._page = None

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def page(self):
        """The active Playwright Page."""
        return self._page

    @property
    def context(self):
        """The active Playwright BrowserContext."""
        return self._context

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _open_browser(self, *, headless: bool) -> None:
        storage = self._load_cookies()
        self._browser = self._pw.chromium.launch(
            headless=headless,
            args=["--no-sandbox", "--disable-web-security"],
        )
        ctx_kwargs: dict[str, Any] = {
            "viewport": {"width": 1440, "height": 900},
            "locale": "zh-CN",
        }
        if storage:
            ctx_kwargs["storage_state"] = storage
        self._context = self._browser.new_context(**ctx_kwargs)
        self._context.set_default_timeout(self.default_timeout_ms)
        self._page = self._context.new_page()

    def _is_logged_in(self) -> bool:
        """Return True if the current page shows a logged-in state.

        Positive signal: user avatar img with alt starting "vidu_<userId>"
        appears in the header when authenticated.
        """
        try:
            user_avatar = self._page.query_selector(_SEL_LOGGED_IN)
            return user_avatar is not None and user_avatar.is_visible()
        except Exception:
            return False

    def _interactive_login(self) -> None:
        """Re-open a visible window, wait for the user to log in, save cookies."""
        # If we're already headless we need to restart with a visible window
        if self.headless:
            self._browser.close()
            self._open_browser(headless=False)
            self._page.goto(_VIDU_LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

        print(
            f"[vidu_web] Please log in to {VIDU_ORIGIN} in the browser window.\n"
            "[vidu_web] Press ENTER here when you are done.",
            flush=True,
        )
        input()

        if self._is_logged_in():
            print("[vidu_web] Login detected — saving session.", flush=True)
        else:
            raise RuntimeError(
                "[vidu_web] Login not detected. Please log in and try again."
            )

        self._save_cookies()

        # Restart headless with freshly saved cookies
        if self.headless:
            self._browser.close()
            self._open_browser(headless=True)
            self._page.goto(_VIDU_LOGIN_CHECK_URL, wait_until="domcontentloaded", timeout=60_000)
            try:
                self._page.wait_for_load_state("networkidle", timeout=15_000)
            except Exception:
                pass

    def _load_cookies(self) -> dict | None:
        if self.cookies_path.is_file():
            try:
                return json.loads(self.cookies_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def _save_cookies(self) -> None:
        if self._context is None:
            return
        try:
            self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
            storage = self._context.storage_state()
            self.cookies_path.write_text(json.dumps(storage, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"[vidu_web] Warning: failed to save cookies: {exc}", flush=True)
