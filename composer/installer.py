"""`composer setup`: the questions, then the install. Nothing is written until every answer is in and every
guard has passed.

  composer setup                         ask, one question at a time, with a default in [brackets]
  composer setup --answers answers.toml  no questions (see composer/answers.py for the format)
  composer setup --yes                   no questions, every default (text-only, no daily brief, no key yet)
  composer setup --reconfigure narration re-ask one part: provider, checker, sources, parser, narration, schedule
                                         or port
  composer setup --data-only             only settings and key, in the data folder (inside the container)

What it creates lives in the app folder (default ~/.lensmith-composer) and is listed in its install manifest.
It never edits your shell profile, PATH, login items, Homebrew or a global Python; it prints the one line you
can add yourself to run `composer` from anywhere.
"""
from __future__ import annotations

import getpass
import json
import os
import shlex
import socket
import sys
from pathlib import Path

from . import __version__, answers as A
from . import home as H
from . import narration as N
from . import settings as S

SECTIONS = ("provider", "checker", "sources", "parser", "narration", "schedule", "port")
HN_ENTRY = {"id": "hn", "label": "Hacker News", "kind": "hn-json-api",
            "url": "https://hacker-news.firebaseio.com/v0/topstories.json", "max_items": 10}


class SetupError(RuntimeError):
    pass


class Asker:
    """Questions on a terminal, or answers from a file / defaults. Every question has a default."""

    def __init__(self, answers: dict | None, interactive: bool, out=print, read=input, secret=getpass.getpass):
        self.answers = answers or {}
        self.interactive = interactive
        self.out = out
        self.read = read
        self.secret = secret

    def given(self, section: str, key: str, default=None):
        return self.answers.get(section, {}).get(key, default)

    def ask(self, question: str, default: str) -> str:
        if not self.interactive:
            return default
        got = self.read(f"{question} [{default}]: ").strip()
        return got or default

    def yes(self, question: str, default: bool) -> bool:
        if not self.interactive:
            return default
        while True:
            got = self.read(f"{question} [{'Y/n' if default else 'y/N'}]: ").strip().lower()
            if not got:
                return default
            if got in ("y", "yes", "n", "no"):
                return got.startswith("y")
            self.out("  please answer y or n")

    def choose(self, question: str, options: list[tuple[str, str]], default: str) -> str:
        if not self.interactive:
            return default
        self.out(question)
        for n, (key, label) in enumerate(options, 1):
            self.out(f"  {n}) {label}")
        keys = [k for k, _ in options]
        while True:
            got = self.read(f"choose 1-{len(options)} [{keys.index(default) + 1}]: ").strip()
            if not got:
                return default
            if got.isdigit() and 1 <= int(got) <= len(options):
                return keys[int(got) - 1]
            self.out("  please type one of the numbers")


def port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def next_free_port(start: int = 8765) -> int:
    for port in range(start, start + 50):
        if port_free(port):
            return port
    return start


# ------------------------------------------------------------------------------------------------ questions

MODELS_FILE = Path(__file__).with_name("data") / "models.json"


def model_choices(kind: str) -> dict:
    """The ids setup offers for a service, from composer/data/models.json (edit that file to change them)."""
    doc = json.loads(MODELS_FILE.read_text(encoding="utf-8"))
    entry = doc.get(kind) or {}
    return {"default": entry.get("default") or "", "models": list(entry.get("models") or []),
            "note": entry.get("note") or ""}


def ask_model(q: Asker, section: str, kind: str, who: str = "") -> str:
    """A short numbered list of common ids for the service, plus "type another"; an answers file takes any id."""
    given = q.given(section, "model")
    if given:
        return given
    choices = model_choices(kind)
    prefix = f"{who.capitalize()} model" if who else "Model"
    if choices["models"]:
        options = [(m, m + (" (default)" if m == choices["default"] else "")) for m in choices["models"]]
        picked = q.choose(f"Which {who + ' ' if who else ''}model?", options + [("other", "type another model id")],
                          choices["default"] or choices["models"][0])
        if picked != "other":
            return picked
        return q.ask(f"{prefix} id", choices["default"]).strip()
    if q.interactive and choices["note"]:
        q.out(f"  {choices['note']}")
    return q.ask(f"{prefix} id", choices["default"]).strip()


def run_test_call(q: Asker, plan: dict, cfg: dict, key: str | None, who: str) -> bool:
    """One tiny call with the key just given. True to go on; False when the person wants to enter them again."""
    test = plan.get("test_call")
    if test is None or not key or cfg["kind"] not in ("anthropic", "openai"):
        return True
    ok, said = test(cfg["kind"], cfg["model"], cfg["base_url"], key)
    q.out(f"  test call ({who}): {said}")
    if ok or not q.interactive:
        if not ok:
            q.out("  keeping these settings; composing will fail until this is fixed")
        return True
    return not q.yes("Enter the model and key again?", True)


def ask_provider(q: Asker, plan: dict) -> None:
    while True:
        _ask_provider_once(q, plan)
        p = plan["provider"]
        key = plan["secret"] or (os.environ.get(p["key_env"], "").strip() if p["key"] == "env" else "")
        if run_test_call(q, plan, p, key, "writer"):
            return


def _ask_provider_once(q: Asker, plan: dict) -> None:
    kind = q.given("provider", "kind") or q.choose(
        "Which model writes and checks your briefs?",
        [("anthropic", "Anthropic (default model claude-sonnet-5-5)"),
         ("openai", "an OpenAI-compatible endpoint (OpenAI, OpenRouter, a local Ollama or LM Studio server)"),
         ("none", "skip this (the app shows the recorded brief; composing needs a model)")], "anthropic")
    if kind not in ("anthropic", "openai", "none"):
        raise SetupError(f"[provider] kind must be anthropic, openai or none, not {kind!r}")
    p = {"kind": kind, "model": "", "base_url": "", "key": "none",
         "key_env": "OPENAI_API_KEY" if kind == "openai" else "ANTHROPIC_API_KEY"}
    if kind == "anthropic":
        p["model"] = ask_model(q, "provider", "anthropic")
    elif kind == "openai":
        p["base_url"] = q.given("provider", "base_url") or q.ask("Endpoint base URL", "https://api.openai.com/v1")
        p["model"] = ask_model(q, "provider", "openai")
        if not p["model"]:
            raise SetupError("an OpenAI-compatible endpoint needs a model id")
        from .providers import ProviderError, checked_endpoint
        try:
            checked_endpoint(p["base_url"])
        except ProviderError as exc:
            raise SetupError(str(exc)) from None
    secret = None
    if kind != "none":
        from_env = q.given("provider", "key_from_env")
        mode = q.given("provider", "key")
        if from_env:
            if from_env not in S.WRITER_KEY_NAMES:
                raise SetupError(f"[provider] key_from_env must be one of {', '.join(S.WRITER_KEY_NAMES)}")
            secret = os.environ.get(from_env, "").strip()
            if not secret:
                raise SetupError(f"[provider] key_from_env names {from_env}, but it is not set")
            p["key"], p["key_env"] = "stored", from_env
        elif mode in ("env", "none"):
            p["key"] = mode
        elif q.interactive:
            q.out(f"Paste your key. Nothing is shown while you paste, and it is stored only in "
                  f"{plan['data']}/secrets.env (mode 0600).")
            q.out(f"Press Enter instead to keep using the {p['key_env']} environment variable.")
            secret = q.secret("key: ").strip()
            if secret:
                p["key"] = "stored"
            else:
                p["key"] = "env"
                if not os.environ.get(p["key_env"]):
                    q.out(f"  note: {p['key_env']} is not set now; composing will ask for it")
    plan["provider"], plan["secret"] = p, secret


def ask_checker(q: Asker, plan: dict, writer_kind: str) -> None:
    while True:
        _ask_checker_once(q, plan, writer_kind)
        c = plan["checker"]
        if c["same"]:
            return
        key = plan["checker_secret"] or (os.environ.get(S.CHECKER_KEY, "").strip() if c["key"] == "env" else "")
        if run_test_call(q, plan, c, key, "checker"):
            return


def _ask_checker_once(q: Asker, plan: dict, writer_kind: str) -> None:
    """The model that checks the claims: the writer's own (the default), or a separate one with its own key, stored
    under its own name. A different model can catch mistakes the writer would make again when checking itself."""
    same = {"same": True, "kind": "anthropic", "model": "", "base_url": "", "key": "none", "key_env": S.CHECKER_KEY}
    given = q.answers.get("checker")
    if writer_kind == "none" and not given:
        plan["checker"], plan["checker_secret"] = same, None
        return
    if q.answers or not q.interactive:
        if not given or given.get("kind") in (None, "same"):
            plan["checker"], plan["checker_secret"] = same, None
            return
    elif q.yes("Check claims with the same model?", True):
        plan["checker"], plan["checker_secret"] = same, None
        return
    kind = q.given("checker", "kind") or q.choose(
        "Which model checks the claims?",
        [("anthropic", "Anthropic (default model claude-sonnet-5-5)"),
         ("openai", "an OpenAI-compatible endpoint (OpenAI, OpenRouter, a local Ollama or LM Studio server)")],
        "anthropic")
    if kind not in ("anthropic", "openai"):
        raise SetupError(f"[checker] kind must be anthropic, openai or same, not {kind!r}")
    c = dict(same, same=False, kind=kind)
    if kind == "anthropic":
        c["model"] = ask_model(q, "checker", "anthropic", "checker")
    else:
        c["base_url"] = q.given("checker", "base_url") or q.ask("Checker endpoint base URL",
                                                                 "https://api.openai.com/v1")
        c["model"] = ask_model(q, "checker", "openai", "checker")
        if not c["model"]:
            raise SetupError("an OpenAI-compatible checker needs a model id")
        from .providers import ProviderError, checked_endpoint
        try:
            checked_endpoint(c["base_url"])
        except ProviderError as exc:
            raise SetupError(str(exc)) from None
    secret = None
    from_env, mode = q.given("checker", "key_from_env"), q.given("checker", "key")
    if from_env:
        # only the checker's own variable: naming the writer's key here would send the writer's credential to
        # whatever endpoint the checker names (and store it as the checker's key)
        if from_env != S.CHECKER_KEY:
            raise SetupError(f"[checker] key_from_env must be {S.CHECKER_KEY}; the writer's key is never sent to "
                             "the checker")
        secret = os.environ.get(from_env, "").strip()
        if not secret:
            raise SetupError(f"[checker] key_from_env names {from_env}, but it is not set")
        c["key"] = "stored"
    elif mode in ("env", "none"):
        c["key"] = mode
    elif q.interactive:
        q.out(f"Paste the checker's key. Nothing is shown while you paste; it is stored in {plan['data']}/secrets.env "
              f"(mode 0600) as {S.CHECKER_KEY}, apart from the writer's key.")
        q.out(f"Press Enter instead to keep using the {S.CHECKER_KEY} environment variable.")
        secret = q.secret("checker key: ").strip()
        c["key"] = "stored" if secret else "env"
        if not secret and not os.environ.get(S.CHECKER_KEY):
            q.out(f"  note: {S.CHECKER_KEY} is not set now; composing will ask for it")
    plan["checker"], plan["checker_secret"] = c, secret


def ask_sources(q: Asker, plan: dict, get=None) -> None:
    add = []
    if q.given("sources", "hacker_news", None) is True or (
            q.given("sources", "hacker_news", None) is None and q.yes("Add Hacker News as a source too?", False)):
        add.append(dict(HN_ENTRY))
    for url in list(q.given("sources", "add", []) or []):
        add.append(probe_feed(q, url, get=get))
    if q.interactive and not q.answers:
        while True:
            url = q.ask("Add your own feed? Paste its address, or press Enter to skip", "").strip()
            if not url:
                break
            try:
                add.append(probe_feed(q, url, get=get))
            except SetupError as exc:
                q.out(f"  not added: {exc}")
    plan["sources_add"] = add


def probe_feed(q: Asker, url: str, get=None) -> dict:
    from . import adapters
    from .fetch import http_get
    from .registry import RegistryError, parse_entry
    from urllib.parse import urlsplit
    host = (urlsplit(url).hostname or "feed").removeprefix("www.")
    sid = "".join(c if c.isalnum() else "-" for c in host.lower()).strip("-")[:30] or "feed"
    raw = {"id": sid, "label": host, "kind": "rss-or-atom", "url": url, "max_items": 5}
    try:
        entry = parse_entry(raw)
        items, receipt = adapters.fetch(entry, get or http_get)
    except (RegistryError, ValueError, OSError) as exc:
        raise SetupError(f"{url}: {exc}") from None
    if receipt.get("status") != "ok" or not items:
        raise SetupError(f"{url} did not read as a feed ({receipt.get('error') or receipt.get('status')})")
    q.out(f"  read {len(items)} items from {host}, for example: {items[0]['title'][:70]}")
    if not q.yes(f"Add {host} as a source?", True):
        raise SetupError("not added")
    return raw


def ask_parser(q: Asker, plan: dict) -> None:
    """The optional article parser (trafilatura) for news pages without a feed. Off unless asked for."""
    want = q.given("parser", "trafilatura", None)
    if want is None and q.interactive:
        q.out("Optional: a better article parser for news pages that have no feed (trafilatura, Apache-2.0, with")
        q.out("  the packages it needs, every file hash-checked). Without it Composer reads those pages")
        q.out("  with its own built-in parser (text only); feeds are not affected.")
    if want is None:
        want = q.yes("Install the optional article parser?", False)
    plan["parser"] = {"trafilatura": bool(want)}


def setup_parser(plan: dict, base: Path, log, *, install=None) -> dict:
    """Install the parser if it was asked for and is not there yet. Returns the extraction settings; a failed
    install leaves the built-in parser in use and says so."""
    from . import html_extract as X
    if not plan["parser"]["trafilatura"]:
        return {"trafilatura": False}
    if X.trafilatura_installed():
        log("  the article parser is already installed")
        return {"trafilatura": True}
    if plan.get("data_only") and install is None:
        log("  article parser not installed: this image has no way to add packages; pages without a feed are read "
            "with the built-in parser")
        return {"trafilatura": False}
    try:
        (install or X.install_trafilatura)(env=H.private_env(base), log=log)
    except X.ExtractionError as exc:
        log(f"  {exc}; pages without a feed are read with the built-in parser")
        log("  try again later with `composer setup --reconfigure parser`")
        return {"trafilatura": False}
    return {"trafilatura": True}


def ask_narration(q: Asker, plan: dict, *, detect=N.detect) -> None:
    want = q.given("narration", "enabled", None)
    if want is None and q.interactive:
        q.out("")
        q.out("Narration (optional) adds a Listen button and three voices. It runs on this computer's CPU.")
        q.out(f"  It needs about {N.DOWNLOAD_MB} MB of model files (unless a Kokoro you already have passes a check)")
        q.out(f"  and a private runtime of about {N.RUNTIME_MB} MB. Without it, briefs are text-only.")
        want = q.yes("Add narration?", False)
    if not want:
        plan["narration"] = {"enabled": False}
        return
    q.out("Narration uses parts under these licences:")
    for line in N.LICENCES:
        q.out(f"  - {line}")
    accepted = q.given("narration", "accept_licences", None)
    if accepted is None:
        accepted = q.yes("Continue with these licences?", False)
    if not accepted:
        q.out("  narration skipped: the licences were not accepted (set accept_licences = true to accept)")
        plan["narration"] = {"enabled": False}
        return
    found = detect(skip=(str(plan["home"]),))
    usable = [c for c in found if c["kind"] in ("files", "server")]
    for c in found:
        if c["kind"] == "files":
            q.out(f"  found Kokoro model files ({c['found_by']}): {c['model']}")
        elif c["kind"] == "server":
            q.out(f"  found a Kokoro server at {c['url']}")
        elif c["kind"] == "unusable":
            q.out(f"  found {c['path']}: {c['why']}")
    use = q.given("narration", "use")
    options = []
    for n, c in enumerate(usable):
        label = (f"use your existing model files, read-only: {c['model']}" if c["kind"] == "files"
                 else f"use your Kokoro server at {c['url']}")
        options.append((f"existing:{n}", label + " (checked first)"))
    options += [("download", f"download the model into the app folder ({N.DOWNLOAD_MB} MB)"),
                ("skip", "no narration (text-only briefs)")]
    if use is None:
        use = q.choose("Which narration engine?", options, options[0][0] if usable else "skip")
    elif use == "existing":
        use = "existing:0" if usable else "missing"
    elif use == "server":
        url = q.given("narration", "url") or N.SERVER_HINTS[0]
        usable.append({"kind": "server", "url": url})
        use = f"existing:{len(usable) - 1}"
    if use == "missing":
        q.out("  no existing Kokoro was found; narration stays off (text-only)")
        plan["narration"] = {"enabled": False}
        return
    if use == "skip":
        plan["narration"] = {"enabled": False}
        return
    if use == "download":
        if q.interactive and not q.yes(f"Download {N.DOWNLOAD_MB} MB of model files now?", True):
            plan["narration"] = {"enabled": False}
            return
        plan["narration"] = {"enabled": True, "how": "download"}
        return
    if not use.startswith("existing:"):
        raise SetupError(f"[narration] use must be existing, server, download or skip, not {use!r}")
    choice = usable[int(use.split(":", 1)[1])]
    if choice["kind"] == "server" and q.interactive:
        url = q.ask("Confirm the server's exact address", choice["url"])
        choice = dict(choice, url=url)
    plan["narration"] = {"enabled": True, "how": "existing", "candidate": choice}


def ask_schedule(q: Asker, plan: dict) -> None:
    enabled = q.given("schedule", "enabled", None)
    if enabled is None:
        enabled = q.yes("Compose a daily brief automatically (while Composer runs)?", False)
    s = dict(S.DEFAULTS["schedule"])
    s["enabled"] = bool(enabled)
    if enabled:
        s["time"] = q.given("schedule", "time") or q.ask("At what time (24-hour HH:MM)", s["time"])
        s["timezone"] = q.given("schedule", "timezone") or q.ask("In which time zone: local or UTC", "local")
        s["sources"] = q.given("schedule", "sources") or s["sources"]
        s["lens"] = q.given("schedule", "lens") or q.ask("Through which lens", s["lens"])
        s["insights"] = q.given("schedule", "insights") or s["insights"]
    plan["schedule"] = s
    plan["backup"] = {"weekly": q.given("backup", "weekly", True), "keep": q.given("backup", "keep", 8)}


def ask_port(q: Asker, plan: dict) -> None:
    given = q.given("server", "port")
    if given is not None:
        port = int(given)
    else:
        port = int(q.ask("Port on this computer", str(next_free_port())))
    if not port_free(port):
        if given is not None:
            raise SetupError(f"[server] port {port} is in use on this computer; pick another")
        q.out(f"  {port} is in use; using {next_free_port(port + 1)}")
        port = next_free_port(port + 1)
    plan["port"] = port


# ------------------------------------------------------------------------------------------------ writes

def _launcher_text(home: Path, target: str) -> str:
    env = H.private_env(home, base={})
    lines = ["#!/bin/sh", "# Lensmith Composer launcher, made by `composer setup`. It changes nothing outside "
             "this folder:", "# every cache and temporary file goes inside it."]
    for key in sorted(env):
        lines.append(f"{key}={shlex.quote(env[key])}; export {key}")
    lines.append(f"exec {target} \"$@\"")
    return "\n".join(lines) + "\n"


def write_launcher(home: Path) -> Path:
    """bin/composer: runs app/current when setup.sh made the private environment, else this Python."""
    in_app = Path(sys.prefix).parent.parent == home / "app"
    command = (shlex.quote(str(home / "app" / "current" / "venv" / "bin" / "composer")) if in_app
               else f"{shlex.quote(sys.executable)} -m composer")
    path = home / "bin" / "composer"
    path.parent.mkdir(mode=0o700, exist_ok=True)
    H.atomic_write(path, _launcher_text(home, command), mode=0o700)
    return path


def setup_narration(q: Asker, plan: dict, base: Path, home: Path, log, *, check=None, install=None,
                    download=None) -> tuple[dict, list]:
    """Install/check/download as chosen. Returns (narration settings, reused manifest entries)."""
    n = dict(S.DEFAULTS["narration"])
    choice = plan["narration"]
    if not choice.get("enabled"):
        return n, []
    try:
        if choice.get("candidate", {}).get("kind") == "server":
            url = N.checked_server_url(choice["candidate"]["url"])
            result = (check or N.check_server)(url, home=base)
            if not result["rendered"]:
                raise N.NarrationError(f"the server rendered none of {', '.join(N.VOICES)}")
            if result["missing"]:
                log(f"  the server lacks {', '.join(result['missing'])}; only the voices that work are offered")
            n.update(enabled=True, engine="kokoro-http", url=url, voices=result["rendered"], reused=True)
            return n, []
        python = N.runtime_python(base, {})
        if python is None and plan.get("data_only"):
            raise N.NarrationError("this image has no narration runtime; set COMPOSER_TARGET=narration in .env, "
                                   "`docker compose build composer`, then run this again")
        python = python or (install or N.install_runtime)(base, log=log)
        if choice["how"] == "existing":
            cand = choice["candidate"]
            ok, why, info = N.check_files(cand["model"], cand["voices"])
            if not ok:
                raise N.NarrationError(f"your existing model files were not used: {why} (nothing was changed)")
            log("  test render with your existing files (read-only), all three voices")
            result = (check or N.check_render)(python, cand["model"], cand["voices"], home=base)
            if not result.get("ok"):
                raise N.NarrationError(f"your existing model files did not pass the voice check: missing "
                                       f"{', '.join(result.get('missing') or []) or 'a render'} (nothing was changed)")
            n.update(enabled=True, engine="kokoro-onnx", model_path=cand["model"], voices_path=cand["voices"],
                     python=str(python), voices=list(N.VOICES), reused=True)
            reused = [{"path": str(Path(cand[k]).resolve()), "kind": "reused", "sha256": info[label]["sha256"],
                       "size": info[label]["size"]} for k, label in (("model", "model"), ("voices", "voices"))]
            return n, reused
        model, voices = (download or N.download)(base, log=log)
        result = (check or N.check_render)(python, str(model), str(voices), home=base)
        if not result.get("ok"):
            raise N.NarrationError("the downloaded model did not pass the voice check")
        n.update(enabled=True, engine="kokoro-onnx", model_path=str(model), voices_path=str(voices),
                 python=str(python), voices=list(N.VOICES), reused=False)
        return n, []
    except Exception as exc:
        log(f"  narration stays off: {exc}")
        log("  briefs stay text-only; try again later with `composer setup --reconfigure narration`")
        return dict(S.DEFAULTS["narration"]), []


def run(*, home: Path, data: Path | None, answers_file: str | None, assume_yes: bool, reconfigure: list,
        data_only: bool, home_created_by_bootstrap: bool = False, check_only: bool = False, out=print, read=input,
        secret=getpass.getpass, interactive: bool | None = None, detect=N.detect, get=None, check=None,
        install=None, download=None, install_parser=None, test_call=None) -> int:
    # 1. Read-only: every guard and every answer, before anything is written.
    ans = A.load(answers_file) if answers_file else {}
    if check_only:
        interactive = False  # setup.sh's preflight: guards and answers only, nothing asked, nothing written
    if interactive is None:
        interactive = not answers_file and not assume_yes and sys.stdin.isatty()
    if not interactive and not answers_file and not assume_yes and not check_only:
        raise SetupError("no terminal to ask questions on: pass --answers FILE or --yes")
    for name in reconfigure:
        if name not in SECTIONS:
            raise SetupError(f"--reconfigure takes one of {', '.join(SECTIONS)}")
    if data_only:
        data = data or H.data_root(None)
        base = data
        if data.exists() and any(data.iterdir()) and not (data / "current").exists():
            names = [n for n in os.listdir(data) if n not in ("lost+found",)]
            if names:
                raise SetupError(f"refused: {data} holds files that are not Composer data; nothing was written")
        state = "data"
    else:
        state = H.guard(home)
        data = data or home / H.DATA_DIR  # native: inside the app folder unless --data says otherwise
        base = home
        real_home, real_data = Path(os.path.realpath(home)), Path(os.path.realpath(data))
        if real_data != Path(os.path.realpath(home / H.DATA_DIR)) and (
                real_data == real_home or real_home in real_data.parents):
            raise SetupError(f"refused: inside the app folder your data can only be {home / H.DATA_DIR}; "
                             "pick a data folder outside it, or leave --data out")
        if data != home / H.DATA_DIR and data.exists() and any(data.iterdir()) and not (data / "current").exists():
            raise SetupError(f"refused: {data} holds files that are not Composer data; nothing was written")
    existing = None
    if (data / "current").exists():
        try:
            existing = S.load(data)
        except S.SettingsError as exc:
            raise SetupError(str(exc)) from None
    first = existing is None or not (S.generation_dir(data, create=False) / "config.json").exists()
    todo = set(SECTIONS) if first else set(reconfigure)
    q = Asker(ans, interactive, out=out, read=read, secret=secret)
    plan = {"home": home, "data": data, "data_only": data_only,
            "test_call": test_call}  # setup's one tiny call per key; None (the default here) makes none
    if check_only and not answers_file and not assume_yes:
        return 0  # the questions come later, on the terminal; the folder guards above have passed
    out(f"Composer {__version__} setup. " + (f"App folder: {home}" if not data_only else f"Data folder: {data}"))
    if not first and not reconfigure:
        out("Composer is already set up here; your key, sources, lenses and briefs are kept.")
        out("Change one part with --reconfigure provider|checker|sources|parser|narration|schedule|port.")
    if "provider" in todo:
        ask_provider(q, plan)
    if "checker" in todo:
        writer = plan["provider"]["kind"] if "provider" in plan else (existing or S.DEFAULTS)["provider"]["kind"]
        ask_checker(q, plan, writer)
    if "sources" in todo:
        ask_sources(q, plan, get=get)
    if "parser" in todo:
        ask_parser(q, plan)
    if "narration" in todo:
        ask_narration(q, plan, detect=detect)
    if "schedule" in todo:
        ask_schedule(q, plan)
    if "port" in todo and not data_only:
        ask_port(q, plan)

    if check_only:
        out("preflight: every check passed; nothing was written")
        return 0
    # 2. Writes: the folder, the marker and manifest, the data, the settings, the key, the extras.
    if not data_only:
        home.mkdir(mode=0o700, exist_ok=True)
        if not (home / H.MARKER).exists():
            H.atomic_write(home / H.MARKER, H.MARKER_TEXT, mode=0o600)
        doc = H.load_manifest(home) if (home / H.MANIFEST).exists() else H.new_manifest(
            home, home_created=(state == "new" or home_created_by_bootstrap), version=__version__)
        doc["version"] = __version__
        doc["state"] = "installed"
        H.save_manifest(home, doc)
        H.ensure_private_dirs(home)
    data.mkdir(parents=True, exist_ok=True)
    os.chmod(data, 0o700)
    S.generation_dir(data)
    from .lifecycle import RUN_LOCK
    (data / RUN_LOCK).touch(mode=0o600, exist_ok=True)  # the lock `composer up` and the lifecycle commands share
    cfg = existing or json.loads(json.dumps(S.DEFAULTS))
    if "provider" in plan:
        cfg["provider"] = plan["provider"]
        if plan["secret"]:
            S.write_secret(data, plan["provider"]["key_env"], plan["secret"])
            plan["secret"] = None
    if "checker" in plan:
        cfg["checker"] = plan["checker"]
        if plan["checker_secret"]:
            S.write_secret(data, S.CHECKER_KEY, plan["checker_secret"])
            plan["checker_secret"] = None
    reused = []
    if "parser" in plan:
        cfg["extraction"] = setup_parser(plan, base, out, install=install_parser)
    if "narration" in plan:
        log = out
        cfg["narration"], reused = setup_narration(q, plan, base, home, log, check=check, install=install,
                                                   download=download)
    if "schedule" in plan:
        cfg["schedule"], cfg["backup"] = plan["schedule"], plan["backup"]
    if "port" in plan:
        cfg["server"]["port"] = plan["port"]
    S.save(data, cfg)
    if plan.get("sources_add"):
        from .registry import add_to_file, parse_entry
        for raw in plan["sources_add"]:
            add_to_file(S.sources_file(data), parse_entry(raw))
    if not data_only:
        write_launcher(home)
        doc = H.load_manifest(home)
        for name in H.OWNED_NAMES:
            if os.path.lexists(home / name):
                H.add_entry(doc, name, "created")
        H.add_entry(doc, H.DATA_DIR, "user-data")
        doc["data_path"] = str(Path(os.path.realpath(data)))
        if "narration" in plan:
            doc["entries"] = [e for e in doc["entries"] if e["kind"] != "reused"]
            for entry in reused:
                H.add_entry(doc, entry["path"], "reused", sha256=entry["sha256"], size=entry["size"])
        doc["choices"] = {"provider": cfg["provider"]["kind"], "checker_same": cfg["checker"]["same"],
                          "parser": cfg["extraction"]["trafilatura"],
                          "narration": cfg["narration"]["engine"],
                          "schedule": cfg["schedule"]["enabled"], "port": cfg["server"]["port"]}
        H.save_manifest(home, doc)

    # 3. Summary.
    out("")
    out("Done. Your choices:")
    out(f"  provider   {cfg['provider']['kind']}" + (f" ({cfg['provider']['model']})" if cfg['provider']['model'] else "")
        + {"stored": ", key stored (0600)", "env": f", key from {cfg['provider']['key_env']}", "none": ", no key"}
        [cfg["provider"]["key"]])
    c = cfg["checker"]
    out("  checker    " + ("the same model checks the claims" if c["same"] else
                           f"{c['kind']} ({c['model']})" + {"stored": ", key stored (0600)", "env": f", key from "
                                                            f"{S.CHECKER_KEY}", "none": ", no key"}[c["key"]]))
    out(f"  parser     {'trafilatura (optional article parser)' if cfg['extraction']['trafilatura'] else 'built-in'}")
    out(f"  narration  {'on: ' + cfg['narration']['engine'] if cfg['narration']['enabled'] else 'off (text-only)'}")
    out(f"  schedule   {'daily at ' + cfg['schedule']['time'] if cfg['schedule']['enabled'] else 'off'}")
    if not data_only:
        out(f"  port       {cfg['server']['port']}")
        out("")
        out(f"Start it:   {home}/bin/composer up")
        out(f"Then open:  http://127.0.0.1:{cfg['server']['port']}/")
        out(f"Check it:   {home}/bin/composer doctor")
        out("To run `composer` from anywhere, add this line to your shell profile yourself (setup does not):")
        out(f"  alias composer={shlex.quote(str(home / 'bin' / 'composer'))}")
    return 0
