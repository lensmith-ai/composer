"""rss-or-atom: one GET of the feed, then RSS 2.0, RSS 1.0 or Atom entries as items.

Elements are matched by their local name, so namespaced feeds parse. A feed that declares
entities (<!ENTITY) is refused before parsing: no feed needs them, and they are how XML
expansion attacks work.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from ..sanitize import clean_text, clean_url
from .common import DESC_CAP, PUB_CAP, TIMEOUT_S, TITLE_CAP, new_receipt, strip_html

ITEM_TAGS = ("item", "entry")
TITLE = ("title",)
DESC = ("description", "summary", "content", "encoded")
PUB = ("pubDate", "updated", "published", "date")


def _local(tag) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _text(el, names) -> str:
    """Text of the first child named in `names` that has text (an empty <description> does not
    hide a full <content:encoded> after it)."""
    first = None
    for child in el:
        if _local(child.tag) in names:
            if first is None:
                first = child
            if (child.text or "").strip():
                return child.text
    return (first.text or "") if first is not None else ""


def _link(el) -> str:
    """RSS: <link>text</link>. Atom: <link href=...>, preferring rel="alternate"."""
    best = ""
    for child in el:
        if _local(child.tag) != "link":
            continue
        href = (child.get("href") or "").strip()
        text = (child.text or "").strip()
        if href:
            if (child.get("rel") or "alternate").lower() == "alternate":
                return href
            best = best or href
        elif text:
            return text
    return best


def parse(raw: bytes, max_items: int) -> tuple[list[dict], int]:
    """(items, cleaned-count) from feed bytes. Raises ValueError for a feed that cannot be read."""
    if b"<!ENTITY" in raw:
        raise ValueError("feed declares XML entities; refused")
    root = ET.fromstring(raw)
    items: list[dict] = []
    cleaned = 0
    for el in root.iter():
        if _local(el.tag) not in ITEM_TAGS:
            continue
        if len(items) >= max_items:
            break
        title = clean_text(strip_html(_text(el, TITLE))[:TITLE_CAP])
        desc = clean_text(strip_html(_text(el, DESC))[:DESC_CAP])
        pub = clean_text(_text(el, PUB).strip()[:PUB_CAP])
        link = clean_url(_link(el))
        cleaned += title.changes + desc.changes + pub.changes + link.changes
        if not title.text:
            continue
        items.append({"title": title.text, "description": desc.text, "url": link.text,
                      "published": pub.text})
    return items, cleaned


def fetch(source, get):
    receipt = new_receipt(source)
    try:
        resp = get(source.url, TIMEOUT_S)
        receipt["bytes"] = len(resp.body)
        if resp.status != 200:
            raise ValueError(f"feed answered HTTP {resp.status}")
        items, cleaned = parse(resp.body, source.max_items)
    except Exception as exc:  # a bad feed is reported, never raised
        receipt["error"] = f"{type(exc).__name__}: {exc}"[:300]
        return [], receipt
    receipt["cleaned"] = cleaned
    receipt["items"] = len(items)
    if items:
        receipt["status"] = "ok"
    else:
        receipt["error"] = "the feed had no items with a title"
    return items, receipt
