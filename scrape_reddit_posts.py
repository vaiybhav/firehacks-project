#!/usr/bin/env python3
"""Optional CLI for reddit_community.scrape_reddit_posts (used by the API on open)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from reddit_community import scrape_reddit_posts

ROOT = Path(__file__).resolve().parent
DEFAULT_OUT = ROOT / "one-breath-app" / "public" / "community_seed.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape Reddit .json (same logic as /community-posts)")
    parser.add_argument("-n", "--count", type=int, default=15)
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    posts = scrape_reddit_posts(count=args.count)
    if not posts:
        print("No posts scraped.", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(posts, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(posts)} posts → {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
