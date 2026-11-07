"""The fixed adapter set. A registry entry picks one by `kind`; data can never run code.

Every adapter has the same contract:

    fetch(source, get) -> (items, receipt)

`get(url, timeout)` returns a composer.fetch.Response or raises. `items` is a list of
{"title", "description", "url", "published"} with every string cleaned (composer.sanitize).
`receipt` says what happened: {"source", "label", "status": "ok" | "failed", "items", "bytes",
"cleaned", and "error" when it failed}. An adapter never raises for a bad feed; it reports it.
"""
from __future__ import annotations

from . import hn_json_api, html_index, rss_or_atom
from .common import DESC_CAP, PUB_CAP, TITLE_CAP, new_receipt  # noqa: F401

ADAPTERS = {
    "rss-or-atom": rss_or_atom.fetch,
    "hn-json-api": hn_json_api.fetch,
    "html-index": html_index.fetch,
}


def fetch(source, get, *, enrich=False):
    """Run the adapter the source names. `enrich` (a brief asks for it) lets an rss-or-atom feed read an entry with
    no real text from its own page, or drop it (composer.adapters.thin); other kinds ignore it."""
    try:
        adapter = ADAPTERS[source.kind]
    except KeyError:
        raise ValueError(f"no adapter for kind {source.kind!r}") from None
    if source.kind == "rss-or-atom":
        return adapter(source, get, enrich=enrich)
    return adapter(source, get)
