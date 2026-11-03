"""Public lens registry and content-addressed custom lens recipes."""
from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

from .home import make_dirs

READING_LEVELS = ("plain", "standard", "technical")
LOCK_NAME = ".lens-store.lock"
REGISTERS = ("earnest", "sceptical", "deadpan")
LENS_MAX_CHARS = 300


class LensError(ValueError):
    """A lens definition or recipe cannot be used safely."""


class StaleRevision(LensError):
    """An edit names a revision that is no longer the lens's newest one."""


@dataclass(frozen=True)
class Lens:
    id: str
    name: str
    blurb: str
    instruction: str
    reading_level: str = "standard"
    shape: dict | None = None
    available: bool = True
    reason: str = ""
    revision: str = ""
    register: str = ""
    previous: str = ""
    editable: bool = False
    number: int = 0

    def option(self) -> dict:
        return {"id": self.id, "name": self.name, "title": self.name, "blurb": self.blurb,
                "reading_level": self.reading_level, "register": self.register, "shape": dict(self.shape or {}),
                "available": self.available, "reason": self.reason, "revision": self.number or None,
                "digest": self.revision, "previous": self.previous or None, "looks_for": self.instruction,
                "editable": self.editable}


_BUILTINS = (
    Lens("system-improvements", "System improvements", "Find useful changes that make a system work better.",
         "Look for concrete improvements, who benefits, and what would make them durable.", "plain", {"items": "insights"}),
    Lens("second-order-effects", "Second-order effects", "Look past the first result for what changes next.",
         "Trace likely follow-on effects, tradeoffs, and who might be affected after the first change.", "standard", {"items": "insights"}),
    Lens("raised-eyebrow", "Raised eyebrow", "Notice claims that deserve a careful second look.",
         "Identify surprising claims, missing evidence, incentives, and the most useful question to ask next.", "plain", {"items": "insights"}),
)


def validate_text(value: object) -> str:
    if not isinstance(value, str):
        raise LensError("the lens must be text")
    text = value.strip()
    if not text:
        raise LensError("give a lens: a few words on what to look for")
    if len(text) > LENS_MAX_CHARS:
        raise LensError(f"keep the lens under {LENS_MAX_CHARS} characters")
    if "LENS>>>" in text or "<<<LENS" in text:
        raise LensError("the lens may not contain the lens delimiters")
    return text


def check_shape(lens: Lens, brief: dict, requested_insights: int) -> list[str]:
    items = brief.get("items") if isinstance(brief, dict) else None
    if not isinstance(items, list):
        return ["brief has no items"]
    if len(items) != requested_insights:
        return [f"lens asked for {requested_insights} insights but brief has {len(items)}"]
    if lens.reading_level == "plain":
        for index, item in enumerate(items):
            text = str(item.get("insight", "")) if isinstance(item, dict) else ""
            if any(len(word.strip(".,;:!?()[]{}\"'")) > 24 for word in text.split()):
                return [f"plain reading level failed for insight {index + 1}"]
    return []


class LensRegistry:
    def __init__(self, entries: tuple[Lens, ...] = _BUILTINS):
        self._entries = entries
        self._by_id = {entry.id: entry for entry in entries}

    @classmethod
    def builtin(cls) -> "LensRegistry":
        return cls()

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(entry.id for entry in self._entries)

    def entries(self) -> tuple[Lens, ...]:
        return self._entries

    def get(self, lens_id: str) -> Lens:
        try:
            return self._by_id[lens_id]
        except KeyError:
            raise LensError(f"unknown lens {str(lens_id)[:60]!r}") from None


class LensStore:
    """Your own lenses. Every revision is a recipe file named by the SHA-256 of its canonical JSON, never changed
    after it is written. An edit writes a new revision that names the one it replaces (`previous`) and keeps the
    lens's id, so a lens has one id and a line of revisions: the picker shows the newest, and a brief records the
    exact revision it used."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self._lock = threading.Lock()

    @staticmethod
    def _recipe(raw: object, previous: str | None = None, lens_id: str | None = None) -> dict:
        if not isinstance(raw, dict) or not {"name", "instruction", "reading_level"} <= set(raw) <= {
                "name", "instruction", "reading_level", "register"}:
            raise LensError("a lens recipe needs name, instruction, and reading_level (and may name a register)")
        name = raw["name"]
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 60:
            raise LensError("lens name must be 1 to 60 characters")
        level = raw["reading_level"]
        if level not in READING_LEVELS:
            raise LensError("reading_level must be plain, standard, or technical")
        register = raw.get("register", "")
        if register not in ("", *REGISTERS):
            raise LensError("register must be " + ", ".join(REGISTERS[:-1]) + " or " + REGISTERS[-1])
        recipe = {"schema": "lens-recipe/v1", "name": " ".join(name.split()), "instruction": validate_text(raw["instruction"]),
                  "reading_level": level}
        if register:
            recipe["register"] = register
        if previous:
            recipe["previous"] = previous
        if lens_id:
            recipe["lens"] = lens_id
        return recipe

    @contextlib.contextmanager
    def _locked(self):
        """Every save holds this for its whole read-check-write: the in-process lock, and a lock file in the lens
        folder shared by every process that writes it (two `composer serve` on one folder, `composer up`), so an
        edit's check that it names the newest revision cannot be overtaken by another process's edit."""
        from . import registry
        make_dirs(self.root)
        with self._lock:
            try:
                with registry.file_lock(self.root / LOCK_NAME, lock_file=self.root / LOCK_NAME):
                    yield
            except registry.RegistryError as exc:
                raise LensError("the lens folder is busy (another save holds its lock); try again") from exc

    def _write(self, recipe: dict) -> str:
        encoded = json.dumps(recipe, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        revision = hashlib.sha256(encoded).hexdigest()
        target = self.root / revision
        make_dirs(target)
        path = target / "recipe.json"
        if not path.exists():  # a temporary file of its own, flushed, then renamed into place
            fd, temporary = tempfile.mkstemp(prefix=".recipe.", suffix=".tmp", dir=str(target))
            try:
                with os.fdopen(fd, "wb") as out:
                    out.write(encoded + b"\n")
                    out.flush()
                    os.fsync(out.fileno())
                os.replace(temporary, path)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            if os.name != "nt":
                dir_fd = os.open(str(target), os.O_RDONLY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
        return revision

    def save(self, raw: object, *, previous: str | None = None) -> Lens:
        """Save a recipe; with `previous`, as the next revision of the lens that revision belongs to."""
        with self._locked():
            lens_id = None
            if previous is not None:
                lens_id = self.get(previous).id
                head = self.head(lens_id)
                if head is None or head.revision != previous:
                    # two edits of the same revision would fork the lens and hide one of them
                    raise StaleRevision("this lens was changed since that revision; edit its newest revision"
                                        + (f" ({head.revision})" if head is not None else ""))
            revision = self._write(self._recipe(raw, previous, lens_id if previous else None))
            return self._lineage(self.get(revision))

    def save_form(self, form: object) -> tuple[Lens, bool]:
        """The page's "Make a lens" / "Edit lens" form: {name, looks_for, register, reading_level, replaces}.

        `replaces` is null for a new lens, or the id of one of your lenses to edit; the edit becomes that lens's
        newest revision. Returns (the lens as it now is, whether a new revision was written)."""
        if not isinstance(form, dict) or not {"name", "looks_for", "reading_level"} <= set(form) <= {
                "name", "looks_for", "register", "reading_level", "replaces"}:
            raise LensError("send {\"name\", \"looks_for\", \"register\", \"reading_level\", \"replaces\"}")
        raw = {"name": form["name"], "instruction": form["looks_for"], "reading_level": form["reading_level"]}
        if form.get("register") not in (None, ""):
            raw["register"] = form["register"]
        replaces = form.get("replaces")
        with self._locked():
            if replaces in (None, ""):
                revision = self._write(self._recipe(raw))
                return self._lineage(self.get(revision)), True
            if not isinstance(replaces, str):
                raise LensError("replaces must be the id of one of your lenses")
            head = self.head(replaces)
            if head is None:
                if replaces in LensRegistry.builtin().ids:
                    raise LensError("a built-in lens cannot be changed; make a new lens instead")
                raise LensError("there is no lens of yours with that id to edit")
            recipe = self._recipe(raw, head.revision, head.id)
            unchanged = all(recipe[key] == getattr(head, field) for key, field in (
                ("name", "name"), ("instruction", "instruction"), ("reading_level", "reading_level"))) and \
                recipe.get("register", "") == head.register
            if unchanged:
                return head, False
            return self._lineage(self.get(self._write(recipe))), True

    def _all(self) -> dict:
        found = {}
        if not self.root.exists():
            return found
        for child in sorted(self.root.iterdir()):
            if child.is_dir():
                try:
                    found[child.name] = self.get(child.name)
                except LensError:
                    continue
        return found

    def _lineage(self, lens: Lens, everything: dict | None = None) -> Lens:
        """The lens with its revision number: 1 for a new lens, one more for each edit before it."""
        everything = self._all() if everything is None else everything
        number, cursor, seen = 1, lens, {lens.revision}
        while cursor.previous and cursor.previous in everything and cursor.previous not in seen:
            seen.add(cursor.previous)
            cursor = everything[cursor.previous]
            number += 1
        return dataclasses.replace(lens, number=number)

    def entries(self) -> tuple[Lens, ...]:
        """The newest revision of each of your lenses, oldest lens first."""
        everything = self._all()
        replaced = {lens.previous for lens in everything.values() if lens.previous}
        heads: dict[str, Lens] = {}
        for lens in (self._lineage(entry, everything) for entry in everything.values()):
            if lens.revision in replaced:
                continue
            best = heads.get(lens.id)
            if best is None or (lens.number, self._mtime(lens)) > (best.number, self._mtime(best)):
                heads[lens.id] = lens
        return tuple(sorted(heads.values(), key=lambda lens: (self._first_saved(lens, everything), lens.id)))

    def _mtime(self, lens: Lens) -> int:
        try:
            return (self.root / lens.revision / "recipe.json").stat().st_mtime_ns
        except OSError:
            return 0

    def _first_saved(self, lens: Lens, everything: dict) -> int:
        """When the lens's first revision was written (its order in the picker)."""
        cursor, seen = lens, {lens.revision}
        while cursor.previous in everything and cursor.previous not in seen:
            seen.add(cursor.previous)
            cursor = everything[cursor.previous]
        return self._mtime(cursor)

    def head(self, lens_id: str) -> Lens | None:
        """The newest revision of one of your lenses, by its id."""
        for lens in self.entries():
            if lens.id == lens_id:
                return lens
        return None

    def get(self, revision: str) -> Lens:
        if not isinstance(revision, str) or len(revision) != 64 or any(c not in "0123456789abcdef" for c in revision):
            raise LensError("invalid lens revision")
        try:
            recipe = json.loads((self.root / revision / "recipe.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError):
            raise LensError("lens revision not found") from None
        encoded = json.dumps(recipe, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != revision:
            raise LensError("lens recipe digest does not match its revision")
        lens_id = recipe.get("lens") or "custom-" + revision[:12]
        return Lens(lens_id, recipe["name"], "Your saved lens.", recipe["instruction"],
                    recipe["reading_level"], {"items": "insights"}, revision=revision,
                    register=recipe.get("register", ""), previous=recipe.get("previous", ""), editable=True)
