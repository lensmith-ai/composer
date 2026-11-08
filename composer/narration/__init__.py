"""Optional narration: a Listen button and three voices, made on this machine with Kokoro.

Off by default. Turning it on needs about 354 MB of model files (unless a Kokoro you already have passes the
check below) and a small private runtime. Licences: the Kokoro-82M model and voices are Apache-2.0; kokoro-onnx
and onnxruntime are MIT; espeakng-loader 0.2.4 states no licence (its project has since added MIT) and bundles the
eSpeak NG speech library, which is GPL-3.0-or-later (source: https://github.com/espeak-ng/espeak-ng); kokoro-onnx
uses phonemizer-fork, which is GPL-3.0-or-later; soundfile is BSD-3-Clause and bundles libsndfile (LGPL-2.1). The
other packages the runtime needs, numpy among them, are listed with their licences in THIRD-PARTY.md.

Coexisting with a Kokoro you already have:
  - detect() only looks (read-only, bounded in depth and time): KOKORO_MODEL_PATH, kokoro-v1.0 model pairs under
    common folders in your home, the Hugging Face cache, and a Kokoro server on this machine (port 8880).
  - Finding is not reusing. Model files are offered only when their SHA-256 matches the pinned release and a
    test render with all three voices works from the unchanged files. A server is offered only for the exact URL
    you confirm, after it renders all three voices.
  - Reused files are opened read-only and recorded in the install manifest as reused: uninstall never touches
    them. Composer never downloads a second copy without asking, and says how big it is first.

What is read aloud is the brief's own narration script: the model writes it with the brief (a short spoken
version covering the insights and the connection), it is saved as the job's transcript.txt, and the page's
transcript sheet shows the same words. At run time, a brief is narrated after its text is final, one brief at a time, at low priority, capped in length
and time. Any failure leaves the brief text-only with the reason on record; the page then shows the brief with no
dead controls.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlsplit

from .. import tls
from ..home import (CONFINED, HomeError, atomic_write, check_handed, no_group_write, open_owned, owned_dir,
                    private_env)

VOICES = ("af_heart", "am_michael", "bf_emma")
VOICE_LABELS = {"af_heart": "Heart", "am_michael": "Michael", "bf_emma": "Emma"}
MODEL_FILE = "kokoro-v1.0.onnx"
VOICES_FILE = "voices-v1.0.bin"
RELEASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
PINNED = {
    MODEL_FILE: ("7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5", 325532387),
    VOICES_FILE: ("bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d", 28214398),
}
DOWNLOAD_MB = round(sum(size for _, size in PINNED.values()) / 1_000_000)
RUNTIME_MB = 110
RUNTIME_LOCK = Path(__file__).with_name("requirements.lock")
WORKER = Path(__file__).with_name("worker.py")
LICENCES = (
    "Kokoro-82M model and voices: Apache-2.0",
    "kokoro-onnx, onnxruntime: MIT",
    "espeakng-loader: no licence stated in 0.2.4 (its project has since added MIT)",
    "eSpeak NG (bundled inside espeakng-loader): GPL-3.0-or-later, a separate library; "
    "source: https://github.com/espeak-ng/espeak-ng",
    "phonemizer-fork (used by kokoro-onnx): GPL-3.0-or-later",
    "soundfile: BSD-3-Clause, with libsndfile: LGPL-2.1",
    "numpy and the other packages these need: see THIRD-PARTY.md",
)
SERVER_HINTS = ("http://127.0.0.1:8880/v1",)
SEARCH_UNDER = (".cache", "Library/Application Support", "models", "Downloads", "")
SKIP_DIRS = {".git", "node_modules", ".Trash", "Photos Library.photoslibrary", "site-packages"}


class NarrationError(RuntimeError):
    pass


# ------------------------------------------------------------------------------------------------ detection

def detect(*, user_home: Path | None = None, env=None, skip: tuple = (), time_cap_s: float = 10.0,
           max_depth: int = 4, probe_servers: bool = True, opener=None) -> list[dict]:
    """Look for an existing Kokoro without changing anything. Returns candidates:
    {"kind": "files", "model": path, "voices": path, "found_by": ...}, {"kind": "server", "url": ...},
    or {"kind": "unusable", "path": ..., "why": ...}."""
    env = os.environ if env is None else env
    user_home = Path(user_home or Path.home())
    skip_real = {os.path.realpath(p) for p in skip}
    found, seen = [], set()

    def add_pair(folder: Path, how: str, model: Path | None = None):
        model = model or folder / MODEL_FILE
        voices = folder / VOICES_FILE
        if not voices.is_file():
            alt = sorted(folder.glob("voices-v1.0*.bin"))
            voices = alt[0] if alt else voices
        key = (os.path.realpath(model), os.path.realpath(voices))
        if model.is_file() and voices.is_file() and key not in seen:
            seen.add(key)
            found.append({"kind": "files", "model": str(model), "voices": str(voices), "found_by": how})

    raw = env.get("KOKORO_MODEL_PATH", "").strip()
    if raw:
        p = Path(os.path.expanduser(raw))
        if p.is_dir():
            add_pair(p, "KOKORO_MODEL_PATH")
        elif p.is_file():
            vp = env.get("KOKORO_VOICES_PATH", "").strip()
            if vp and Path(vp).is_file():
                key = (os.path.realpath(p), os.path.realpath(vp))
                if key not in seen:
                    seen.add(key)
                    found.append({"kind": "files", "model": str(p), "voices": vp, "found_by": "KOKORO_MODEL_PATH"})
            else:
                add_pair(p.parent, "KOKORO_MODEL_PATH", model=p)

    deadline = time.monotonic() + time_cap_s
    for sub in SEARCH_UNDER:
        root = user_home / sub if sub else user_home
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
            if time.monotonic() > deadline:
                found.append({"kind": "note", "why": f"stopped looking after {time_cap_s:.0f} s"})
                return found
            here = Path(dirpath)
            if os.path.realpath(here) in skip_real:
                dirnames[:] = []
                continue
            depth = len(here.parts) - base_depth
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and depth < max_depth]
            for name in filenames:
                if re.fullmatch(r"kokoro-v1\.0(\.[\w-]+)?\.onnx", name):
                    add_pair(here, "search", model=here / name)
                elif re.fullmatch(r"kokoro.*\.pth", name, re.I):
                    path = str(here / name)
                    if path not in seen:
                        seen.add(path)
                        found.append({"kind": "unusable", "path": path,
                                      "why": "PyTorch weights: found, not usable by this engine"})
    hub = user_home / ".cache" / "huggingface" / "hub"
    if hub.is_dir():
        for folder in sorted(hub.glob("models--*[Kk]okoro*")):
            if str(folder) not in seen:
                seen.add(str(folder))
                found.append({"kind": "unusable", "path": str(folder),
                              "why": "Hugging Face cache entry: a different file layout, not usable by this engine"})
    if probe_servers:
        for url in SERVER_HINTS:
            try:
                voices = server_voices(url, timeout=1.0, opener=opener)
            except NarrationError:
                continue
            found.append({"kind": "server", "url": url, "voices": voices, "found_by": "a server on this machine"})
    return found


# ------------------------------------------------------------------------------------------------ files

def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def check_files(model: str | Path, voices: str | Path) -> tuple[bool, str, dict]:
    """Does this model pair match the pinned release byte for byte? Only reads."""
    info = {}
    for label, path, name in (("model", Path(model), MODEL_FILE), ("voices", Path(voices), VOICES_FILE)):
        want_sha, want_size = PINNED[name]
        if not path.is_file():
            return False, f"{label} file {path} is missing", info
        size = path.stat().st_size
        if size != want_size:
            return False, f"{label} file is {size} bytes, the pinned release is {want_size}", info
        got = sha256_file(path)
        if got != want_sha:
            return False, f"{label} file's SHA-256 does not match the pinned release", info
        info[label] = {"path": str(path), "sha256": got, "size": size}
    return True, "matches the pinned release", info


def _owned(home: Path, *parts: str) -> Path:
    """A folder of Composer's own under home, checked to be real folders all the way down, made when missing."""
    try:
        return owned_dir(home, *parts)
    except HomeError as exc:
        raise NarrationError(str(exc)) from None


def _handed_env(home: Path) -> dict:
    """private_env(home), after checking every folder it hands to the program (TMPDIR, the caches) is still one no
    other account can change."""
    try:
        check_handed(home)
    except HomeError as exc:
        raise NarrationError(str(exc)) from None
    return private_env(home)


def _note(message: str) -> None:
    """Where a note goes when the caller gives no log of its own: standard error, so it is seen, never dropped."""
    print(message, file=sys.stderr, flush=True)


def _remove_owned_tree(home: Path, parts: tuple, name: str, log=_note) -> bool:
    """Remove <home>/<parts>/<name> through open folders; a missing folder is fine. Where folders cannot be opened
    that way (CONFINED is False), nothing is removed by path: the folder is left, with a note. True when removed."""
    if not CONFINED:
        log(f"  left {Path(home).joinpath(*parts, name)}: this system cannot remove it through open folders; "
            "remove it yourself")
        return False
    try:
        with open_owned(home, *parts, create=False) as at:
            if at.exists(name):
                at.remove_tree(name)
                return True
    except (FileNotFoundError, HomeError):
        pass
    return False


def download(home: Path, *, log=print, opener=None) -> tuple[Path, Path]:
    """Download the pinned model pair into <home>/models/kokoro, checking size and SHA-256 before keeping it."""
    target = _owned(home, "models", "kokoro")
    if CONFINED:
        return _download_at(home, target, log=log, opener=opener)
    open_url = opener or tls.urlopen
    for name, (want_sha, want_size) in PINNED.items():
        final = target / name
        if final.is_file() and final.stat().st_size == want_size and sha256_file(final) == want_sha:
            log(f"  {name}: already here and checked")
            continue
        part = target / (name + ".part")
        log(f"  downloading {name} ({want_size / 1_000_000:.0f} MB)")
        h, got = hashlib.sha256(), 0
        try:
            part.unlink(missing_ok=True)  # never reuse (or truncate) an existing .part, which may be a hard link
            fresh = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
            with open_url(RELEASE + name, timeout=60) as resp, os.fdopen(fresh, "wb") as out:
                if not resp.geturl().startswith("https://"):
                    raise NarrationError("the download left HTTPS; stopped")
                while True:
                    block = resp.read(1 << 20)
                    if not block:
                        break
                    got += len(block)
                    if got > want_size:
                        break
                    h.update(block)
                    out.write(block)
        except BaseException:
            part.unlink(missing_ok=True)  # nothing half-downloaded is left behind
            raise
        if got != want_size or h.hexdigest() != want_sha:
            part.unlink(missing_ok=True)
            raise NarrationError(f"{name} did not match its pinned size and SHA-256; nothing was kept")
        os.replace(part, final)
    return target / MODEL_FILE, target / VOICES_FILE


def _download_at(home: Path, target: Path, *, log, opener) -> tuple[Path, Path]:
    """download(), writing only inside the models/kokoro folder as opened (never by path)."""
    open_url = opener or tls.urlopen
    try:
        at = open_owned(home, "models", "kokoro")
    except HomeError as exc:
        raise NarrationError(str(exc)) from None
    with at:
        for name, (want_sha, want_size) in PINNED.items():
            final = target / name
            if final.is_file() and final.stat().st_size == want_size and sha256_file(final) == want_sha:
                log(f"  {name}: already here and checked")
                continue
            part = name + ".part"
            log(f"  downloading {name} ({want_size / 1_000_000:.0f} MB)")
            h, got = hashlib.sha256(), 0
            try:
                # a fresh file every time: whatever has the .part name (a leftover, or a hard link to a file
                # elsewhere) is unlinked, never opened and truncated
                _unlink_at(at.fd, part)
                fd = os.open(part, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=at.fd)
                with open_url(RELEASE + name, timeout=60) as resp, os.fdopen(fd, "wb") as out:
                    if not resp.geturl().startswith("https://"):
                        raise NarrationError("the download left HTTPS; stopped")
                    while True:
                        block = resp.read(1 << 20)
                        if not block:
                            break
                        got += len(block)
                        if got > want_size:
                            break
                        h.update(block)
                        out.write(block)
            except BaseException:
                _unlink_at(at.fd, part)  # nothing half-downloaded is left behind
                raise
            if got != want_size or h.hexdigest() != want_sha:
                _unlink_at(at.fd, part)
                raise NarrationError(f"{name} did not match its pinned size and SHA-256; nothing was kept")
            os.rename(part, name, src_dir_fd=at.fd, dst_dir_fd=at.fd)
    return target / MODEL_FILE, target / VOICES_FILE


def _unlink_at(dir_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=dir_fd)
    except FileNotFoundError:
        pass


# ------------------------------------------------------------------------------------------------ runtime

def runtime_python(home: Path, cfg: dict | None = None) -> Path | None:
    """The interpreter that has the narration runtime: the configured one, <home>/narration/venv, or this
    interpreter when it already has kokoro_onnx (the narration container image)."""
    configured = ((cfg or {}).get("python") or "").strip()
    if configured and Path(configured).is_file():
        return Path(configured)
    for candidate in (home / "narration" / "venv" / "bin" / "python",
                      home / "narration" / "venv" / "Scripts" / "python.exe"):
        if candidate.is_file() and (candidate.parent.parent / ".runtime-ok").is_file():
            return candidate
    if has_runtime_here():
        return Path(sys.executable)
    return None


def has_runtime_here() -> bool:
    import importlib.util
    return all(importlib.util.find_spec(m) is not None for m in ("kokoro_onnx", "soundfile"))


def install_runtime(home: Path, *, log=print, base_python: str | None = None) -> Path:
    """Make <home>/narration/venv and install the hash-locked runtime into it (wheels only)."""
    venv = _owned(home, "narration") / "venv"
    if os.path.islink(venv):
        raise NarrationError(f"refused: {venv} is a symbolic link; nothing was installed")
    env = _handed_env(home)
    made = not venv.exists()
    python = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    try:
        with no_group_write():  # the runtime is made private whatever the umask
            if made:
                log("  making a private environment for narration")
                subprocess.run([base_python or sys.executable, "-m", "venv", str(venv)], check=True, env=env)
            log(f"  installing the narration runtime (about {RUNTIME_MB} MB, hash-checked)")
            subprocess.run([str(python), "-m", "pip", "install", "--quiet", "--require-hashes", "--no-deps",
                            "--only-binary", ":all:", "-r", str(RUNTIME_LOCK)], check=True, env=env)
            subprocess.run([str(python), "-I", "-c", "import kokoro_onnx, soundfile"], check=True, env=env,
                           capture_output=True)
            atomic_write(venv / ".runtime-ok", "installed from requirements.lock\n", mode=0o600)
    except (subprocess.CalledProcessError, OSError) as exc:
        if made:
            _remove_owned_tree(home, ("narration",), "venv", log)  # a half-made runtime would look installed
        raise NarrationError(f"the narration runtime did not install ({exc})") from None
    return python


def run_worker(python: Path, request: dict, *, home: Path, timeout: float) -> dict:
    """Run worker.py in the narration runtime; its JSON answer, or NarrationError with a short reason."""
    _owned(home, "tmp")
    env = _handed_env(home)
    try:  # the worker lowers its own priority (forking hooks are unsafe in a threaded server)
        proc = subprocess.run([str(python), "-I", str(WORKER)], input=json.dumps({**request, "nice": 10}),
                              capture_output=True, text=True, timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise NarrationError(f"narration took longer than {timeout:.0f} s and was stopped") from None
    except OSError as exc:
        raise NarrationError(f"the narration runtime could not start: {exc.strerror or exc}") from None
    lines = [ln for ln in (proc.stdout or "").splitlines() if ln.strip().startswith("{")]
    if not lines:
        tail = (proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
        raise NarrationError(f"the narration runtime failed: {tail[0][:200]}")
    answer = json.loads(lines[-1])
    if proc.returncode != 0 or not answer.get("ok"):
        raise NarrationError(answer.get("error") or f"the narration runtime said no ({answer})"[:200])
    return answer


def check_render(python: Path, model: str, voices: str, *, home: Path, timeout: float = 120, log=_note) -> dict:
    """The capability check: load the pair, then render one sentence with each of the three voices."""
    work = _owned(home, "tmp", "narration-check")
    try:
        req = {"mode": "check", "model": str(model), "voices": str(voices), "out_dir": str(work), "want": list(VOICES)}
        env = _handed_env(home)
        proc = subprocess.run([str(python), "-I", str(WORKER)], input=json.dumps(req), capture_output=True,
                              text=True, timeout=timeout, env=env)
        lines = [ln for ln in proc.stdout.splitlines() if ln.strip().startswith("{")]
        if not lines:
            tail = (proc.stderr or "").strip().splitlines()[-1:] or ["no output"]
            raise NarrationError(f"the test render failed: {tail[0][:200]}")
        return json.loads(lines[-1])
    except subprocess.TimeoutExpired:
        raise NarrationError(f"the test render took longer than {timeout:.0f} s") from None
    finally:
        _remove_owned_tree(home, ("tmp",), "narration-check", log)


# ------------------------------------------------------------------------------------------------ server engine

def checked_server_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or parts.hostname not in ("127.0.0.1", "localhost", "::1"):
        raise NarrationError("a Kokoro server must be on this machine (http://127.0.0.1:PORT/v1)")
    if parts.query or parts.fragment or parts.username or parts.password:
        raise NarrationError("give the server's base address only, such as http://127.0.0.1:8880/v1")
    return url.strip().rstrip("/")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise NarrationError("the server answered with a redirect; refused")


_OPENER = urllib.request.build_opener(_NoRedirect(), tls.HTTPSHandler())


def server_voices(url: str, *, timeout: float = 5.0, opener=None) -> list[str]:
    base = checked_server_url(url)
    try:
        with (opener or _OPENER).open(base + "/audio/voices", timeout=timeout) as resp:
            doc = json.loads(resp.read(1 << 20).decode("utf-8"))
    except (OSError, ValueError, urllib.error.URLError) as exc:
        raise NarrationError(f"no Kokoro server answered at {base}: {exc}"[:200]) from None
    voices = doc.get("voices") if isinstance(doc, dict) else doc
    if not isinstance(voices, list):
        raise NarrationError("the server's voice list is not in the expected shape")
    return sorted(v if isinstance(v, str) else str(v.get("id") or v.get("name")) for v in voices)


def server_render(url: str, voice: str, text: str, out_base: Path, *, timeout: float, opener=None) -> dict:
    base = checked_server_url(url)
    body = json.dumps({"model": "kokoro", "input": text, "voice": voice, "response_format": "mp3"}).encode()
    req = urllib.request.Request(base + "/audio/speech", data=body, method="POST",
                                 headers={"Content-Type": "application/json"})
    started = time.monotonic()
    try:
        with (opener or _OPENER).open(req, timeout=timeout) as resp:
            data = resp.read(200 * 1024 * 1024)
    except (OSError, urllib.error.URLError) as exc:
        raise NarrationError(f"the Kokoro server did not render: {exc}"[:200]) from None
    if not data or not (data[:3] == b"ID3" or data[:1] == b"\xff"):
        raise NarrationError("the Kokoro server's answer is not MP3 audio")
    path = Path(str(out_base) + ".mp3")
    path.unlink(missing_ok=True)  # a fresh file, never an existing one (or a hard link) truncated
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
    return {"ok": True, "file": str(path), "format": "mp3", "seconds": round(time.monotonic() - started, 2)}


def check_server(url: str, *, home: Path, timeout: float = 60, opener=None, log=_note) -> dict:
    voices = server_voices(url, opener=opener)
    missing = [v for v in VOICES if v not in voices]
    rendered = []
    work = _owned(home, "tmp", "narration-check")
    try:
        for voice in VOICES:
            if voice in voices:
                out = server_render(url, voice, "Composer checks this voice.", work / f"check-{voice}",
                                    timeout=timeout, opener=opener)
                Path(out["file"]).unlink(missing_ok=True)
                rendered.append(voice)
    finally:
        _remove_owned_tree(home, ("tmp",), "narration-check", log)
    return {"ok": not missing, "rendered": rendered, "missing": missing}


# ------------------------------------------------------------------------------------------------ text

TEXT_BYTE_BUDGET = 120_000
TRUNCATION_MARKER = " \u2026[trimmed to audio byte budget]"


def canonical_words(text: str) -> tuple:
    return tuple(re.findall(r"\S+", (text or "").lower()))


def prepare_text(transcript: str, budget: int = TEXT_BYTE_BUDGET) -> tuple[str, str, bool]:
    """The one text that crosses into the speech engine, from the brief's own narration script (the
    `transcript` the model writes with the brief, the same script the page's transcript sheet shows).
    Returns (display_text, render_text, truncated): whitespace is collapsed for the engine; when the script
    is over the byte budget it is cut at a word and marked, and the display text becomes that same prefix.
    The words shown and the words rendered are always the same words."""
    render = re.sub(r"\s+", " ", transcript or "").strip()
    encoded = render.encode("utf-8")
    truncated = len(encoded) > budget
    if truncated:
        trimmed = encoded[:budget].decode("utf-8", errors="ignore").rsplit(" ", 1)[0].strip()
        if len((trimmed + TRUNCATION_MARKER).encode("utf-8")) <= budget:
            trimmed += TRUNCATION_MARKER
        render = trimmed
    display = render if truncated else (transcript or "").strip()
    if canonical_words(display) != canonical_words(render):
        raise NarrationError("the shown and the rendered words differ")
    return display, render, truncated


# ------------------------------------------------------------------------------------------------ run time

def options_fragment(cfg: dict) -> dict:
    """What the page reads to show or hide narration (options.json): voices [] or narration.enabled false
    hides the voice picker and the player; nothing is left that cannot work."""
    n = (cfg or {}).get("narration") or {}
    on = bool(n.get("enabled")) and n.get("engine") in ("kokoro-onnx", "kokoro-http") and bool(n.get("voices"))
    return {"voices": list(n.get("voices") or []) if on else [],
            "voice_labels": {v: VOICE_LABELS[v] for v in (n.get("voices") or []) if v in VOICE_LABELS} if on else {},
            "narration": {"enabled": on, "engine": n.get("engine") if on else "none"}}


class Narrator:
    """One background worker: narrates finished briefs one at a time. Hook it to the job store with
    JobStore(on_finished=narrator.on_finished)."""

    FINAL = ("verified", "verification_failed")

    def __init__(self, cfg: dict, home: Path, *, render=None):
        self.cfg = dict(cfg or {})
        self.home = home
        self.store = None
        self._render = render or self._render_with_engine
        self.queue: queue.Queue = queue.Queue()
        self.seen: set[str] = set()
        self.lock = threading.Lock()
        self.thread = threading.Thread(target=self._loop, name="narration", daemon=True)
        self.thread.start()

    def attach(self, store) -> "Narrator":
        self.store = store
        return self

    @property
    def enabled(self) -> bool:
        return options_fragment({"narration": self.cfg})["narration"]["enabled"]

    def on_finished(self, job_id: str) -> None:
        job = self.store.status(job_id)
        if job.get("phase") not in self.FINAL or not isinstance(job.get("result"), dict):
            return
        with self.lock:
            if job_id in self.seen or job.get("audio_state") in ("generating", "ready"):
                return
            self.seen.add(job_id)
        if not self.enabled:
            self.store.set_audio(job_id, {"state": "off"})
            return
        voices = list(self.cfg.get("voices") or [])
        voice = (job.get("request") or {}).get("voice")
        voice = voice if voice in voices else voices[0]
        self.store.set_audio(job_id, {"state": "generating", "voice": voice})
        self.queue.put((job_id, voice))

    def wait_idle(self, timeout: float = 30) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.queue.unfinished_tasks == 0:
                return True
            time.sleep(0.02)
        return False

    def _loop(self) -> None:
        while True:
            job_id, voice = self.queue.get()
            try:
                self._one(job_id, voice)
            finally:
                self.queue.task_done()

    def _one(self, job_id: str, voice: str) -> None:
        started = time.monotonic()
        folder = self.store.job_dir(job_id)
        base = folder / f".narration-{voice}"
        try:
            job = self.store.status(job_id)
            script = job["result"].get("transcript") if isinstance(job["result"], dict) else None
            if not isinstance(script, str) or not script.strip():
                raise NarrationError("this brief has no narration script")
            _, text, truncated = prepare_text(script, int(self.cfg.get("max_bytes", TEXT_BYTE_BUDGET)))
            answer = self._render(text=text, voice=voice, out_base=base,
                                  timeout=float(self.cfg.get("max_seconds", 600)))
            produced = Path(answer["file"])
            fmt = answer.get("format")
            if fmt not in ("mp3", "wav") or produced.parent != folder or not produced.is_file() \
                    or produced.stat().st_size == 0:
                raise NarrationError("the engine reported audio that is not there")
            final = folder / f"composer-{voice}.{fmt}"
            os.replace(produced, final)
            self.store.set_audio(job_id, {"state": "ready", "voice": voice, "file": final.name, "format": fmt,
                                          "chars": len(text), "truncated": truncated,
                                          "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                                          "seconds": round(time.monotonic() - started, 1)})
        except Exception as exc:  # any failure: the brief stays text-only, with the reason on record
            for leftover in folder.glob(f".narration-{voice}.*"):
                leftover.unlink(missing_ok=True)
            reason = str(exc) if isinstance(exc, NarrationError) else f"narration failed ({type(exc).__name__})"
            try:
                self.store.set_audio(job_id, {"state": "failed", "voice": voice, "reason": reason[:200]})
            except Exception:
                pass

    def _render_with_engine(self, *, text: str, voice: str, out_base: Path, timeout: float) -> dict:
        engine = self.cfg.get("engine")
        if engine == "kokoro-http":
            return server_render(self.cfg.get("url", ""), voice, text, out_base, timeout=timeout)
        if engine == "kokoro-onnx":
            python = runtime_python(self.home, self.cfg)
            if python is None:
                raise NarrationError("the narration runtime is not installed; run `composer setup --reconfigure narration`")
            return run_worker(python, {"mode": "render", "model": self.cfg.get("model_path"),
                                       "voices": self.cfg.get("voices_path"), "voice": voice, "text": text,
                                       "out": str(out_base)}, home=self.home, timeout=timeout)
        raise NarrationError("narration is off")
