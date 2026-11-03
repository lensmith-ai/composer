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

import contextlib
import ipaddress
import json
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from . import fetch
from .home import make_dirs

SCHEMA = "composer-sources/v1"
BUNDLED = Path(__file__).with_name("sources.json")
LOCAL_DEFAULT = "composer-sources.json"
KINDS = ("rss-or-atom", "hn-json-api", "html-index")
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FIELDS = {"id", "label", "kind", "url", "max_items", "discovery", "note", "available", "hidden", "reason",
          "extraction_tier"}
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
    available: bool = True
    hidden: bool = False
    reason: str = ""
    extraction_tier: str = "native"

    def to_json(self) -> dict:
        out = {"id": self.id, "label": self.label, "kind": self.kind, "url": self.url,
               "max_items": self.max_items}
        if self.discovery:
            out["discovery"] = dict(self.discovery)
        if self.note:
            out["note"] = self.note
        if not self.available:
            out["available"] = False
        if self.hidden:
            out["hidden"] = True
        if self.reason:
            out["reason"] = self.reason
        if self.extraction_tier != "native":
            out["extraction_tier"] = self.extraction_tier
        return out


def public_https(value, name: str) -> str:
    """`value` if it is an https address with a host, no user:password part and no address on this machine or a
    private network (names are checked again at fetch time, on the address actually connected to)."""
    if not isinstance(value, str):
        raise RegistryError(f"{name} must be a string")
    p = urlsplit(value)
    if p.scheme != "https" or not p.hostname or p.username or p.password:
        raise RegistryError(f"{name} must be an https address with a host and no user:password part")
    if not fetch.private_allowed() and _names_this_machine_or_private(p.hostname):
        raise RegistryError(f"{name} names this machine or a private network address; sources must be "
                            f"public web sites (set {fetch.ALLOW_PRIVATE_ENV}=1 to allow it on purpose)")
    return value


def _names_this_machine_or_private(hostname: str) -> bool:
    """A literal non-public IP address, or a localhost name. Other names are checked again at
    fetch time, on the address actually connected to (composer.fetch)."""
    h = hostname.lower().rstrip(".")
    if h == "localhost" or h.endswith(".localhost"):
        return True
    try:
        ipaddress.ip_address(h)
    except ValueError:
        return False
    return not fetch.is_public_address(h)


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
    url = public_https(raw["url"], f"{sid}: url")
    max_items = raw.get("max_items", 5)
    if not isinstance(max_items, int) or isinstance(max_items, bool) or not (
            MAX_ITEMS_RANGE[0] <= max_items <= MAX_ITEMS_RANGE[1]):
        raise RegistryError(f"{sid}: max_items must be a whole number from 1 to 20")
    discovery = raw.get("discovery") or {}
    extraction_tier = raw.get("extraction_tier", "native")
    if extraction_tier not in ("native", "trafilatura"):
        raise RegistryError(f"{sid}: extraction_tier must be native or trafilatura")
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
    elif discovery or "extraction_tier" in raw:
        raise RegistryError(f"{sid}: only an html-index source takes discovery or extraction_tier")
    note = raw.get("note", "")
    if not isinstance(note, str):
        raise RegistryError(f"{sid}: note must be a string")
    available = raw.get("available", True)
    hidden = raw.get("hidden", False)
    reason = raw.get("reason", "")
    if not isinstance(available, bool) or not isinstance(hidden, bool) or not isinstance(reason, str) or len(reason) > 300:
        raise RegistryError(f"{sid}: available and hidden must be booleans; reason must be at most 300 characters")
    if (not available or hidden) and not reason.strip():
        raise RegistryError(f"{sid}: an unavailable or hidden source needs a reason")
    return Source(sid, label.strip(), kind, url, max_items, dict(discovery), note, available, hidden, reason.strip(),
                  extraction_tier)


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
            if not entry.available or entry.hidden:
                raise RegistryError(f"source {entry.id!r} is unavailable: {entry.reason or 'not available'}")
            if entry not in out:
                out.append(entry)
        return out


LOCK_WAIT_S = 30


@contextlib.contextmanager
def file_lock(path, wait_s: float = LOCK_WAIT_S, *, lock_file=None):
    """Hold <sources file>.lock (or `lock_file`): every writer of one sources file (each `composer serve` or
    `composer up` process, `composer sources add`, setup) takes it for the whole read, check, merge and write; the lens
    store uses the same lock for its own folder."""
    lock_path = Path(lock_file) if lock_file is not None else Path(str(path) + ".lock")
    make_dirs(lock_path.parent)
    # 0600 explicitly (a default ACL above would make open()'s 0666 group-writable), never through a link
    handle = os.fdopen(os.open(lock_path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600), "r+b")
    deadline = time.monotonic() + wait_s
    try:
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RegistryError(f"the sources file is busy (another writer holds {lock_path.name}); "
                                        "try again") from None
                time.sleep(0.05)
        yield
    finally:
        try:
            if os.name == "nt":
                import msvcrt
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        handle.close()


def write_document(path, doc: dict) -> None:
    """Replace the file with `doc` in one step: a temporary file of its own in the same folder, flushed to disk,
    renamed over the old one, then the folder itself flushed (where the system allows it)."""
    p = Path(path)
    fd, temporary = tempfile.mkstemp(prefix=f".{p.name}.", suffix=".tmp", dir=str(p.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(json.dumps(doc, indent=2, ensure_ascii=False) + "\n")
            out.flush()
            os.fsync(out.fileno())
        os.replace(temporary, p)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if os.name != "nt":
        dir_fd = os.open(str(p.parent), os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)


def add_to_file(path, entry: Source) -> None:
    """Add (or replace) one entry in your own sources file, creating it if needed (under the file's lock)."""
    p = Path(path)
    make_dirs(p.parent)
    with file_lock(p):
        if p.exists():
            doc = json.loads(p.read_text(encoding="utf-8"))
            parse_document(doc, str(p))
        else:
            doc = {"schema": SCHEMA, "sources": []}
        doc["sources"] = [s for s in doc["sources"] if s.get("id") != entry.id] + [entry.to_json()]
        parse_document(doc, str(p))
        write_document(p, doc)
