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
        return given_path(raw)
    return (home or resolve_home()) / DATA_DIR


def given_path(raw: str | os.PathLike) -> Path:
    """A folder named on the command line, made absolute and normalised as written: never resolved, so a symbolic
    link on the way stays visible to the trust check (which refuses it and names the real path)."""
    path = Path(os.path.expanduser(str(raw)))
    return Path(os.path.normpath(str(path if path.is_absolute() else Path.cwd() / path)))


def runtime_base(home: Path, data: Path) -> Path:
    """Where runtime scratch, caches and downloaded models live: the app folder of a native install, or the data
    folder in the container (which has no app folder)."""
    return home if (home / MANIFEST).exists() else data


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------------------------------------------ guards

# ------------------------------------------------------------------------------------------------ the trust contract
# Composer trusts your own account and root, and nothing else. Before it sets up, updates, rolls back, recovers or
# works in its folder (narration included), the folder and every folder above it, up to /, must be owned by you or
# root and writable by no one else (no group or other write bit), checked on the path as given and on its real path
# (links resolved); the path as given may not go through a symbolic link at all. Inside it, the same rule holds for every folder and file Composer writes into, runs or reads as
# its own configuration (bin, app, app/<version> and its environment, python, bootstrap, narration, models, cache,
# tmp, the marker and the manifest, and the data folder with its recovery records): an existing install where any of
# them breaks it is refused, not adopted. This is the rule OpenSSH applies to ~/.ssh ("StrictModes"). With it, only
# your own account (or root) can change anything under Composer's folder, so a race between a check and a use there
# is a race against yourself: no other account can redirect a write, a removal, or what a program Composer starts
# reads or writes.
# What is not defended: a process already running as you (it can change your files directly), root, and systems
# without POSIX owners and permission bits (on Windows this check does not run).
_OTHERS_WRITE = stat.S_IWGRP | stat.S_IWOTH


def trust_problem(path, st: os.stat_result, uid: int) -> str | None:
    """The rule for one folder or file, from its stat result: why another account could change it, or None. It must
    belong to you (uid) or root, and a folder or file must have no group or other write bit (a link's own bits mean
    nothing, so only its owner counts). Pure: it only reads `st`."""
    if st.st_uid not in (uid, 0):
        return (f"{path} belongs to another account (uid {st.st_uid}). Fix: chown $(id -un) {path}, or put the "
                "app folder somewhere else (the default is ~/.lensmith-composer)")
    if stat.S_ISLNK(st.st_mode) or not st.st_mode & _OTHERS_WRITE:
        return None
    mode = f"{stat.S_IMODE(st.st_mode):04o}"
    if stat.S_ISDIR(st.st_mode) and st.st_mode & stat.S_ISVTX:
        return (f"{path} is a folder shared by every account (mode {mode}, like /tmp). Put the app folder under "
                "your own home instead (the default is ~/.lensmith-composer)")
    return (f"{path} can be written by other accounts (mode {mode}). Fix: chmod go-w {path}, or put the app "
            "folder somewhere else (the default is ~/.lensmith-composer)")


def _uid() -> int | None:
    return os.getuid() if os.name == "posix" and hasattr(os, "getuid") else None


def check_trust(path: Path) -> None:
    """Refuse when `path` (or, if it does not exist yet, its nearest existing folder) or any folder above it is owned
    by another account or writable by group or others, or when any of them is a symbolic link. A link is refused
    because the folders it leads through (and the ones its target's own links lead through) are on neither the path
    as given nor the real path, so they would go unchecked: a writable folder there lets another account change
    where the path leads. Only reads."""
    uid = _uid()
    if uid is None:
        return
    path = Path(os.path.normpath(str(path)))
    start = path
    while not os.path.lexists(start) and start != start.parent:
        start = start.parent
    for folder in (start, *start.parents):
        if os.path.islink(folder):
            raise HomeError(f"refused: {folder} is a symbolic link. Give the real path instead "
                            f"({os.path.realpath(path)}): Composer checks every folder on the path it is given, and "
                            "the folders a link leads through are not on it")
    real = Path(os.path.realpath(start))
    seen = set()
    for folder in (start, *start.parents, real, *real.parents):
        if folder in seen:
            continue
        seen.add(folder)
        try:
            st = os.stat(folder)
        except OSError as exc:
            raise HomeError(f"refused: cannot check {folder} ({exc.strerror or exc})") from None
        why = trust_problem(folder, st, uid)
        if why:
            raise HomeError(f"refused: {why}. Composer's folder and every folder above it must belong to you or root "
                            "and be writable only by you or root, so no other account can change what it runs")


class no_group_write:
    """For as long as it is held (a whole update, a runtime install), everything this process and the programs it
    starts make (venv, pip, Python's bytecode) gets no group or other write bit, whatever the umask was: under 002,
    common with per-user groups, they would make folders the check below refuses. Only takes bits away."""

    def __enter__(self):
        self.old = os.umask(0o022) if os.name == "posix" else None
        if self.old is not None:
            os.umask(self.old | 0o022)
        return self

    def __exit__(self, *exc):
        if self.old is not None:
            os.umask(self.old)
        return False


def check_entry(path: Path, st: os.stat_result | None = None) -> None:
    """The rule for one folder or file inside Composer's folders (lstat unless `st` is given). Only reads."""
    uid = _uid()
    if uid is None:
        return
    if st is None:
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            return
    why = trust_problem(path, st, uid)
    if why:
        raise HomeError(f"refused: {why}. Every folder and file in Composer's folder must belong to you or root and "
                        "be writable only by you or root, so no other account can change what it writes, runs or "
                        "reads; nothing was written or removed")


def check_tree(root: Path) -> None:
    """check_entry for `root` and everything below it, links included but never followed: folders, files and
    links. Only reads. Refuses at the first entry that another account could change."""
    if _uid() is None:
        return
    root = Path(os.path.normpath(str(root)))
    try:
        st = os.lstat(root)
    except FileNotFoundError:
        return
    check_entry(root, st)
    if not stat.S_ISDIR(st.st_mode):
        return
    stack = [root]
    while stack:
        folder = stack.pop()
        try:
            entries = list(os.scandir(folder))
        except OSError as exc:
            raise HomeError(f"refused: cannot check {folder} ({exc.strerror or exc}); nothing was written or "
                            "removed") from None
        for entry in entries:
            st = entry.stat(follow_symlinks=False)
            check_entry(Path(entry.path), st)
            if stat.S_ISDIR(st.st_mode):
                stack.append(Path(entry.path))


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
    check_trust(home)
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
    check_trust(path)
    if create and parts and not os.path.lexists(path):
        make_dirs(path)
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
            _set_folder_mode(path, 0o700)  # explicit: a default ACL above would otherwise decide
        else:
            continue
        check_entry(path)  # each folder on the way, not only the base: a writable one lets another account swap
    return path


# The folders whose paths every program Composer starts is given (private_env): TMPDIR, the caches, the Python
# folder. Checked just before a program is started, so a folder opened up since the last full check is refused.
HANDED = ("tmp", "cache", "python", "cache/pip", "cache/uv", "cache/xdg", "cache/xdg-config", "cache/xdg-data",
          "cache/hf", "cache/pycache")


def check_handed(base: Path) -> None:
    """Refuse when a folder whose path private_env(base) hands to a program, or `base` itself, could be changed by
    another account (the folders that do not exist yet are fine: they are made private). Only reads."""
    base = Path(os.path.normpath(str(base)))
    check_trust(base)
    check_entry(base)
    for rel in HANDED:
        path = base / rel
        if os.path.islink(path):
            raise HomeError(f"refused: {path} is a symbolic link; Composer works only in its own real folders")
        check_entry(path)


# ------------------------------------------------------------------------------------------- confined operations
# A check on a path, then a write by that path, leaves a gap: a folder swapped for a link in between sends the write
# elsewhere. So writes and removals in Composer's own folders go through open folder descriptors: the app folder is
# opened once (not following a link), each folder below it is opened relative to the one above (again not following
# links), and files are created, renamed and removed by name inside an open folder. A folder renamed or swapped after
# it was opened cannot redirect anything: the descriptor still names the folder that was checked.
_DIR_FLAGS = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
CONFINED = (hasattr(os, "O_NOFOLLOW") and hasattr(os, "O_DIRECTORY") and os.open in os.supports_dir_fd
            and os.mkdir in os.supports_dir_fd and os.unlink in os.supports_dir_fd and os.rmdir in os.supports_dir_fd
            and os.rename in os.supports_dir_fd and os.scandir in os.supports_fd)


def _set_folder_mode(path: Path, mode: int) -> None:
    """chmod a folder through the folder itself, opened without following a link (fchmod): a link put in its place
    is refused, never followed, so the mode of the folder a link names is never changed."""
    if os.name != "posix" or not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "fchmod"):
        os.chmod(path, mode)
        return
    try:
        fd = os.open(path, _DIR_FLAGS)
    except OSError:
        raise HomeError(f"refused: {path} is a symbolic link or not a folder; Composer sets the mode of its own real "
                        "folders only, so nothing was changed") from None
    try:
        os.fchmod(fd, mode)
    finally:
        os.close(fd)


def make_dirs(path: Path, *, mode: int = 0o700, exist_ok: bool = True) -> Path:
    """`mkdir -p` for Composer's own folders: each folder it makes is set to `mode` (0700) explicitly once it exists,
    through the folder as opened. mkdir's own mode is narrowed by the umask, but under a default POSIX ACL on the
    folder above the ACL decides instead (0777 comes out 0775); an explicit mode is the same whatever the umask or
    the ACL. Folders that already exist are left as they are (exist_ok=False: `path` itself must be new)."""
    path = Path(os.path.normpath(str(path)))
    if not exist_ok and os.path.lexists(path):
        raise FileExistsError(f"{path} already exists")
    missing = []
    probe = path
    while not os.path.lexists(probe) and probe != probe.parent:
        missing.append(probe)
        probe = probe.parent
    for folder in reversed(missing):
        try:
            os.mkdir(folder, mode)
        except FileExistsError:
            continue  # made meanwhile (only this account can write here): left as it is
        _set_folder_mode(folder, mode)
    return path


def private_folder(path: Path) -> Path:
    """The data folder: made (with any missing folder above it) and set to 0700 through the folder as opened, never
    by path, so a link put in its place cannot make Composer change the mode of the folder that link names."""
    path = make_dirs(path)
    _set_folder_mode(path, 0o700)
    return path


class Owned:
    """An open folder of Composer's own: `fd` stays on the folder that was checked for as long as it is open."""

    def __init__(self, fd: int, path: Path):
        self.fd, self.path = fd, path

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
        return False

    def close(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def write(self, name: str, text: str, *, mode: int = 0o644) -> Path:
        """Write a file by name in this folder: a new temporary file (never following a link), then a rename."""
        if not _plain_name(name):
            raise HomeError(f"refused: {name!r} is not a plain file name")
        tmp = f".{name}.{os.getpid()}.tmp"
        try:
            os.unlink(tmp, dir_fd=self.fd)  # a leftover of that name is never reused: always a fresh file
        except FileNotFoundError:
            pass
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=self.fd)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.flush()
                os.fchmod(handle.fileno(), mode)
                os.fsync(handle.fileno())
            os.rename(tmp, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
        except BaseException:
            try:
                os.unlink(tmp, dir_fd=self.fd)
            except OSError:
                pass
            raise
        return self.path / name

    def child(self, name: str, *, create: bool = True) -> "Owned":
        """The folder `name` inside this one, opened without following a link (made 0700 when missing)."""
        if not _plain_name(name):
            raise HomeError(f"refused: {name!r} is not a plain folder name")
        made = False
        if create:
            try:
                os.mkdir(name, 0o700, dir_fd=self.fd)
                made = True
            except FileExistsError:
                pass
        try:
            fd = os.open(name, _DIR_FLAGS, dir_fd=self.fd)
        except FileNotFoundError:
            raise
        except OSError:
            raise HomeError(f"refused: {self.path / name} is a symbolic link or not a folder; Composer works only in "
                            "its own real folders, so nothing was written or removed") from None
        if made:
            try:
                os.fchmod(fd, 0o700)  # explicit, on the folder as opened: a default ACL above would otherwise decide
            except BaseException:
                os.close(fd)
                raise
        return _checked(fd, self.path / name)

    def exists(self, name: str) -> bool:
        try:
            os.stat(name, dir_fd=self.fd, follow_symlinks=False)
            return True
        except FileNotFoundError:
            return False

    def remove_tree(self, name: str) -> None:
        """Remove the folder `name` in this one and everything in it, entirely through open folder descriptors: a
        link inside is removed as a link, never followed."""
        if not _plain_name(name):
            raise HomeError(f"refused: {name!r} is not a plain folder name")
        with self.child(name, create=False) as sub:
            for entry in list(os.scandir(sub.fd)):
                if entry.is_dir(follow_symlinks=False):
                    sub.remove_tree(entry.name)
                else:
                    os.unlink(entry.name, dir_fd=sub.fd)
        os.rmdir(name, dir_fd=self.fd)


def _checked(fd: int, path: Path) -> Owned:
    """An opened folder, kept only when the folder actually opened passes the rule (fstat: the folder itself, not
    whatever has its name by now)."""
    try:
        check_entry(path, os.fstat(fd))
    except BaseException:
        os.close(fd)
        raise
    return Owned(fd, path)


def open_home(home: Path) -> Owned:
    """The app folder itself, opened without following a link. Everything later is done relative to it."""
    if not CONFINED:
        raise HomeError("refused: this system cannot open folders without following links, which Composer needs "
                        "to write and remove safely in its own folder; nothing was written or removed")
    home = Path(os.path.normpath(str(home)))
    check_trust(home)
    try:
        fd = os.open(home, _DIR_FLAGS)
    except OSError:
        raise HomeError(f"refused: {home} is a symbolic link or not a folder; give the real folder") from None
    return _checked(fd, home)


def touch_private(folder: Path, name: str) -> None:
    """Create the file `name` in `folder` (0600) when it is missing, inside the folder as opened and never following
    a link at that name (the run lock: a link planted there would make Composer create a file wherever it names)."""
    if not _plain_name(name):
        raise HomeError(f"refused: {name!r} is not a plain file name")
    flags = os.O_WRONLY | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        if CONFINED:
            with open_home(folder) as at:
                fd = os.open(name, flags, 0o600, dir_fd=at.fd)
        else:
            fd = os.open(Path(folder) / name, flags, 0o600)
    except HomeError:
        raise
    except OSError as exc:
        raise HomeError(f"refused: {Path(folder) / name} cannot be made ({exc.strerror or exc}): it is a symbolic link "
                        "or not a file; nothing was written") from None
    os.close(fd)


def open_owned(home: Path, *parts: str, create: bool = True) -> Owned:
    """<home>/<parts...>, each opened relative to the one above without following links."""
    current = open_home(home)
    try:
        for part in parts:
            nxt = current.child(part, create=create)
            current.close()
            current = nxt
        return current
    except BaseException:
        current.close()
        raise


def check_owned(home: Path) -> None:
    """Refuse an app folder whose own parts lead elsewhere: every folder Composer makes in it (bin, app, python,
    bootstrap, narration, models, cache, tmp and the ones inside them) must be a real folder, not a symbolic link,
    and the only link allowed is app/current, which must name a real app/<version> folder beside it. And refuse one
    where anything in it (every folder, file and link, all the way down) belongs to another account or can be
    written by group or others: an existing install is checked, never adopted as it is. Call it before any write
    or removal in the app folder; it only reads."""
    home = Path(os.path.normpath(str(home)))
    if not check_install_tree(home):
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


def check_install_tree(home: Path) -> bool:
    """The trust rule for an app folder, read-only: no link on its path, it and every folder above it yours or root's
    and writable by no one else, and everything in it (folders, files and links, all the way down) the same. Unlike
    check_owned it does not ask Composer's own folders to be real folders: uninstall removes a link there as a link,
    through the opened folder. False when the folder does not exist."""
    if os.path.islink(home):
        raise HomeError(f"refused: {home} is a symbolic link; give the real folder")
    check_trust(home)
    if not home.exists():
        return False
    try:
        check_tree(home)
    except HomeError as exc:
        raise HomeError(f"{exc}. To fix a whole install made under a permissive umask: chmod -R go-w {home}") from None
    return True


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


def load_manifest(home: Path, *, at: "Owned | None" = None) -> dict:
    """The install manifest; with `at`, read inside the app folder as it was opened (never following a link)."""
    path = home / MANIFEST
    try:
        if at is not None:
            fd = os.open(MANIFEST, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=at.fd)
            with os.fdopen(fd, "r", encoding="utf-8") as handle:
                doc = json.loads(handle.read())
        else:
            doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise HomeError(f"no install manifest at {path}") from None
    except (OSError, json.JSONDecodeError) as exc:
        raise HomeError(f"the install manifest at {path} cannot be read: {exc}") from None
    if not isinstance(doc, dict) or doc.get("schema") != MANIFEST_SCHEMA or not isinstance(doc.get("entries"), list):
        raise HomeError(f"{path} is not a Composer install manifest")
    return doc


def save_manifest(home: Path, doc: dict, *, at: "Owned | None" = None) -> None:
    doc["updated_at"] = now()
    # ensure_ascii=False keeps the folder's name as written, so setup.sh can match it ("home": "<path>")
    text = json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    if at is not None:
        at.write(MANIFEST, text, mode=0o600)  # inside the app folder as it was opened
    else:
        atomic_write(home / MANIFEST, text, mode=0o600)


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
    make_dirs(path.parent)
    tmp = path.with_name("." + path.name + f".{os.getpid()}.tmp")
    try:
        os.unlink(tmp)  # a leftover of that name (or a hard link to a file elsewhere) is never reused
    except FileNotFoundError:
        pass
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), mode)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            if hasattr(os, "fchmod"):
                os.fchmod(handle.fileno(), mode)  # the file as opened, not whatever has its name by now
            os.fsync(handle.fileno())
        if not hasattr(os, "fchmod"):
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
        if CONFINED:
            open_owned(home, name).close()
        else:
            owned_dir(home, name)
