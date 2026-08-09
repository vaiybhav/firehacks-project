#!/usr/bin/env python3
"""Scrape Reddit posts for the Community Wall (runs via API when the page opens).

Prefers the public `.json` suffix shortcut. Falls back to Reddit's Atom `.rss`
feed when JSON is blocked (common 403 on some networks).
"""

from __future__ import annotations

import json
import re
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime
from html import unescape

DEFAULT_SUBREDDITS = ("meditation", "yoga", "mindfulness")
USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 "
    "Mobile/15E148 Safari/604.1"
)
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl._create_unverified_context()


def _http_get(url: str, accept: str = "application/json") -> bytes:
    """GET with urllib first; fall back to curl (often survives Reddit bot filters)."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20, context=_ssl_context()) as resp:
            return resp.read()
    except Exception as urllib_exc:
        try:
            result = subprocess.run(
                [
                    "curl",
                    "-fsSL",
                    "-m",
                    "20",
                    "-A",
                    USER_AGENT,
                    "-H",
                    f"Accept: {accept}",
                    url,
                ],
                check=True,
                capture_output=True,
            )
            return result.stdout
        except Exception:
            raise urllib_exc


def _strip_html(raw: str) -> str:
    text = unescape(re.sub(r"<[^>]+>", " ", raw or ""))
    return re.sub(r"\s+", " ", text).strip()


def _parse_json_listing(payload: dict, subreddit: str) -> list[dict]:
    posts: list[dict] = []
    for child in payload.get("data", {}).get("children", []):
        data = child.get("data") or {}
        text = (data.get("selftext") or "").strip()
        if len(text) <= 30 or data.get("over_18"):
            continue
        posts.append(
            {
                "id": f"reddit_{data['id']}",
                "type": "reddit",
                "author": data.get("author") or "Redditor",
                "text": text[:500] + ("..." if len(text) > 500 else ""),
                "timestamp": int(data.get("created_utc", 0) * 1000),
                "upvotes": int(data.get("ups") or 0),
                "subreddit": data.get("subreddit") or subreddit,
            }
        )
    return posts


def _parse_rss(raw: bytes, subreddit: str) -> list[dict]:
    root = ET.fromstring(raw)
    posts: list[dict] = []
    for entry in root.findall("a:entry", ATOM_NS):
        content_el = entry.find("a:content", ATOM_NS)
        summary_el = entry.find("a:summary", ATOM_NS)
        body = _strip_html((content_el.text if content_el is not None else None) or "")
        if not body:
            body = _strip_html((summary_el.text if summary_el is not None else None) or "")
        title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
        text = body if len(body) > 30 else (f"{title}. {body}".strip() if title else body)
        if len(text) <= 30:
            continue

        entry_id = entry.findtext("a:id", default="", namespaces=ATOM_NS) or ""
        # ids look like: t3_abcdef
        short = entry_id.rsplit("/", 1)[-1].replace("t3_", "") or str(abs(hash(entry_id)))[:10]
        author = entry.findtext("a:author/a:name", default="Redditor", namespaces=ATOM_NS) or "Redditor"
        updated = entry.findtext("a:updated", default="", namespaces=ATOM_NS) or ""
        try:
            ts = int(datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp() * 1000)
        except Exception:
            try:
                ts = int(parsedate_to_datetime(updated).timestamp() * 1000)
            except Exception:
                ts = int(time.time() * 1000)

        posts.append(
            {
                "id": f"reddit_{short}",
                "type": "reddit",
                "author": author,
                "text": text[:500] + ("..." if len(text) > 500 else ""),
                "timestamp": ts,
                "upvotes": 0,
                "subreddit": subreddit,
            }
        )
    return posts


def fetch_subreddit_hot(subreddit: str, limit: int = 25) -> list[dict]:
    # 1) Preferred: .json suffix shortcut
    json_url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    try:
        raw = _http_get(json_url, accept="application/json")
        payload = json.loads(raw.decode("utf-8"))
        posts = _parse_json_listing(payload, subreddit)
        if posts:
            return posts
    except Exception as exc:
        print(f"Reddit JSON blocked/failed for r/{subreddit}: {exc}")

    # 2) Fallback: Atom RSS (still Reddit public feed)
    rss_url = f"https://www.reddit.com/r/{subreddit}/.rss"
    raw = _http_get(rss_url, accept="application/atom+xml,application/xml,text/xml,*/*")
    return _parse_rss(raw, subreddit)[:limit]


def scrape_reddit_posts(
    count: int = 15,
    subreddits: tuple[str, ...] | list[str] = DEFAULT_SUBREDDITS,
) -> list[dict]:
    """Return up to `count` text posts. Called when Community Wall opens."""
    collected: list[dict] = []
    seen: set[str] = set()

    for i, subreddit in enumerate(subreddits):
        try:
            batch = fetch_subreddit_hot(subreddit, limit=min(25, max(count * 2, 15)))
            print(f"r/{subreddit}: got {len(batch)} posts")
        except Exception as exc:  # noqa: BLE001
            print(f"Reddit scrape failed for r/{subreddit}: {exc}")
            continue

        for post in batch:
            if post["id"] in seen:
                continue
            seen.add(post["id"])
            collected.append(post)
            if len(collected) >= count:
                return collected

        if i < len(subreddits) - 1:
            time.sleep(0.8)

    return collected
