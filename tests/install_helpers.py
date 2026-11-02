"""Helpers for the install tests: a throwaway HOME, tree snapshots, and fake narration engines."""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401  (temporary folders the app folder checks can trust)

CLEAR = ("COMPOSER_HOME", "COMPOSER_DATA", "KOKORO_MODEL_PATH", "KOKORO_VOICES_PATH", "ANTHROPIC_API_KEY",
         "OPENAI_API_KEY", "COMPOSER_PROVIDER", "COMPOSER_MODEL", "COMPOSER_SOURCES", "COMPOSER_TRUSTED_PROXY",
         "COMPOSER_PUBLIC_ORIGIN", "COMPOSER_SERVER_PASS", "COMPOSER_CHECKER_API_KEY", "COMPOSER_CHECKER_PROVIDER",
         "COMPOSER_CHECKER_MODEL", "COMPOSER_CHECKER_OPENAI_BASE_URL")
FAKE_KEY = "test-key-value-for-setup-only"


@contextmanager
def fake_home(**extra_env):
    """A temporary HOME (and nothing from the real one): yields its Path."""
    root = Path(tempfile.mkdtemp(prefix="composer-home-"))
    home = root / "home"
    home.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items() if k not in CLEAR}
    # test mode: a `composer setup` started here makes no test call to a model service
    env.update({"HOME": str(home), "COMPOSER_NO_TEST_CALL": "1"}, **extra_env)
    try:
        with mock.patch.dict(os.environ, env, clear=True):
            yield home
    finally:
        shutil.rmtree(root, ignore_errors=True)


def snapshot(root: Path, skip: Path | None = None) -> dict:
    """{relative path: (kind, sha256 or link target, mode, mtime_ns)} for everything under root."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if skip is not None and (here == skip or skip in here.parents):
            dirnames[:] = []
            continue
        for name in sorted(dirnames + filenames):
            path = here / name
            if skip is not None and path == skip:
                continue
            st = os.lstat(path)
            rel = str(path.relative_to(root))
            if os.path.islink(path):
                out[rel] = ("link", os.readlink(path), st.st_mode, st.st_mtime_ns)
            elif path.is_dir():
                out[rel] = ("dir", None, st.st_mode, st.st_mtime_ns)
            else:
                out[rel] = ("file", hashlib.sha256(path.read_bytes()).hexdigest(), st.st_mode, st.st_mtime_ns)
    if skip is None:  # with a skipped folder inside, the root's own mtime changes when that folder is made
        st = os.lstat(root)
        out["."] = ("dir", None, st.st_mode, st.st_mtime_ns)
    return out


def fake_model_pair(folder: Path) -> tuple[Path, Path, dict]:
    """Two small files standing in for the Kokoro pair, and the PINNED table that matches them."""
    from composer import narration as N
    folder.mkdir(parents=True, exist_ok=True)
    model, voices = folder / N.MODEL_FILE, folder / N.VOICES_FILE
    model.write_bytes(b"fake onnx model bytes " * 64)
    voices.write_bytes(b"fake voices bytes " * 32)
    pinned = {N.MODEL_FILE: (hashlib.sha256(model.read_bytes()).hexdigest(), model.stat().st_size),
              N.VOICES_FILE: (hashlib.sha256(voices.read_bytes()).hexdigest(), voices.stat().st_size)}
    return model, voices, pinned


class FakeRender:
    """A narration engine that writes the exact text it was given into the "audio" file, so a test can compare
    what was rendered with what the page shows. fail=True raises instead."""

    def __init__(self, fail: bool = False, fmt: str = "mp3"):
        self.fail = fail
        self.fmt = fmt
        self.calls = []

    def __call__(self, *, text, voice, out_base, timeout):
        self.calls.append({"text": text, "voice": voice, "timeout": timeout})
        if self.fail:
            from composer.narration import NarrationError
            raise NarrationError("the engine crashed (test)")
        path = Path(str(out_base) + "." + self.fmt)
        path.write_bytes(b"ID3" + text.encode("utf-8"))
        return {"ok": True, "file": str(path), "format": self.fmt}


def fake_check(python, model, voices, *, home):
    """A capability check that opens both files read-only, as the real one does, and reports all voices."""
    from composer import narration as N
    with open(model, "rb") as a, open(voices, "rb") as b:
        a.read(16), b.read(16)
    return {"ok": True, "rendered": list(N.VOICES), "missing": []}
