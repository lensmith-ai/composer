"""hn-json-api: the Hacker News top stories, from the public Firebase API.

One GET for the list of story ids (the source's url), then one GET per story, up to
`max_items`, within a total time budget. Only the title, link and score are kept; story text
and comments are never fetched.
"""
from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

from ..sanitize import clean_text, clean_url
from .common import TITLE_CAP, new_receipt

ITEM_TIMEOUT_S = 15
TOTAL_BUDGET_S = 60


def item_url(list_url: str, item_id: int) -> str:
    """https://<host>/v0/item/<id>.json, on the same host as the list."""
    p = urlsplit(list_url)
    return f"https://{p.netloc}/v0/item/{int(item_id)}.json"


def fetch(source, get, *, clock=time.monotonic):
    receipt = new_receipt(source)
    items: list[dict] = []
    started = clock()
    try:
        top = get(source.url, ITEM_TIMEOUT_S)
        receipt["bytes"] += len(top.body)
        ids = json.loads(top.body.decode("utf-8"))
        if not isinstance(ids, list):
            raise ValueError("the story list is not a list")
        errors = 0
        for item_id in ids:
            if len(items) >= source.max_items:
                break
            if clock() - started > TOTAL_BUDGET_S:
                receipt["note"] = f"time budget of {TOTAL_BUDGET_S} s reached after {len(items)} stories"
                break
            if not isinstance(item_id, int) or isinstance(item_id, bool):
                errors += 1
                continue
            try:
                resp = get(item_url(source.url, item_id), ITEM_TIMEOUT_S)
                receipt["bytes"] += len(resp.body)
                story = json.loads(resp.body.decode("utf-8"))
            except Exception:
                errors += 1
                continue
            if not isinstance(story, dict) or not story.get("title"):
                errors += 1
                continue
            title = clean_text(str(story["title"])[:TITLE_CAP])
            link = clean_url(story.get("url") or f"https://news.ycombinator.com/item?id={item_id}")
            receipt["cleaned"] += title.changes + link.changes
            score = story.get("score")
            items.append({"title": title.text,
                          "description": f"{score} points on Hacker News" if isinstance(score, int) else "",
                          "url": link.text, "published": ""})
        if errors:
            receipt["item_errors"] = errors
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"[:300]
    receipt["items"] = len(items)
    if items:
        receipt["status"] = "ok"
    elif "error" not in receipt:
        receipt["error"] = "no stories could be read"
    return items, receipt
