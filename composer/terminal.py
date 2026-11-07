"""What Composer prints on a terminal: the address of the app on a line of its own, and progress while a brief is
composed. Plain text first: a macOS Terminal makes a plain http:// address Cmd+clickable, so the address is never
wrapped in anything that could hide it. Terminals known to understand OSC 8 links get one around the same visible
address; everything else (a pipe, a log file, `docker logs`, an unknown terminal) gets the address alone."""
from __future__ import annotations

import os
import re
import sys
import threading
import time

_LOCK = threading.Lock()  # one for the whole process: two briefs composing at once must not mix their lines
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f\u202a-\u202e\u2066-\u2069]")  # escape sequences in a source's name or an error text never reach a terminal
OSC8_TERMINALS = {"iTerm.app", "WezTerm", "vscode", "ghostty", "Hyper", "rio"}


def supports_links(stream=None, environ=None) -> bool:
    """True only for a real terminal that is known to draw OSC 8 hyperlinks (set COMPOSER_NO_HYPERLINKS=1 to turn
    this off). Terminal.app is not on the list: its plain-address Cmd+click works without it."""
    stream = stream if stream is not None else sys.stdout
    env = os.environ if environ is None else environ
    if env.get("COMPOSER_NO_HYPERLINKS", "").strip() == "1" or env.get("TERM", "") in ("", "dumb"):
        return False
    try:
        if not stream.isatty():
            return False
    except (AttributeError, ValueError):
        return False
    if env.get("TERM_PROGRAM", "") in OSC8_TERMINALS or env.get("KITTY_WINDOW_ID") or env.get("WT_SESSION"):
        return True
    try:
        return int(env.get("VTE_VERSION", "0")) >= 5000
    except ValueError:
        return False


def link(url: str, *, stream=None, environ=None) -> str:
    """The address as it is printed: the same visible text, inside an OSC 8 link where the terminal draws them."""
    if supports_links(stream, environ):
        return f"\x1b]8;;{url}\x1b\\{url}\x1b]8;;\x1b\\"
    return url


def open_line(url: str, *, stream=None, environ=None) -> str:
    """`Open: http://127.0.0.1:8765/` (one line, nothing after the address)."""
    return f"Open: {link(url, stream=stream, environ=environ)}"


def app_url(host: str, port: int, *, public_origin: str = "") -> str | None:
    """The address to open for a server bound to host:port, or None when no address is certain to work from the
    computer the person is sitting at (bound to every interface, as in a container)."""
    if public_origin:
        return public_origin.rstrip("/") + "/"
    if host in ("127.0.0.1", "localhost"):
        return f"http://127.0.0.1:{port}/"
    if host in ("0.0.0.0", "::", ""):
        return None
    return f"http://[{host}]:{port}/" if ":" in host else f"http://{host}:{port}/"


class ComposeProgress:
    """Turns the pipeline's events into a few numbered terminal lines:
    Step 1 of 4 (reading the sources), 2 (writing), 3 (checking each claim), 4 (done).
    Printing is a courtesy: a closed or broken output never stops or changes the brief."""

    def __init__(self, sources: int | None = None, *, write=None, clock=time.localtime):
        self.sources = sources
        self.write = write or (lambda text: print(text, flush=True))
        self.clock = clock

    def _say(self, text: str) -> None:
        text = _CONTROL.sub("?", text)
        try:
            with _LOCK:
                self.write(text)
        except (OSError, ValueError):  # a closed stdout (launchd, a dead pipe), or a stream already closed
            pass

    def _step(self, n: int, text: str) -> None:
        self._say(f"[{time.strftime('%H:%M:%S', self.clock())}] Step {n} of 4: {text}")

    def __call__(self, kind: str, text: str) -> None:
        if kind == "run.started":
            n = self.sources
            self._step(1, f"reading {n} source{'s' if n != 1 else ''}" if n is not None else "reading the sources")
        elif kind == "lens.started":
            self._step(2, "writing the brief under your lens (the model call can take a minute)")
        elif kind == "claim.verifying":
            self._step(3, "checking each claim against the articles it cites")
        elif kind == "claim.verified":
            self._step(4, f"done · {text.removeprefix('checked · ')}")
        else:
            self._say(f"  {text}")

    def failed(self, exc: BaseException) -> None:
        self._say(f"[{time.strftime('%H:%M:%S', self.clock())}] The brief could not be made: {str(exc)[:300]}")


def with_progress(compose, *, write=None):
    """`pipeline.compose` with its events (and a failure's reason) also printed on the terminal."""
    def wrapped(**kw):
        progress = ComposeProgress(len(kw.get("sources") or ()), write=write)
        inner = kw.get("log")

        def both(kind, text):
            try:
                progress(kind, text)
            except Exception:  # noqa: BLE001  (a bug in the printing must never stop a brief)
                pass
            if inner is not None:
                inner(kind, text)
        kw["log"] = both
        try:
            return compose(**kw)
        except Exception as exc:
            try:
                progress.failed(exc)
            except Exception:  # noqa: BLE001
                pass
            raise
    return wrapped
