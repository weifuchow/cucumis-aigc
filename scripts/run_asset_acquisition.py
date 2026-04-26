#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main() -> int:
    legacy_script = Path(__file__).with_name("run_stock_asset_curator.py")
    sys.argv[0] = Path(__file__).name
    spec = importlib.util.spec_from_file_location("run_stock_asset_curator", legacy_script)
    if spec is None or spec.loader is None:
        raise SystemExit(f"unable to load asset acquisition implementation: {legacy_script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main()


if __name__ == "__main__":
    raise SystemExit(main())
