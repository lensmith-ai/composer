"""The source registry: which feeds and pages a brief may read.

Sources are data, not code. Each entry names one of three fixed adapters by `kind`:

  rss-or-atom   any RSS 2.0, RSS 1.0 or Atom feed (one GET per brief)
  hn-json-api   the Hacker News top stories API (one GET for the list, one per story)
  html-index    a news page that links to articles: one GET for the page, then one per article,
                only for links on the hosts and paths you allow

The bundled list is composer/sources.json. Your own sources go in a file of the same shape
(by default ./composer-sources.json, or the path in COMPOSER_SOURCES, or --sources-file).
Entries in your file are added to the bundled ones; an entry with the same id replaces it.
See docs/adding-sources.md.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

SCHEMA = "composer-sources/v1"
BUNDLED = Path(__file__).with_name("sources.json")
LOCAL_DEFAULT = "composer-sources.json"
KINDS = ("rss-or-atom", "hn-json-api", "html-index")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FIELDS = {"id", "label", "kind", "url", "max_items", "discovery", "note"}
DISCOVERY_FIELDS = {"allowed_hosts", "allowed_path_prefixes", "max_candidates"}
MAX_ITEMS_RANGE = (1, 20)


class RegistryError(ValueError):
    """A sources file is malformed, or a brief named a source that is not in it."""


@dataclass(frozen=True)
class Source:
    id: str
    label: str
    kind: str
    url: str
    max_items: int = 5
    discovery: dict = field(default_factory=dict)
    note: str = ""

    def to_json(self) -> dict:
        out = {"id": self.id, "label": self.label, "kind": self.kind, "url": self.url,
               "max_items": self.max_items}
        if self.discovery:
            out["discovery"] = dict(self.discovery)
        if self.note:
            out["note"] = self.note
        return out


def _https(value, name: str) -> str:
    if not isinstance(value, str):
        raise RegistryError(f"{name} must be a string")
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise RegistryError(f"{name} must be an https address with a host and no user:password part")
    return value


def parse_entry(raw) -> Source:
    """One validated registry entry, or RegistryError naming what is wrong."""
    if not isinstance(raw, dict):
        raise RegistryError("each source must be an object")
    unknown = set(raw) - FIELDS
    missing = {"id", "label", "kind", "url"} - set(raw)
    if unknown or missing:
        raise RegistryError(f"source fields: missing {sorted(missing)}, unknown {sorted(unknown)}")
    sid = raw["id"]
    if not isinstance(sid, str) or not ID_RE.fullmatch(sid):
        raise RegistryError(f"source id {sid!r}: use 1-40 lowercase letters, digits and dashes")
    label = raw["label"]
    if not isinstance(label, str) or not label.strip() or len(label) > 60:
        raise RegistryError(f"{sid}: label must be 1-60 characters")
    kind = raw["kind"]
    if kind not in KINDS:
        raise RegistryError(f"{sid}: kind must be one of {', '.join(KINDS)}")
    url = _https(raw["url"], f"{sid}: url")
    max_items = raw.get("max_items", 5)
    if not isinstance(max_items, int) or isinstance(max_items, bool) or not (
            MAX_ITEMS_RANGE[0] <= max_items <= MAX_ITEMS_RANGE[1]):
        raise RegistryError(f"{sid}: max_items must be a whole number from 1 to 20")
    discovery = raw.get("discovery") or {}
    if kind == "html-index":
        if not isinstance(discovery, dict) or set(discovery) != DISCOVERY_FIELDS:
            raise RegistryError(f"{sid}: an html-index source needs discovery with exactly "
                                f"{sorted(DISCOVERY_FIELDS)}")
        hosts = discovery["allowed_hosts"]
        prefixes = discovery["allowed_path_prefixes"]
        if not isinstance(hosts, list) or not hosts or not all(isinstance(h, str) and h for h in hosts):
            raise RegistryError(f"{sid}: allowed_hosts must list at least one host")
        if not isinstance(prefixes, list) or not prefixes or not all(
                isinstance(x, str) and x.startswith("/") for x in prefixes):
            raise RegistryError(f"{sid}: allowed_path_prefixes must list paths that start with /")
        mc = discovery["max_candidates"]
        if not isinstance(mc, int) or isinstance(mc, bool) or not 1 <= mc <= 40:
            raise RegistryError(f"{sid}: max_candidates must be from 1 to 40")
    elif discovery:
        raise RegistryError(f"{sid}: only an html-index source takes discovery")
    note = raw.get("note", "")
    if not isinstance(note, str):
        raise RegistryError(f"{sid}: note must be a string")
    return Source(sid, label.strip(), kind, url, max_items, dict(discovery), note)


def parse_document(doc, where: str) -> list[Source]:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or not isinstance(doc.get("sources"), list):
        raise RegistryError(f"{where}: expected {{\"schema\": \"{SCHEMA}\", \"sources\": [...]}}")
    entries = []
    seen = set()
    for raw in doc["sources"]:
        entry = parse_entry(raw)
        if entry.id in seen:
            raise RegistryError(f"{where}: duplicate source id {entry.id!r}")
        seen.add(entry.id)
        entries.append(entry)
    return entries


def read_file(path) -> list[Source]:
    p = Path(path)
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise RegistryError(f"no sources file at {p}") from None
    except json.JSONDecodeError as exc:
        raise RegistryError(f"{p}: not valid JSON ({exc.msg}, line {exc.lineno})") from None
    return parse_document(doc, str(p))


def local_path(explicit: str | None = None) -> Path | None:
    """Your own sources file: --sources-file, else COMPOSER_SOURCES, else ./composer-sources.json if present."""
    if explicit:
        return Path(explicit)
    env = os.environ.get("COMPOSER_SOURCES")
    if env:
        return Path(env)
    here = Path.cwd() / LOCAL_DEFAULT
    return here if here.exists() else None


class Registry:
    def __init__(self, entries: list[Source]):
        self._by_id = {e.id: e for e in entries}

    @classmethod
    def load(cls, sources_file: str | None = None, *, bundled: Path = BUNDLED) -> "Registry":
        merged = {e.id: e for e in read_file(bundled)}
        local = local_path(sources_file)
        if local is not None:
            for e in read_file(local):
                merged[e.id] = e
        return cls(list(merged.values()))

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(self._by_id)

    def entries(self) -> list[Source]:
        return list(self._by_id.values())

    def get(self, source_id: str) -> Source:
        try:
            return self._by_id[source_id]
        except KeyError:
            raise RegistryError(f"unknown source {source_id[:40]!r}; known sources: "
                                + ", ".join(self._by_id)) from None

    def pick(self, ids: list[str]) -> list[Source]:
        if not ids:
            raise RegistryError("name at least one source")
        out = []
        for sid in ids:
            entry = self.get(sid)
            if entry not in out:
                out.append(entry)
        return out


def add_to_file(path, entry: Source) -> None:
    """Add (or replace) one entry in your own sources file, creating it if needed."""
    p = Path(path)
    if p.exists():
        doc = json.loads(p.read_text(encoding="utf-8"))
        parse_document(doc, str(p))
    else:
        doc = {"schema": SCHEMA, "sources": []}
    doc["sources"] = [s for s in doc["sources"] if s.get("id") != entry.id] + [entry.to_json()]
    parse_document(doc, str(p))
    p.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
