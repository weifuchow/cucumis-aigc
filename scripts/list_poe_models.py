#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

from poe.catalog import fetch_media_catalog
from poe.client import load_poe_config


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List current Poe audio/image/video models.")
    parser.add_argument("--category", choices=["all", "audio", "image", "video"], default="all")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    catalog = fetch_media_catalog(load_poe_config())
    if args.category == "all":
        payload = catalog
    else:
        payload = {args.category: catalog[args.category]}
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
