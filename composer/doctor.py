"""`composer doctor`: one line per check, PASS / FAIL / SKIP, with the fix. Exit 1 when any check fails.

  composer doctor            this machine and this install, offline: Python, the app folder and its
                             permissions, the manifest, settings, key present (yes/no, never the value), sources,
                             narration files, port, scheduler, disk, data schema
  composer doctor --online   also: one tiny model call, every source fetched with its item count, and (when
                             narration is on) one sentence rendered with its time
  composer doctor --parity   also: a fixture brief end to end through the real routes on a private port, with
                             a throwaway data folder (no model, no key, no network): the page, options, compose,
                             status, the brief's files and transcript, save, shelf, delete, and narration if on
  composer doctor --seals    also: re-verify the claim-seal chain of every saved brief, and that the stored
                             brief is the one that was checked
"""
from __future__ import annotations

import hashlib
import http.client
import json
import os
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import __version__, demo
from . import home as H
from . import settings as S
from .httpd import LocalHTTPServer
from .providers import NO_CHECKER_KEY_MESSAGE, NO_KEY_MESSAGE
from .job_store import DATA_SCHEMA

PARITY_SCRIPT = (
    "This is Composer's own parity check, read aloud. It composes a recorded brief through the same routes the "
    "page uses, with no model and no network, and then checks the result: the page loads, the brief's files are "
    "there, the transcript matches what was read, and saving, the shelf and deleting all work as they should. "
    "If you can hear this, narration works on this machine too.")


class Report:
    def __init__(self, out=print):
        self.rows: list[tuple[str, str, str, str]] = []
        self.out = out
        self.trusted = True  # the trust check passed: doctor may write scratch files and start programs

    def add(self, status: str, name: str, detail: str, fix: str = "") -> None:
        self.rows.append((status, name, detail, fix))
        self.out(f"{status:<4} {name}: {detail}" + (f"\n     fix: {fix}" if fix and status == "FAIL" else ""))

    @property
    def failed(self) -> bool:
        return any(r[0] == "FAIL" for r in self.rows)

    def names(self) -> list[str]:
        return [r[1] for r in self.rows]


def _mode(path: Path) -> int:
    return os.stat(path).st_mode & 0o777


INTEGRITY = ("python", "version", "manifest", "trust", "data", "settings", "sources")
ONLINE_ROWS = ("online: model", "online: checker", "online: sources", "online: narration")
NOT_TRUSTED = "not run: the trust check failed (no settings were read, nothing was called, written or started)"


def run(home: Path, data: Path, *, online: bool = False, parity: bool = False, seals: bool = False, out=print,
        transport=None, get=None, render=None, verify=None, integrity_only: bool = False) -> int:
    """integrity_only: the checks an update must pass before it is kept (a missing key or a busy port is
    not a reason to undo an update); the others still print."""
    r = Report(out)
    offline_checks(r, home, data)
    if not r.trusted:
        # the folders failed the trust check: their settings may have been written by another account, so doctor
        # reads none of them, calls no model or source with them (your key would go where they say) and starts or
        # writes nothing. It reports the refusal and stops.
        for wanted, names in ((online, ONLINE_ROWS), (parity, ("parity",)), (seals, ("seals",))):
            for name in names if wanted else ():
                r.add("SKIP", name, NOT_TRUSTED)
    else:
        cfg = None
        try:
            cfg = S.load(data)
        except S.SettingsError:
            pass
        if online:
            online_checks(r, home, data, cfg, transport=transport, get=get, render=render)
        if parity:
            parity_checks(r, H.runtime_base(home, data), cfg, render=render)
        if seals:
            seal_checks(r, data, verify=verify)
    out(f"doctor: {sum(1 for x in r.rows if x[0] == 'PASS')} passed, {sum(1 for x in r.rows if x[0] == 'FAIL')} "
        f"failed, {sum(1 for x in r.rows if x[0] == 'SKIP')} skipped")
    if integrity_only:
        return 1 if any(x[0] == "FAIL" and (x[1] in INTEGRITY or x[1].startswith("parity:")) for x in r.rows) else 0
    return 1 if r.failed else 0


# ------------------------------------------------------------------------------------------------ offline

def trust_check(r: Report, home: Path | None, data: Path) -> None:
    """The trust contract (SECURITY.md), read-only, as update and `composer up` admit an install. When it fails,
    doctor stops there: it reads no settings, key or sources file from those folders, makes no model, checker or
    source call (--online), and writes and starts nothing (--parity, narration)."""
    from .lifecycle import LifecycleError, admit
    try:
        admit(home, data)
    except LifecycleError as exc:
        r.trusted = False
        r.add("FAIL", "trust", str(exc)[:600], "follow the fix named above, then run `composer doctor` again")
        return
    r.add("PASS", "trust", "no other account can change the " + ("app folder or the " if home else "")
          + "data folder")


def offline_checks(r: Report, home: Path, data: Path) -> None:
    v = sys.version_info
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    r.add("PASS" if v >= (3, 10) else "FAIL", "python",
          f"{v.major}.{v.minor}.{v.micro} at {sys.executable}" + (" (private environment)" if in_venv else ""),
          "Composer needs Python 3.10 or newer")
    r.add("PASS", "version", f"composer {__version__}, data schema {DATA_SCHEMA}")
    container = os.environ.get(H.DATA_ENV) and not (home / H.MANIFEST).exists()
    if container:
        r.add("SKIP", "app folder", f"no app folder: data at {data} (the container layout)")
    elif not home.is_dir():
        r.add("FAIL", "app folder", f"{home} does not exist", "run setup.sh")
    else:
        try:
            doc = H.load_manifest(home)
            problems = H.check_manifest(home, doc, data)
            missing = [e["path"] for e in doc["entries"] if e["kind"] == "created" and not os.path.lexists(home / e["path"])]
            reused_gone = [e["path"] for e in doc["entries"] if e["kind"] == "reused" and not os.path.exists(e["path"])]
            if problems:
                r.add("FAIL", "manifest", "; ".join(problems)[:300], "do not run uninstall; open an issue")
            elif missing or reused_gone:
                r.add("FAIL", "manifest", f"listed but missing: {', '.join(missing + reused_gone)[:300]}",
                      "run `composer setup` again to repair")
            else:
                r.add("PASS", "manifest", f"{len(doc['entries'])} entries, every path inside {home} or reused read-only")
        except H.HomeError as exc:
            r.add("FAIL", "manifest", str(exc), "run setup.sh")
    trust_check(r, None if container or not home.is_dir() else home, data)
    if not r.trusted:
        r.add("SKIP", "the other checks", NOT_TRUSTED)
        return
    if not (data / "current").exists():
        r.add("FAIL", "data", f"no Composer data at {data}", "run `composer setup`")
        return
    try:
        gen = S.generation_dir(data, create=False)
        have = (gen / "VERSION").read_text(encoding="utf-8").strip()
        ok = int(have) <= int(DATA_SCHEMA)
        r.add("PASS" if ok else "FAIL", "data", f"{data}, generation {gen.name}, schema {have}",
              "a newer Composer migrated this data: run `composer rollback --data-only` with that version")
    except (OSError, ValueError, S.SettingsError) as exc:
        r.add("FAIL", "data", str(exc), "restore a backup with `composer restore`")
        return
    if os.name == "posix":
        bad = [str(p) for p in (data,) if _mode(p) & 0o077]
        secret_ok = S.secrets_mode_ok(data)
        if secret_ok is False:
            bad.append(str(S.secrets_path(data)))
        r.add("FAIL" if bad else "PASS", "permissions",
              ("only you can open: data 0700" + (", key file 0600" if secret_ok else "")) if not bad
              else "readable by others: " + ", ".join(bad), "chmod 700 the data folder and chmod 600 secrets.env")
    try:
        cfg = S.load(data)
        r.add("PASS", "settings", f"provider {cfg['provider']['kind']}"
              + (f", model {cfg['provider']['model']}" if cfg["provider"]["model"] else ""))
    except S.SettingsError as exc:
        r.add("FAIL", "settings", str(exc), "run `composer setup --reconfigure provider`")
        return
    if cfg["provider"]["kind"] == "none":
        r.add("SKIP", "key", "no model provider chosen: the app shows the recorded brief; composing needs one",
              "run `composer setup --reconfigure provider`")
    elif cfg["provider"]["key"] == "none" and not S.key_present(data, cfg):
        r.add("SKIP", "key", f"{NO_KEY_MESSAGE} ({cfg['provider']['key_env']} is not set; the app shows the "
              "recorded brief meanwhile)", "run `./setup.sh --reconfigure provider`")
    else:
        present = S.key_present(data, cfg)
        where = "environment variable" if os.environ.get(cfg["provider"]["key_env"]) else "key file"
        r.add("PASS" if present else "FAIL", "key", f"{cfg['provider']['key_env']} present: "
              + (f"yes ({where})" if present else f"no. {NO_KEY_MESSAGE}"), f"set {cfg['provider']['key_env']} or "
              "run `./setup.sh --reconfigure provider`")
    c = cfg["checker"]
    if c["same"]:
        r.add("PASS", "checker", "same model as the writer (it checks its own brief)")
    else:
        present = S.key_present(data, cfg, "checker")
        where = "environment variable" if os.environ.get(c["key_env"]) else "key file"
        r.add("PASS" if present else "FAIL", "checker",
              f"a different model: {c['kind']}" + (f", model {c['model']}" if c["model"] else "")
              + f"; {c['key_env']} present: " + (f"yes ({where})" if present else f"no. {NO_CHECKER_KEY_MESSAGE}"),
              f"set {c['key_env']} or run `composer setup --reconfigure checker`")
    try:
        from .registry import Registry
        sf = S.sources_file(data)
        reg = Registry.load(str(sf) if sf.exists() else None)
        r.add("PASS", "sources", ", ".join(reg.ids))
    except Exception as exc:
        r.add("FAIL", "sources", str(exc)[:200], "fix or remove the sources file in your data folder")
    narration_offline(r, home, cfg)
    port = cfg["server"]["port"]
    r.add("PASS", "port", port_state(port))
    s = cfg["schedule"]
    if s["enabled"]:
        from datetime import datetime, timezone
        from .scheduler import next_slot
        nxt = next_slot(datetime.now(timezone.utc), s["time"], s["timezone"]).strftime("%Y-%m-%d %H:%M UTC")
        r.add("PASS", "scheduler", f"daily at {s['time']} ({s['timezone']}); next run {nxt}, while `composer up` runs")
    else:
        r.add("SKIP", "scheduler", "no daily brief set", "`composer setup --reconfigure schedule` to add one")
    try:
        state = json.loads((data / "scheduler.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = {}
    if not cfg["seals"]["daily"]:
        r.add("SKIP", "daily seal re-check", "off (seals.daily is false)")
    elif isinstance(state, dict) and state.get("last_seal_day"):
        outcome = str(state.get("last_seal_outcome") or "")
        r.add("FAIL" if outcome.startswith(("FAILED", "could not run")) else "PASS", "daily seal re-check",
              f"{state['last_seal_day']}: {outcome[:200]}", "run `composer doctor --seals` and restore from a backup")
    else:
        r.add("SKIP", "daily seal re-check", "not run yet; it runs once a day while `composer up` runs")
    from .html_extract import trafilatura_installed
    if trafilatura_installed():
        r.add("PASS", "article parser", "trafilatura is installed (html-index sources that ask for it use it)")
    elif cfg["extraction"]["trafilatura"]:
        r.add("FAIL", "article parser", "setup installed trafilatura but it cannot be imported now; pages without a "
              "feed are read with the built-in parser", "`composer setup --reconfigure parser`")
    else:
        r.add("SKIP", "article parser", "built-in parser (the optional trafilatura parser is not installed)")
    free = shutil.disk_usage(data).free
    r.add("PASS" if free > 200 * 1024 * 1024 else "FAIL", "disk", f"{free // (1024 * 1024)} MB free",
          "free some disk space")


def port_state(port: int) -> str:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    except OSError:
        return f"{port} is free on 127.0.0.1 (Composer binds to this machine only)"
    try:
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        c.request("GET", "/health", headers={"Host": f"127.0.0.1:{port}"})
        resp = c.getresponse()
        body = resp.read(4096)
        if resp.status == 200 and b"active_jobs" in body:
            return f"Composer is answering on 127.0.0.1:{port}"
    except OSError:
        pass
    return f"{port} is in use by another program; `composer up --port <another>`"


def narration_offline(r: Report, home: Path, cfg: dict) -> None:
    n = cfg["narration"]
    if not n["enabled"]:
        r.add("SKIP", "narration", "off: briefs are text-only, the page shows no player or voice picker",
              "`composer setup --reconfigure narration` to add it")
        return
    if n["engine"] == "kokoro-http":
        r.add("PASS", "narration", f"Kokoro server {n['url']} (checked at setup; --online renders a sentence)")
        return
    from . import narration as N
    py = N.runtime_python(home, n)
    problems = []
    if py is None:
        problems.append("the narration runtime is missing")
    for label, path, name in (("model", n["model_path"], N.MODEL_FILE), ("voices", n["voices_path"], N.VOICES_FILE)):
        p = Path(path)
        if not p.is_file():
            problems.append(f"{label} file {path} is missing")
        elif p.stat().st_size != N.PINNED[name][1]:
            problems.append(f"{label} file {path} is not the pinned size")
    if problems:
        r.add("FAIL", "narration", "; ".join(problems), "`composer setup --reconfigure narration`")
    else:
        r.add("PASS", "narration", f"kokoro-onnx, voices {', '.join(n['voices'])}"
              + (" (your existing model files, read-only)" if n["reused"] else ""))


# ------------------------------------------------------------------------------------------------ --online

def online_checks(r: Report, home: Path, data: Path, cfg: dict | None, *, transport=None, get=None,
                  render=None) -> None:
    if not r.trusted:  # settings from a folder that failed the trust check could send your key anywhere
        for name in ONLINE_ROWS:
            r.add("SKIP", name, NOT_TRUSTED)
        return
    if cfg is None:
        r.add("SKIP", "online: model", "no settings")
        return
    from .providers import ProviderError, from_env, use_key_file
    if cfg["provider"]["kind"] == "none":
        r.add("SKIP", "online: model", "no model provider chosen")
    else:
        use_key_file(S.secrets_path(data))
        env = dict(os.environ)
        env.update(S.provider_env(cfg))
        try:
            started = time.monotonic()
            model = from_env(env=env, transport=transport)
            model("Reply with the single word OK.", timeout=60)
            # the configured name, not the endpoint's own model field or reply text (either could echo the key)
            r.add("PASS", "online: model", f"{model.name} answered in {time.monotonic() - started:.1f} s")
        except ProviderError as exc:
            r.add("FAIL", "online: model", str(exc)[:200], "check the key and the model name")
    if not cfg["checker"]["same"]:
        from .providers import checker_from_env
        use_key_file(S.secrets_path(data))
        try:
            started = time.monotonic()
            checker = checker_from_env(env={**os.environ, **S.checker_env(cfg)}, transport=transport)
            checker("Reply with the single word OK.", timeout=60)
            r.add("PASS", "online: checker", f"{checker.name} answered in {time.monotonic() - started:.1f} s")
        except ProviderError as exc:
            r.add("FAIL", "online: checker", str(exc)[:200], "check the checker's key and model name")
    from . import adapters
    from .fetch import http_get
    from .registry import Registry
    sf = S.sources_file(data)
    reg = Registry.load(str(sf) if sf.exists() else None)
    for entry in reg.entries():
        try:
            items, receipt = adapters.fetch(entry, get or http_get)
            ok = receipt.get("status") == "ok" and items
            r.add("PASS" if ok else "FAIL", f"online: source {entry.id}",
                  f"{len(items)} items" if ok else str(receipt.get("error") or receipt.get("status"))[:200],
                  "check the address with `composer sources check`")
        except Exception as exc:
            r.add("FAIL", f"online: source {entry.id}", str(exc)[:200], "check the address")
    n = cfg["narration"]
    if not n["enabled"]:
        r.add("SKIP", "online: narration", "narration is off")
        return
    from . import narration as N
    base = H.runtime_base(home, data)
    try:
        # checked now, not only at the trust row: the app folder may not have existed then (only the data folder was
        # checked) and may have been made since, so it gets the same trust check before anything is written in it
        tmp = H.owned_dir(base, "tmp")
    except H.HomeError as exc:
        r.add("FAIL", "online: narration", str(exc)[:600], "follow the fix named above, then run `composer doctor "
              "--online` again")
        return
    work = Path(tempfile.mkdtemp(prefix="doctor-", dir=str(tmp)))
    try:
        narrator = N.Narrator(n, base, render=render)
        started = time.monotonic()
        answer = narrator._render(text="Composer can speak on this machine.", voice=n["voices"][0],
                                  out_base=work / "doctor", timeout=float(n["max_seconds"]))
        size = Path(answer["file"]).stat().st_size
        r.add("PASS", "online: narration", f"one sentence in {time.monotonic() - started:.1f} s "
              f"({answer['format']}, {size} bytes, voice {n['voices'][0]})")
    except Exception as exc:
        r.add("FAIL", "online: narration", str(exc)[:200], "`composer setup --reconfigure narration`")
    finally:
        shutil.rmtree(work, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ --parity

def _http(port: int, method: str, path: str, body: dict | None = None) -> tuple[int, bytes, dict]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    headers = {"Host": f"127.0.0.1:{port}"}
    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")
        headers.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{port}",
                        "X-Composer-CSRF": "same-origin", "Content-Length": str(len(payload))})
    c.request(method, path, body=payload, headers=headers)
    resp = c.getresponse()
    data = resp.read()
    c.close()
    return resp.status, data, dict(resp.getheaders())


def parity_checks(r: Report, home: Path, cfg: dict | None, *, render=None) -> None:
    from . import narration as N
    from .registry import Registry
    from .scheduler import chain
    from .server import App, handler_for

    if not r.trusted:
        r.add("SKIP", "parity", NOT_TRUSTED)
        return
    edition = demo.load()
    problems = demo.validate(edition)
    r.add("PASS" if not problems else "FAIL", "parity: recorded edition",
          f"{len(edition['cards'])} cards, check {edition['check']['agree']}/{edition['check']['rows']} agree"
          if not problems else "; ".join(problems)[:200], "reinstall Composer")
    fixture = dict(edition, transcript=PARITY_SCRIPT)

    def compose(**_kw):
        return {"edition": fixture, "result": {}, "fetched": {}}

    ncfg = dict((cfg or S.DEFAULTS)["narration"])
    scratch = Path(tempfile.mkdtemp(prefix="composer-parity-"))
    narrator = N.Narrator(ncfg, home, render=render)
    app = App(Registry.load(None), lambda: object(), compose=compose, data_root=scratch / "data",
              settings={"narration": ncfg}, on_finished=chain(narrator.on_finished))
    narrator.attach(app.jobs)
    quiet = type("QuietHandler", (handler_for(app, local_only=True),), {"log_message": lambda *a: None})
    httpd = LocalHTTPServer(("127.0.0.1", 0), quiet)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        st, body, _ = _http(port, "GET", "/app/")
        r.add("PASS" if st == 200 and b"<html" in body.lower() else "FAIL", "parity: page", f"/app/ {st}, "
              f"{len(body)} bytes", "reinstall Composer")
        st, body, _ = _http(port, "GET", "/data/options.json")
        opts = json.loads(body) if st == 200 else {}
        r.add("PASS" if st == 200 and opts.get("sources") else "FAIL", "parity: options",
              f"{len(opts.get('sources', []))} sources, voices {opts.get('voices')}", "reinstall Composer")
        st, body, _ = _http(port, "POST", "/compose", {"sources": opts.get("sources", [])[:2] or ["google-ai"],
                                                         "lens": "parity check", "insights": 5})
        job = json.loads(body).get("job") if st == 202 else None
        if not job:
            r.add("FAIL", "parity: compose", f"POST /compose {st}", "reinstall Composer")
            return
        phase, deadline = None, time.monotonic() + 30
        while time.monotonic() < deadline:
            st, body, _ = _http(port, "GET", f"/status/{job}")
            phase = json.loads(body).get("phase")
            if phase in ("verified", "verification_failed", "compose_failed"):
                break
            time.sleep(0.05)
        r.add("PASS" if phase == "verified" else "FAIL", "parity: compose", f"{job} reached {phase}",
              "reinstall Composer")
        st, body, _ = _http(port, "GET", f"/data/live/{job}/composed.json")
        composed = json.loads(body) if st == 200 else {}
        st2, text, _ = _http(port, "GET", f"/data/live/{job}/transcript.txt")
        ok = (len(composed.get("items", [])) == len(edition["cards"]) and st2 == 200
              and text.decode("utf-8").strip() == composed.get("transcript", "").strip())
        r.add("PASS" if ok else "FAIL", "parity: brief files", f"composed.json {len(composed.get('items', []))} "
              f"items, transcript.txt {st2}", "reinstall Composer")
        st, _, _ = _http(port, "POST", f"/save/{job}", {})
        _, shelf, _ = _http(port, "GET", "/shelf")
        on_shelf = any(i.get("job") == job for i in json.loads(shelf).get("items", []))
        r.add("PASS" if st == 200 and on_shelf else "FAIL", "parity: save and shelf", f"save {st}, on shelf "
              f"{'yes' if on_shelf else 'no'}", "reinstall Composer")
        if narrator.enabled:
            deadline = time.monotonic() + float(ncfg.get("max_seconds", 600)) + 5
            while True:
                jst = json.loads(_http(port, "GET", f"/data/live/{job}/job.json")[1])
                if jst.get("audio_state") not in (None, "generating") or time.monotonic() > deadline:
                    break
                time.sleep(0.1)
            audio = jst.get("audio") or {}
            if jst.get("audio_state") == "ready":
                ast, blob, _ = _http(port, "GET", f"/data/live/{job}/{audio.get('file')}")
                _, rendered, _ = N.prepare_text(PARITY_SCRIPT)
                same = audio.get("text_sha256") == hashlib.sha256(rendered.encode()).hexdigest()
                r.add("PASS" if ast == 200 and blob and same else "FAIL", "parity: narration",
                      f"{audio.get('file')} {len(blob)} bytes; transcript and rendered text "
                      f"{'match' if same else 'differ'}", "`composer doctor --online` for the reason")
            else:
                r.add("FAIL", "parity: narration", f"audio {jst.get('audio_state')}: {audio.get('reason')}",
                      "`composer setup --reconfigure narration`")
        else:
            deadline = time.monotonic() + 5
            while True:
                jst = json.loads(_http(port, "GET", f"/data/live/{job}/job.json")[1])
                if jst.get("audio_state") or time.monotonic() > deadline:
                    break
                time.sleep(0.05)
            r.add("PASS" if jst.get("audio_state") == "off" and opts.get("voices") == [] else "FAIL",
                  "parity: text-only", f"audio_state {jst.get('audio_state')}, voices {opts.get('voices')}: no "
                  "player and no voice picker on the page", "reinstall Composer")
        st, _, _ = _http(port, "POST", f"/delete/{job}", {})
        _, shelf, _ = _http(port, "GET", "/shelf")
        gone = not any(i.get("job") == job for i in json.loads(shelf).get("items", []))
        r.add("PASS" if st == 200 and gone else "FAIL", "parity: delete", f"delete {st}, off the shelf "
              f"{'yes' if gone else 'no'}", "reinstall Composer")
    finally:
        httpd.shutdown()
        httpd.server_close()
        shutil.rmtree(scratch, ignore_errors=True)


# ------------------------------------------------------------------------------------------------ --seals

def seal_checks(r: Report, data: Path, *, verify=None) -> None:
    if not r.trusted:
        r.add("SKIP", "seals", NOT_TRUSTED)
        return
    if not (data / "current").exists():
        r.add("SKIP", "seals", "no data")
        return
    from . import seal as SEAL
    try:
        result = SEAL.recheck_saved(data, verify=verify)
    except SEAL.SealError as exc:
        r.add("FAIL", "seals", str(exc), "reinstall Composer")
        return
    if result["failed"]:
        r.add("FAIL", "seals", f"{result['checked']} verified; failed: {', '.join(result['failed'])[:300]}",
              "restore the brief from a backup")
    elif result["checked"] or result["unsealed"]:
        r.add("PASS", "seals", SEAL.summary(result))
    else:
        r.add("SKIP", "seals", "no saved briefs yet")
