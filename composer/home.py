"""The app folder (COMPOSER_HOME) and its install manifest.

Everything a native install creates lives in one folder, by default ~/.lensmith-composer:

  bin/composer            the launcher (the only thing you run)
  app/<version>/venv/     a private Python environment per version; app/current points at the live one
  python/ bootstrap/      only when setup had to provide Python (a pinned uv and the CPython it installs)
  narration/venv/         only when you chose narration: its private runtime
  models/kokoro/          only when you let Composer download the narration model
  cache/ tmp/             caches and scratch for everything Composer runs
  data/                   YOUR DATA: briefs, settings, key, backups, recovery records
  install-manifest.json   what Composer created, and what it reuses read-only from outside this folder
  .composer-home          a marker that says this folder is a Composer install

Uninstall removes only what the manifest lists as created, after checking each path stays inside this folder.
It never removes data/ unless you pass --delete-data, and never touches anything listed as reused.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path

HOME_ENV = "COMPOSER_HOME"
DATA_ENV = "COMPOSER_DATA"
MARKER = ".composer-home"
MARKER_TEXT = "lensmith-composer home v1\n"
MANIFEST = "install-manifest.json"
MANIFEST_SCHEMA = "composer-install/v1"
DATA_DIR = "data"
# The only top-level names Composer itself ever creates in its folder (setup.sh uses the same list).
OWNED_NAMES = ("bin", "app", "python", "bootstrap", "narration", "models", "cache", "tmp", MARKER)
OWNED_DIRS = tuple(n for n in OWNED_NAMES if n != MARKER)
# folders Composer makes inside its own folders; like the top-level ones, each must be a real folder
OWNED_SUBDIRS = (("narration", "venv"), ("models", "kokoro"))
MIN_FREE_BYTES = 300 * 1024 * 1024


class HomeError(RuntimeError):
    """The app folder is not safe to write to, or a manifest entry is not safe to act on."""


def default_home() -> Path:
    return Path.home() / ".lensmith-composer"


def resolve_home(explicit: str | os.PathLike | None = None) -> Path:
    raw = explicit or os.environ.get(HOME_ENV) or default_home()
    path = Path(os.path.expanduser(str(raw)))
    if not path.is_absolute():
        path = Path.cwd() / path
    return Path(os.path.normpath(str(path)))


def data_root(home: Path | None = None, explicit: str | os.PathLike | None = None) -> Path:
    """The persistent data root: --data, else COMPOSER_DATA (the container sets /data), else <home>/data."""
    raw = explicit or os.environ.get(DATA_ENV)
    if raw:
        path = Path(os.path.expanduser(str(raw)))
        return Path(os.path.normpath(str(path if path.is_absolute() else Path.cwd() / path)))
    return (home or resolve_home()) / DATA_DIR


def runtime_base(home: Path, data: Path) -> Path:
    """Where runtime scratch, caches and downloaded models live: the app folder of a native install, or the data
    folder in the container (which has no app folder)."""
    return home if (home / MANIFEST).exists() else data


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------------ guards

def guard(home: Path, *, need_bytes: int = MIN_FREE_BYTES) -> str:
    """Every check that must pass BEFORE setup writes anything. Returns "new" (the folder does not exist yet),
    "empty" (it exists and is empty) or "ours" (it is already a Composer install). Raises HomeError otherwise.
    This function only reads."""
    home = Path(os.path.normpath(str(home)))
    if not home.is_absolute():
        raise HomeError(f"the app folder must be an absolute path, not {home}")
    user_home = Path(os.path.normpath(str(Path.home())))
    if home == Path(home.anchor) or home == user_home or _inside(user_home, home):
        raise HomeError(f"refused: {home} is your home folder or contains it; pick a folder of its own, "
                        "such as ~/.lensmith-composer")
    if os.path.islink(home):
        raise HomeError(f"refused: {home} is a symbolic link; give the real folder")
    if home.exists():
        if not home.is_dir():
            raise HomeError(f"refused: {home} exists and is not a folder")
        names = sorted(os.listdir(home))
        if not names:
            state = "empty"
        elif MARKER in names and is_ours(home):
            check_owned(home)
            state = "ours"
        else:
            shown = ", ".join(names[:5]) + (" ..." if len(names) > 5 else "")
            raise HomeError(f"refused: {home} already holds files that are not a Composer install ({shown}). "
                            "Nothing was written. Pick an empty or new folder with --home.")
        if not os.access(home, os.W_OK | os.X_OK):
            raise HomeError(f"refused: you cannot write to {home}")
        probe = home
    else:
        parent = home.parent
        if not parent.is_dir():
            raise HomeError(f"refused: the folder above it, {parent}, does not exist")
        if not os.access(parent, os.W_OK | os.X_OK):
            raise HomeError(f"refused: you cannot create folders in {parent}")
        state, probe = "new", parent
    free = shutil.disk_usage(probe).free
    if free < need_bytes:
        raise HomeError(f"refused: {free // (1024 * 1024)} MB free next to {home}; setup needs "
                        f"{need_bytes // (1024 * 1024)} MB")
    return state


def _plain_name(name: str) -> bool:
    return bool(name) and name not in (".", "..") and "/" not in name and os.sep not in name and "\0" not in name


def owned_dir(base: Path, *parts: str, create: bool = True) -> Path:
    """<base>/<parts...>, where base and every part is a real folder (never a symbolic link), made 0700 when it is
    missing (unless create is False). Composer writes and removes only inside folders checked this way, at the
    moment it uses them, so a link planted in its folder cannot lead a write or a removal elsewhere."""
    path = Path(os.path.normpath(str(base)))
    if os.path.islink(path):
        raise HomeError(f"refused: {path} is a symbolic link; Composer works only in its own real folders")
    if create and parts and not os.path.lexists(path):
        os.makedirs(path, mode=0o700, exist_ok=True)
    for part in parts:
        if not _plain_name(part):
            raise HomeError(f"refused: {part!r} is not a plain folder name")
        path = path / part
        if os.path.islink(path):
            raise HomeError(f"refused: {path} is a symbolic link; Composer works only in its own real folders, "
                            "so nothing was written or removed. Remove the link (or the folder) and run it again.")
        if os.path.lexists(path):
            if not path.is_dir():
                raise HomeError(f"refused: {path} is not a folder")
        elif create:
            os.mkdir(path, 0o700)
            if os.path.islink(path) or not path.is_dir():  # made by someone else in between
                raise HomeError(f"refused: {path} changed while Composer made it")
    return path


def check_owned(home: Path) -> None:
    """Refuse an app folder whose own parts lead elsewhere: every folder Composer makes in it (bin, app, python,
    bootstrap, narration, models, cache, tmp and the ones inside them) must be a real folder, not a symbolic link,
    and the only link allowed is app/current, which must name a real app/<version> folder beside it. Call it before
    any write or removal in the app folder; it only reads."""
    home = Path(os.path.normpath(str(home)))
    if os.path.islink(home):
        raise HomeError(f"refused: {home} is a symbolic link; give the real folder")
    if not home.exists():
        return
    for name in OWNED_DIRS:
        owned_dir(home, name, create=False)
    for parts in OWNED_SUBDIRS:
        owned_dir(home, *parts, create=False)
    app = home / "app"
    if not app.is_dir():
        return
    for entry in sorted(os.listdir(app)):
        path = app / entry
        if entry in ("current", ".current.tmp"):  # the version pointer (and its temporary name while it changes)
            target = os.readlink(path) if os.path.islink(path) else ""
            if not (_plain_name(target) and not target.startswith(".") and os.path.isdir(app / target)
                    and not os.path.islink(app / target)):
                raise HomeError(f"refused: {path} must be a link to a version folder beside it (it points at "
                                f"{target or 'nothing'!r}); nothing was written or removed")
        elif os.path.islink(path):
            raise HomeError(f"refused: {path} is a symbolic link; Composer works only in its own real folders")
        elif path.is_dir():
            owned_dir(path, "venv", create=False)


def is_ours(home: Path) -> bool:
    marker = home / MARKER
    try:
        if marker.is_symlink() or marker.read_text(encoding="utf-8") != MARKER_TEXT:
            return False
    except OSError:
        return False
    manifest = home / MANIFEST
    if not manifest.exists():
        return True  # setup.sh wrote the marker and stopped before the manifest; setup finishes it
    try:
        doc = load_manifest(home)
    except HomeError:
        return False
    return doc.get("home") == str(home)


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


# ------------------------------------------------------------------------------------------------ manifest

def new_manifest(home: Path, *, home_created: bool, version: str) -> dict:
    return {"schema": MANIFEST_SCHEMA, "home": str(home), "home_created": home_created, "version": version,
            "created_at": now(), "updated_at": now(), "state": "installed", "entries": [], "changes_outside": []}


def load_manifest(home: Path) -> dict:
    path = home / MANIFEST
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HomeError(f"no install manifest at {path}") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise HomeError(f"the install manifest at {path} cannot be read: {exc}") from None
    if not isinstance(doc, dict) or doc.get("schema") != MANIFEST_SCHEMA or not isinstance(doc.get("entries"), list):
        raise HomeError(f"{path} is not a Composer install manifest")
    return doc


def save_manifest(home: Path, doc: dict) -> None:
    doc["updated_at"] = now()
    # ensure_ascii=False keeps the folder's name as written, so setup.sh can match it ("home": "<path>")
    atomic_write(home / MANIFEST, json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n", mode=0o600)


def add_entry(doc: dict, path: str, kind: str, **extra) -> None:
    """Record one path. kind: "created" (Composer made it; uninstall removes it), "user-data" (removed only
    with --delete-data) or "reused" (an absolute path outside the folder, opened read-only, never removed)."""
    if kind not in ("created", "user-data", "reused"):
        raise HomeError(f"unknown manifest entry kind {kind!r}")
    entry = {"path": path, "kind": kind, **extra}
    doc["entries"] = [e for e in doc["entries"] if not (e.get("path") == path and e.get("kind") == kind)]
    doc["entries"].append(entry)


def created_path(home: Path, rel: str) -> Path:
    """The real path of a "created" or "user-data" entry, or HomeError if it is not safely inside the folder:
    it must be relative, have no "..", not be the folder itself, and resolve (through any symlinked parent)
    to a place inside the folder."""
    if not isinstance(rel, str) or not rel or rel.startswith(("/", "\\")) or os.path.isabs(rel):
        raise HomeError(f"manifest entry {rel!r} is not a relative path inside the app folder")
    parts = Path(rel).parts
    if any(p in ("..", ".", "") for p in parts) or "\\" in rel:
        raise HomeError(f"manifest entry {rel!r} is not a plain path inside the app folder")
    real_home = Path(os.path.realpath(home))
    target = home / rel
    parent_real = Path(os.path.realpath(target.parent))
    if parent_real != real_home and not _inside(parent_real, real_home):
        raise HomeError(f"manifest entry {rel!r} leads outside the app folder")
    return target


def _identities(path: Path) -> set:
    """(device, inode) of a path and of every folder above it: what a removal must never contain. Identity, not
    spelling, so a different letter case or Unicode form on a case-insensitive disk cannot slip past."""
    out = set()
    p = Path(os.path.realpath(path))
    while True:
        try:
            st = os.stat(p)
            out.add((st.st_dev, st.st_ino))
        except OSError:
            pass
        if p.parent == p:
            return out
        p = p.parent


def check_manifest(home: Path, doc: dict, data: Path) -> list[str]:
    """Problems that make acting on this manifest unsafe (empty list = safe). The data folder is protected by its
    identity as well as its path: the one given, <home>/data, and the one recorded at setup."""
    problems = []
    if doc.get("home") != str(home):
        problems.append(f"the manifest belongs to {doc.get('home')!r}, not {home}")
    real_data = Path(os.path.realpath(data))
    protected = [real_data, Path(os.path.realpath(home / DATA_DIR))]
    if isinstance(doc.get("data_path"), str) and os.path.isabs(doc["data_path"]):
        protected.append(Path(os.path.realpath(doc["data_path"])))
    guarded = set()
    for d in protected:
        guarded |= _identities(d)
    guarded -= _identities(home)  # the app folder and the folders above it hold more than your data
    for entry in doc.get("entries", []):
        kind, rel = entry.get("kind"), entry.get("path")
        if kind == "reused":
            if not isinstance(rel, str) or not os.path.isabs(rel):
                problems.append(f"reused entry {rel!r} is not an absolute path")
            continue
        if kind not in ("created", "user-data"):
            problems.append(f"entry {rel!r} has an unknown kind {kind!r}")
            continue
        try:
            target = created_path(home, rel)
        except HomeError as exc:
            problems.append(str(exc))
            continue
        real = Path(os.path.realpath(target))
        if kind == "created" and rel not in OWNED_NAMES:
            problems.append(f"entry {rel!r} is not something setup creates; refusing")
            continue
        if kind == "created":
            ident = None
            try:
                st = os.lstat(target)
                ident = (st.st_dev, st.st_ino)
            except OSError:
                pass
            if (rel.split("/", 1)[0].casefold() == DATA_DIR or ident in guarded
                    or any(real == d or _inside(d, real) or _inside(real, d) for d in protected)):
                problems.append(f"entry {rel!r} is listed as removable but holds your data; refusing")
        if kind == "user-data" and rel != DATA_DIR:
            problems.append(f"user-data entry {rel!r} is not the data folder")
        for other in doc.get("entries", []):
            if other.get("kind") == "reused" and isinstance(other.get("path"), str):
                outside = Path(os.path.realpath(other["path"]))
                if outside == real or _inside(outside, real):
                    problems.append(f"entry {rel!r} contains a reused path {other['path']}; refusing")
    return problems


def remove_entry(home: Path, rel: str) -> bool:
    """Remove one created path without following symbolic links. True when something was removed."""
    target = created_path(home, rel)
    try:
        st = os.lstat(target)
    except FileNotFoundError:
        return False
    if stat.S_ISLNK(st.st_mode) or not stat.S_ISDIR(st.st_mode):
        os.unlink(target)
    else:
        shutil.rmtree(target)  # never follows symlinks inside the tree; a symlink is removed, not its target
    return True


# ------------------------------------------------------------------------------------------------ files

def atomic_write(path: Path, text: str, *, mode: int = 0o644) -> None:
    """Write text to a temporary file next to `path` (created with `mode` from the start), then rename it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name("." + path.name + f".{os.getpid()}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def private_env(home: Path, base: dict | None = None) -> dict:
    """The environment for everything Composer starts: every cache, temp and config location points inside
    the app folder, user pip settings and the user site folder are ignored, and pip refuses to install outside
    a virtual environment."""
    env = {k: v for k, v in (os.environ if base is None else base).items()
           if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "COMPOSER_CHECKER_API_KEY",
                        "COMPOSER_SERVER_PASS")}  # no key reaches a child
    cache, tmp = home / "cache", home / "tmp"
    env.update({
        "TMPDIR": str(tmp), "PIP_CACHE_DIR": str(cache / "pip"), "UV_CACHE_DIR": str(cache / "uv"),
        "UV_PYTHON_INSTALL_DIR": str(home / "python"), "XDG_CACHE_HOME": str(cache / "xdg"),
        "XDG_CONFIG_HOME": str(cache / "xdg-config"), "XDG_DATA_HOME": str(cache / "xdg-data"),
        "HF_HOME": str(cache / "hf"), "PYTHONPYCACHEPREFIX": str(cache / "pycache"),
        "PIP_REQUIRE_VIRTUALENV": "1", "PIP_CONFIG_FILE": os.devnull, "PYTHONNOUSERSITE": "1",
        "PIP_DISABLE_PIP_VERSION_CHECK": "1", "UV_NO_CONFIG": "1", HOME_ENV: str(home),
    })
    return env


def ensure_private_dirs(home: Path) -> None:
    for name in ("cache", "tmp"):
        owned_dir(home, name)
