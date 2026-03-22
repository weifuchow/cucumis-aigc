from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .base import MultimodalProvider

REPO_ROOT = Path(__file__).resolve().parents[2]

# Provider name → module-level factory function
_REGISTRY: dict[str, str] = {
    "poe": "providers.poe:make_poe_provider",
    "vidu": "providers.vidu:make_vidu_provider",
    "vidu_web": "providers.vidu_web:make_vidu_web_provider",
}


def _read_dotenv(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        values[k.strip()] = v.strip().strip("'").strip('"')
    return values


def load_provider(
    env: dict[str, str] | None = None,
    env_path: Path | None = None,
) -> MultimodalProvider:
    """Create and return the configured multimodal provider.

    Resolution order for ``MEDIA_PROVIDER``:
      1. ``env`` dict argument
      2. OS environment variables
      3. ``.env`` file at repo root

    Supported values: ``poe``, ``vidu``, ``vidu_web`` (default)

    Example .env::

        MEDIA_PROVIDER=vidu_web
    """
    env_values = dict(_read_dotenv(env_path or REPO_ROOT / ".env"))
    env_values.update(os.environ)
    if env:
        env_values.update(env)

    provider_name = env_values.get("MEDIA_PROVIDER", "vidu_web").strip().lower()

    entry = _REGISTRY.get(provider_name)
    if entry is None:
        known = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown MEDIA_PROVIDER={provider_name!r}. Known providers: {known}"
        )

    module_path, func_name = entry.rsplit(":", 1)
    import importlib
    module = importlib.import_module(module_path)
    factory = getattr(module, func_name)

    provider = factory(env=env_values, env_path=env_path)
    print(f"[providers] loaded provider: {provider_name} ({type(provider).__name__})", flush=True)
    return provider
