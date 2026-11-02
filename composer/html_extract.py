"""Optional HTML extraction tiers. Native is always available; trafilatura is an optional install.

There is one way to install it: from the hash-locked composer/extraction-requirements.lock, with every package
pinned, every file's SHA-256 checked and wheels only. Say yes to the article parser question in `composer setup` (or
`composer setup --reconfigure parser`), which runs that install in Composer's own environment; by hand it is
`python -m pip install --require-hashes --no-deps --only-binary :all: -r composer/extraction-requirements.lock`.
There is deliberately no pip extra for it: an extra would pin the parser but let pip pick the packages it needs. Without it, an html-index source that asks for trafilatura is
read with the built-in parser (text only), and its receipt says so.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

from .adapters import html_index

LOCK = "extraction-requirements.lock"


class ExtractionError(ValueError):
    """The requested extraction tier is unavailable or invalid."""


def trafilatura_installed() -> bool:
    return importlib.util.find_spec("trafilatura") is not None


def lock_path() -> Path:
    return Path(__file__).with_name(LOCK)


def install_trafilatura(*, python: str | None = None, env: dict | None = None, log=print) -> None:
    """Install the parser into Composer's own environment from the hash-locked file: wheels only, every file's
    SHA-256 checked, nothing resolved beyond the file. Raises ExtractionError if anything fails."""
    python = python or sys.executable
    log("  installing the optional article parser (trafilatura and the packages it needs, hash-checked)")
    try:
        subprocess.run([python, "-m", "pip", "install", "--quiet", "--require-hashes", "--no-deps",
                        "--only-binary", ":all:", "-r", str(lock_path())], check=True, env=env)
        subprocess.run([python, "-I", "-c", "import trafilatura"], check=True, env=env, capture_output=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        raise ExtractionError(f"the article parser did not install ({exc})") from None


def available_tiers() -> dict:
    return {"native": "available", "trafilatura": "available" if trafilatura_installed() else "unavailable"}


def extract(markup: str, *, tier: str = "native") -> tuple[str, str]:
    if tier == "native":
        return html_index.extract(markup)
    if tier != "trafilatura":
        raise ExtractionError("extraction tier must be native or trafilatura")
    try:
        import trafilatura
    except ImportError:
        raise ExtractionError("trafilatura extraction is not enabled") from None
    markup = markup[:html_index.MARKUP_CAP]
    text = trafilatura.extract(markup, include_comments=False, include_tables=False) or ""
    title, fallback = html_index.extract(markup)
    text = " ".join(text.split())[:html_index.DESC_CAP]
    return title, text or fallback
