"""Live-safe source options, probe/register, hot reload, and data-only packages."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from . import adapters, discovery, fetch, registry
from .home import make_dirs
from .sanitize import clean_text


# A probe of a full registry entry (and the re-read before it is saved): an html-index entry may list up to 40
# candidate articles of up to 2 MB each, so the whole probe also has a request and a byte budget.
PROBE_MAX_REQUESTS = 24
PROBE_MAX_BYTES = 8 * 1024 * 1024


class SourceServiceError(ValueError):
    """A source service request is invalid or cannot safely be persisted."""


PACKAGES_SCHEMA = "source-packages/v1"
BUNDLED_PACKAGES = Path(__file__).with_name("packages.json")
_PACKAGE_FIELDS = {"package_id", "label", "description", "provenance", "source_ids", "selection_policy"}
_POLICY_FIELDS = {"unavailable_members", "paid_requires_confirmation", "offline_trial_eligible"}
_UNAVAILABLE_POLICIES = ("refuse", "skip_with_disclosure")


@dataclass(frozen=True)
class SourcePackage:
    """A named starting set of sources (the picker's package chips). A suggestion only: it never changes what a
    compose request may name, and the brief uses the sources ticked when it is sent."""
    package_id: str
    label: str
    description: str
    provenance: str
    source_ids: tuple[str, ...]
    unavailable_members: str = "refuse"
    paid_requires_confirmation: bool = False
    offline_trial_eligible: bool = False

    @property
    def id(self) -> str:
        return self.package_id


def parse_package(raw: object, sources: registry.Registry | None = None) -> SourcePackage:
    """One validated package. With `sources`, every member must be a known, visible source, and a package that
    skips unavailable members must keep at least one available."""
    if not isinstance(raw, dict) or set(raw) != _PACKAGE_FIELDS:
        found = sorted(raw) if isinstance(raw, dict) else []
        raise SourceServiceError(f"a source package needs exactly {sorted(_PACKAGE_FIELDS)} (got {found})")
    package_id = raw["package_id"]
    if not isinstance(package_id, str) or not registry.ID_RE.fullmatch(package_id):
        raise SourceServiceError("source package id: use 1-40 lowercase letters, digits and dashes")
    for name in ("label", "description", "provenance"):
        if not isinstance(raw[name], str) or not raw[name].strip() or len(raw[name]) > 300:
            raise SourceServiceError(f"{package_id}: {name} must be 1 to 300 characters")
    if len(raw["label"].strip()) > 60:
        raise SourceServiceError(f"{package_id}: label must be 1 to 60 characters")
    source_ids = raw["source_ids"]
    if not isinstance(source_ids, list) or not source_ids or not all(isinstance(x, str) for x in source_ids):
        raise SourceServiceError(f"{package_id}: source_ids must list one or more source ids")
    if len(set(source_ids)) != len(source_ids):
        raise SourceServiceError(f"{package_id}: a source is named twice")
    policy = raw["selection_policy"]
    if not isinstance(policy, dict) or set(policy) != _POLICY_FIELDS:
        raise SourceServiceError(f"{package_id}: selection_policy needs exactly {sorted(_POLICY_FIELDS)}")
    if policy["unavailable_members"] not in _UNAVAILABLE_POLICIES:
        raise SourceServiceError(f"{package_id}: unavailable_members must be refuse or skip_with_disclosure")
    if not isinstance(policy["paid_requires_confirmation"], bool) or not isinstance(policy["offline_trial_eligible"],
                                                                                     bool):
        raise SourceServiceError(f"{package_id}: paid_requires_confirmation and offline_trial_eligible are true or false")
    package = SourcePackage(package_id, raw["label"].strip(), raw["description"].strip(), raw["provenance"].strip(),
                            tuple(source_ids), policy["unavailable_members"], policy["paid_requires_confirmation"],
                            policy["offline_trial_eligible"])
    if sources is not None:
        known = {e.id: e for e in sources.entries()}
        for source_id in source_ids:
            if source_id not in known:
                raise SourceServiceError(f"{package_id}: names a source that is not in the registry ({source_id!r})")
            if known[source_id].hidden:
                raise SourceServiceError(f"{package_id}: names a hidden source ({source_id!r})")
        if package.unavailable_members == "skip_with_disclosure" and not any(
                known[x].available for x in source_ids):
            raise SourceServiceError(f"{package_id}: none of its sources is available")
    return package


def package_projection(packages, sources: registry.Registry) -> dict:
    """What the page reads (options `packages`): each package's policy and its members' state now. A member that has
    since left the registry is marked unknown, one hidden since is left out. This registry has no paid sources and
    no offline replay of single sources, so paid and trial_eligible are always false."""
    known = {e.id: e for e in sources.entries()}
    out = {}
    for package in packages:
        members = []
        for source_id in package.source_ids:
            entry = known.get(source_id)
            if entry is None:
                members.append({"source_id": source_id, "status": "unknown", "paid": False, "trial_eligible": False})
            elif not entry.hidden:
                members.append({"source_id": source_id, "status": "available" if entry.available else "unavailable",
                                "paid": False, "trial_eligible": False})
        out[package.package_id] = {
            "package_id": package.package_id, "label": package.label, "description": package.description,
            "selection_policy": {"unavailable_members": package.unavailable_members,
                                 "paid_requires_confirmation": package.paid_requires_confirmation,
                                 "offline_trial_eligible": package.offline_trial_eligible},
            "members": members}
    return out


class PackageService:
    """The bundled packages (composer/packages.json) plus your own file of the same shape; an entry in your file with
    the same package_id replaces the bundled one. Read again when either file or the source registry changes. A
    package that names an unknown or hidden source is set aside (the others still load) and the health says why; a
    file that cannot be read at all keeps the last good set."""

    def __init__(self, path: Path | None = None, *, bundled: Path = BUNDLED_PACKAGES):
        self.path = Path(path) if path is not None else None
        self.bundled = Path(bundled)
        self._lock = threading.RLock()
        self._key = None
        self._packages: tuple[SourcePackage, ...] = ()
        self._health = {"degraded": False, "error": "", "package_ids": [], "refused_packages": {}}

    @staticmethod
    def _stamp(path: Path | None):
        if path is None:
            return None
        try:
            st = path.stat()
        except OSError:
            return None
        return st.st_ino, st.st_mtime_ns, st.st_size

    @staticmethod
    def _read(path: Path) -> list:
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SourceServiceError(f"{path.name}: not valid JSON ({exc.msg}, line {exc.lineno})") from None
        if not isinstance(doc, dict) or set(doc) != {"schema", "packages"} or doc["schema"] != PACKAGES_SCHEMA \
                or not isinstance(doc["packages"], list):
            raise SourceServiceError(f"{path.name}: expected {{\"schema\": \"{PACKAGES_SCHEMA}\", \"packages\": [...]}}")
        ids = [p.get("package_id") for p in doc["packages"] if isinstance(p, dict)]
        if len(ids) != len(set(ids)):
            raise SourceServiceError(f"{path.name}: a package id is used twice")
        return doc["packages"]

    def current(self, sources: registry.Registry, version=None) -> tuple[tuple[SourcePackage, ...], dict]:
        """The packages checked against `sources`; `version` names that registry (its reload generation), so a new
        registry is never mistaken for the one the packages were last checked against."""
        with self._lock:
            key = (self._stamp(self.bundled), self._stamp(self.path), version if version is not None else id(sources))
            if key == self._key:
                return self._packages, dict(self._health)
            self._key = key
            try:
                raw = {p.get("package_id"): p for p in self._read(self.bundled) if isinstance(p, dict)}
                if self.path is not None and self.path.exists():
                    raw.update({p.get("package_id"): p for p in self._read(self.path) if isinstance(p, dict)})
            except (OSError, SourceServiceError) as exc:
                self._health = {"degraded": True, "error": _safe_reason(exc),
                                "package_ids": [p.package_id for p in self._packages], "refused_packages": {}}
                return self._packages, dict(self._health)
            packages, refused = [], {}
            for name, item in raw.items():
                try:
                    packages.append(parse_package(item, sources))
                except SourceServiceError as exc:
                    refused[str(name or "?")[:60]] = _safe_reason(exc)
            self._packages = tuple(packages)
            self._health = {"degraded": bool(refused),
                            "error": "; ".join(f"{k}: {v}" for k, v in refused.items()),
                            "package_ids": [p.package_id for p in packages], "refused_packages": refused}
            return self._packages, dict(self._health)


def suggest_id(label: str, taken: set) -> str:
    """A registry id from a name: lower case, dashes, unique."""
    base = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:32] or "source"
    if base not in taken:
        return base
    for n in range(2, 1000):
        candidate = f"{base}-{n}"
        if candidate not in taken:
            return candidate
    raise SourceServiceError("could not find a free id for that name")


def _safe_reason(value: object) -> str:
    return " ".join(str(value or "").split())[:300]


def source_option(source: registry.Source) -> dict:
    return {"id": source.id, "label": source.label, "kind": source.kind, "max_items": source.max_items,
            "available": source.available, "hidden": source.hidden, "reason": source.reason}


class SourceService:
    """An in-process registry service; the last valid registry survives a bad local edit."""

    def __init__(self, path: Path, *, bundled: Path = registry.BUNDLED, get=fetch.http_get,
                 packages: PackageService | None = None):
        self.path = Path(path)
        self.packages = packages or PackageService(None)
        self.bundled = Path(bundled)
        self.get = get
        self._lock = threading.RLock()
        self._registry = registry.Registry(registry.read_file(self.bundled))
        self._generation = 0
        self._stamp = None
        self._reload = {"state": "ready", "reason": ""}
        self._probe_status: dict[str, dict] = {}
        self._refresh(force=True)

    def _file_stamp(self):
        try:
            stat = self.path.stat()
        except FileNotFoundError:
            return None
        return stat.st_ino, stat.st_mtime_ns, stat.st_size

    def _load(self) -> registry.Registry:
        if not self.path.exists():
            return registry.Registry(registry.read_file(self.bundled))
        return registry.Registry.load(str(self.path), bundled=self.bundled)

    def _refresh(self, *, force: bool = False) -> None:
        stamp = self._file_stamp()
        if not force and stamp == self._stamp:
            return
        try:
            loaded = self._load()
        except registry.RegistryError as exc:
            self._reload = {"state": "degraded", "reason": _safe_reason(exc)}
            self._stamp = stamp
            return
        self._registry = loaded
        self._generation += 1
        self._stamp = stamp
        self._reload = {"state": "ready", "reason": ""}

    def snapshot(self) -> registry.Registry:
        with self._lock:
            self._refresh()
            return self._registry

    def options(self) -> dict:
        current = self.snapshot()
        return {"generation": self._generation, "reload": dict(self._reload),
                "sources": [source_option(item) for item in current.entries()]}

    def probe(self, raw: object) -> dict:
        try:
            source = registry.parse_entry(raw)
        except registry.RegistryError as exc:
            raise SourceServiceError(str(exc)) from None
        deadline = time.monotonic() + fetch.TOTAL_S
        spent = {"requests": 0, "bytes": 0}

        def guarded_get(url: str, timeout: float):
            # one probe: one time limit, at most PROBE_MAX_REQUESTS requests and PROBE_MAX_BYTES read in all
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise fetch.FetchTimeout("the source probe ran out of time")
            if spent["requests"] >= PROBE_MAX_REQUESTS:
                raise fetch.FetchError(f"the source probe made its {PROBE_MAX_REQUESTS} requests")
            if spent["bytes"] >= PROBE_MAX_BYTES:
                raise fetch.FetchError(f"the source probe read its {PROBE_MAX_BYTES // (1024 * 1024)} MB")
            spent["requests"] += 1
            if self.get is fetch.http_get:
                got = self.get(url, min(timeout, remaining), total_s=remaining)
            else:
                got = self.get(url, min(timeout, remaining))
            spent["bytes"] += len(getattr(got, "body", b"") or b"")
            return got

        items, receipt = adapters.fetch(source, guarded_get)
        safe_receipt = {key: receipt[key] for key in
                        ("source", "label", "status", "items", "bytes", "cleaned", "fetch_tier") if key in receipt}
        if receipt.get("error"):
            safe_receipt["reason"] = _safe_reason(receipt["error"])
        result = {"source": source_option(source), "receipt": safe_receipt,
                  "fetch_tier": safe_receipt.get("fetch_tier", "native"),
                  "headlines": [{"title": item["title"], "url": item["url"], "published": item.get("published", "")}
                                for item in items]}
        with self._lock:
            self._probe_status[source.id] = safe_receipt
        return result

    def _write(self, entry: registry.Source, *, new: bool = False) -> None:
        """Write one entry to the sources file. The whole read, check, merge and write happens under the file's lock,
        shared by every process and command that writes it, so two writers cannot lose each other's entry. With
        `new`, an entry whose id or address appeared meanwhile is refused instead of replaced."""
        make_dirs(self.path.parent)
        try:
            with registry.file_lock(self.path):
                if self.path.exists():
                    try:
                        document = json.loads(self.path.read_text(encoding="utf-8"))
                        registry.parse_document(document, str(self.path))
                    except (json.JSONDecodeError, registry.RegistryError) as exc:
                        raise SourceServiceError(f"cannot replace malformed sources file: {exc}") from None
                else:
                    document = {"schema": registry.SCHEMA, "sources": []}
                if new and any(item.get("id") == entry.id or item.get("url") == entry.url
                               for item in document["sources"]):
                    raise SourceServiceError("that source was added by someone else while this was working; "
                                             "check again")
                document["sources"] = ([item for item in document["sources"] if item.get("id") != entry.id]
                                       + [entry.to_json()])
                registry.parse_document(document, str(self.path))
                registry.write_document(self.path, document)
        except registry.RegistryError as exc:
            raise SourceServiceError(str(exc)) from None

    def register(self, raw: object) -> dict:
        result = self.probe(raw)
        if result["receipt"].get("status") != "ok":
            raise SourceServiceError("source must pass its probe before registration")
        try:
            entry = registry.parse_entry(raw)
        except registry.RegistryError as exc:
            raise SourceServiceError(str(exc)) from None
        with self._lock:
            self._write(entry)
            self._stamp = None
            self._refresh(force=True)
        return source_option(entry)

    # ------------------------------------------------------------------ add a source from a pasted address

    def discover(self, address: object) -> dict:
        """The page's "Check the address": candidate feeds behind a pasted address, none of them chosen."""
        try:
            return discovery.discover(address, get=self.get)
        except discovery.DiscoveryError as exc:
            raise SourceServiceError(str(exc)) from None

    def register_candidate(self, body: object) -> dict:
        """The page's "Add to my sources": one candidate a person picked, under the name they typed.

        The candidate comes back from the browser, so nothing in it is trusted but its address: that address is read
        again, once, and must still give items. The entry is a plain rss-or-atom source; its note records when it
        was added, from which pasted address, and what it returned at that moment."""
        if not isinstance(body, dict) or set(body) - {"candidate", "label", "pasted_url"}:
            raise SourceServiceError("send {\"candidate\": {...}, \"label\": \"...\", \"pasted_url\": \"...\"}")
        candidate = body.get("candidate")
        if not isinstance(candidate, dict) or not isinstance(candidate.get("url"), str):
            raise SourceServiceError("pick one of the addresses that were checked")
        label = body.get("label")
        if not isinstance(label, str) or not label.strip():
            raise SourceServiceError("a source needs a name; that is what you will see in the picker")
        label = " ".join(clean_text(label).text.split())  # no hidden or direction-changing characters in a name
        if not label:
            raise SourceServiceError("a source needs a name; that is what you will see in the picker")
        if len(label) > 60:
            raise SourceServiceError("that name is longer than 60 characters")
        try:  # recorded in the entry's note only in the form a check would use (never with a user:password part)
            pasted = " ".join(clean_text(discovery.normalise(body.get("pasted_url"))[0]).text.split())
        except discovery.DiscoveryError:
            pasted = ""
        url = candidate["url"].strip()
        try:
            url = registry.public_https(url, "that address")
        except registry.RegistryError as exc:
            raise SourceServiceError(str(exc)) from None
        # A page whose own article links are read (no feed): the browser only says so; the host, the path prefix and
        # the limits are built here from the address, exactly as the check offered them, never taken from the browser.
        page_links, raw = candidate.get("kind") == "html-index", None
        if page_links:
            try:
                raw = discovery.index_entry(url)
            except discovery.DiscoveryError as exc:
                raise SourceServiceError(str(exc)) from None
            url = raw["url"]
        with self._lock:
            current = self.snapshot().entries()
        for existing in current:
            if existing.url == url:
                raise SourceServiceError(f"that {'page' if page_links else 'feed'} is already here as "
                                         f"\u201c{existing.label}\u201d")
            if existing.label.lower() == label.lower():
                raise SourceServiceError(f"a source called \u201c{label}\u201d already exists; pick another name")
        base = {**raw, "id": suggest_id(label, {e.id for e in current}), "label": label} if page_links else {
            "id": suggest_id(label, {e.id for e in current}), "label": label, "kind": "rss-or-atom", "url": url,
            "max_items": 5}
        entry = registry.parse_entry(base)
        checked = self.probe(entry.to_json())
        if checked["receipt"].get("status") != "ok":
            raise SourceServiceError("that address did not give any items when it was read again, so it was not "
                                     "added: " + (checked["receipt"].get("reason") or "no reason given"))
        titles = [h["title"] for h in checked["headlines"]]
        when = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        reads = (f"; it reads the article links on that page ({raw['discovery']['allowed_hosts'][0]}"
                 f"{raw['discovery']['allowed_path_prefixes'][0]} only)") if page_links else ""
        note = (f"added from the app on {when} from {pasted[:300] or url}{reads}; it then gave {len(titles)} items"
                + (f", newest \u201c{titles[0][:60]}\u201d" if titles else ""))
        entry = registry.parse_entry({**entry.to_json(), "note": note})
        with self._lock:
            ids = {e.id for e in self.snapshot().entries()}
            if entry.id in ids or any(e.url == url for e in self.snapshot().entries()):
                raise SourceServiceError("that source was added by someone else while this was working; check again")
            self._write(entry, new=True)
            self._stamp = None
            self._refresh(force=True)
            now = self._registry
        if entry.id not in now.ids:
            raise SourceServiceError("the source was saved but the registry did not load it; check the sources file")
        return {"source": {"id": entry.id, "label": entry.label, "url": entry.url, "kind": entry.kind,
                           "note": entry.note},
                "sources_now": len(now.ids)}

    def package_options(self) -> tuple[dict, dict]:
        """(the page's `packages`, their health) against the registry as it is now."""
        with self._lock:
            current = self.snapshot()
            generation = self._generation
        packages, health = self.packages.current(current, generation)
        return package_projection(packages, current), health
