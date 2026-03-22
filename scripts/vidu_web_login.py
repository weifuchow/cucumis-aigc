"""One-time login helper for ViduWebProvider.

Run this script once to authenticate and save your Vidu session cookie.
Subsequent automation runs (headless) will reuse the saved cookie.

Usage:
    python3 scripts/vidu_web_login.py

After login, cookies are saved to:
    ~/.config/cucumis/vidu_web_session.json
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).parent))

from vidu_web.session import ViduWebSession, _DEFAULT_COOKIES_PATH

print("=" * 60)
print("Vidu Web Session Login")
print("=" * 60)
print(f"Cookie file: {_DEFAULT_COOKIES_PATH}")
print()

# Force headless=False so the browser window is always visible for login
with ViduWebSession(headless=False) as session:
    if session._is_logged_in():
        print("✓ Already logged in! Session saved.")
    else:
        print("✗ Not logged in — please log in via the browser window.")
        print("  Press ENTER here when done.")
        input()

print()
print(f"✓ Session saved to: {_DEFAULT_COOKIES_PATH}")
print("You can now run with MEDIA_PROVIDER=vidu_web (headless mode).")
