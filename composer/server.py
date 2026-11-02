"""`composer serve`: the always-on tier. A small web server that shows the latest brief and,
with a key in its environment, composes new ones from a form.

Safe defaults:
  - It listens on 127.0.0.1 only, unless you pass --host.
  - On any other address it refuses to start without COMPOSER_SERVER_PASS set; every compose
    request must then send that phrase in the X-Composer-Pass header. Anyone who can compose
    spends your API credit, so do not skip this.
  - On this machine (the default), it answers only requests addressed to this machine by name
    (Host 127.0.0.1, localhost or [::1]), so a web site that points its own name at 127.0.0.1
    (DNS rebinding) is refused. A compose request must be sent as application/json from the
    page's own origin: a browser cannot send that from another site without asking first, and
    this server never says yes, so another site you visit cannot compose and spend your credit.
  - One brief at a time; a second request while one runs gets 429.
  - Request bodies over 16 KB, unknown sources and long lenses are refused before any fetch.
  - It is a plain standard-library server: put a TLS-terminating proxy in front of it before
    you expose it to the internet.
"""
from __future__ import annotations

import dataclasses
import hmac
import ipaddress
import json
import os
import re
import threading
import tempfile
from urllib.parse import urlsplit
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import app_static, demo, discovery, html_extract, lenses, live_files, page, pipeline, receipts, sources_registry
from .job_store import JobStore, StoreError
from .narration import options_fragment
from .prompt import DEFAULT_INSIGHTS, INSIGHT_RANGE
from .providers import ProviderError
from .registry import RegistryError

MAX_BODY = 16 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
LOOPBACK_NAMES = {"127.0.0.1", "localhost", "::1"}
CSRF_HEADER = "X-Composer-CSRF"
CSRF_VALUE = "same-origin"
# the source and lens services: a POST to each path goes to the App method named here
SERVICE_ROUTES = {"/source/probe": "handle_source_probe", "/source/register": "handle_source_register",
                  "/lens/save": "handle_lens_save"}


_PORT = re.compile(r"[0-9]{1,5}")


def host_name(host_header: str) -> str:
    """The name part of a Host header (no port, no brackets, lower case), or "" when the header
    is not exactly one authority: name[:port] or [ipv6][:port], nothing before or after."""
    value = (host_header or "").strip().lower()
    if value.startswith("["):
        close = value.find("]")
        if close < 0:
            return ""
        name, rest = value[1:close], value[close + 1:]
    elif value.count(":") == 1:
        name, rest = value.split(":", 1)
        rest = ":" + rest
    elif ":" in value:
        return ""  # an IPv6 address must be in brackets
    else:
        name, rest = value, ""
    if rest and not (rest.startswith(":") and _PORT.fullmatch(rest[1:]) and 1 <= int(rest[1:]) <= 65535):
        return ""
    return name


def request_problem(method: str, headers, *, local_only: bool) -> str | None:
    """Why a request must be refused before it is handled, or None.

    A compose POST must always declare its body as JSON (a cross-site page cannot send that
    without a CORS preflight, which this server never answers). When the server listens on this
    machine (local_only), the Host must also name this machine, and a POST's Origin (if sent) must
    be this server's own and a browser's Sec-Fetch-Site (if sent) same-origin. Beyond this machine
    the pass phrase header does that job (a custom header also needs a preflight), and a TLS
    proxy in front may rewrite Host, so those two checks are not made there."""
    get_all = getattr(headers, "get_all", None)
    if get_all is not None:
        for name in ("Host", "Origin", "Content-Type", "Sec-Fetch-Site", CSRF_HEADER):
            if len(get_all(name) or []) > 1:
                return f"send one {name} header"
    host = headers.get("Host", "")
    if local_only and host_name(host) not in LOOPBACK_NAMES:
        return "this server only answers requests addressed to 127.0.0.1 or localhost"
    if method != "POST":
        return None
    ctype = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if ctype != "application/json":
        return "send the request as application/json"
    if not hmac.compare_digest(headers.get(CSRF_HEADER, ""), CSRF_VALUE):
        return "send the same-origin anti-forgery header"
    if not local_only:
        return None
    origin = headers.get("Origin")
    if origin is not None:
        o = urlsplit(origin)
        if origin == "null" or o.scheme not in ("http", "https") or o.netloc.lower() != host.strip().lower():
            return "compose requests are only accepted from this server's own page"
    site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
    if site and site not in ("same-origin", "none"):
        return "compose requests are only accepted from this server's own page"
    return None


class _StaticSources:
    """The source service for an App made without one: the App's own registry, read as it is now."""

    def __init__(self, current):
        self.current = current
        self.packages = sources_registry.PackageService(None)

    def package_options(self):
        registry = self.current()
        packages, health = self.packages.current(registry)
        return sources_registry.package_projection(packages, registry), health

    def snapshot(self):
        return self.current()

    def options(self):
        return {"generation": 1, "reload": {"state": "ready", "reason": ""},
                "sources": [sources_registry.source_option(item) for item in self.current().entries()]}


class App:
    def __init__(self, registry, make_model, *, out_dir: Path | None = None, passphrase: str = "",
                 compose=pipeline.compose, data_root: Path | str | None = None, job_worker=None,
                 settings: dict | None = None, on_finished=None, source_service=None, lens_store=None,
                 make_checker=None):
        self.registry = registry
        self.source_service = source_service or _StaticSources(lambda: self.registry)
        self.lens_registry = lenses.LensRegistry.builtin()
        self.lens_store = lens_store
        self.make_model = make_model
        self.make_checker = make_checker  # the optional separate checker model; None: the writer checks its brief
        self.out_dir = out_dir
        self.passphrase = passphrase
        self.compose = compose
        self.settings = settings or {}
        self.scheduler = None
        self.lock = threading.Lock()
        self.latest = demo.load()
        root = Path(data_root) if data_root is not None else ((out_dir or Path(tempfile.mkdtemp(prefix="composer-data-"))) / "composer-data")
        self.jobs = JobStore(root, worker=job_worker or self._job_worker, on_finished=on_finished)

    def sources(self):
        """The source registry as it is now: a sources file edited while the server runs is read again, and
        a broken edit keeps the last good registry (the options say why)."""
        return self.source_service.snapshot()

    def narration_voices(self) -> list:
        return options_fragment(self.settings)["voices"]

    def lens_entries(self) -> tuple:
        custom = self.lens_store.entries() if self.lens_store is not None else ()
        return (*self.lens_registry.entries(), *custom)

    def options(self) -> dict:
        """data/options.json: what the page offers, the one list of sources, lenses, reading levels, insight
        range and voices the engine accepts. The narration part follows the settings: voices [] and
        narration.enabled false when narration is off, so the page shows no voice picker and no player."""
        registry_options = self.source_service.options()
        rows = registry_options["sources"]
        low, high = INSIGHT_RANGE.start, INSIGHT_RANGE.stop - 1
        lens_rows = self.lens_entries()
        reload_state = registry_options.get("reload") or {}
        packages, package_health = self.source_service.package_options()
        out = {"sources": [r["id"] for r in rows],
               "source_meta": {r["id"]: {"label": r["label"], "kind": r["kind"], "max_items": r["max_items"]}
                               for r in rows},
               "source_status": {r["id"]: {"available": r["available"], "hidden": r["hidden"],
                                           "reason": r["reason"]} for r in rows},
               "registry_health": {"degraded": reload_state.get("state") == "degraded",
                                   "error": reload_state.get("reason", ""),
                                   "generation": registry_options.get("generation"),
                                   "packages": package_health},
               "packages": packages,
               "lenses": [lens.id for lens in lens_rows],
               "lens_meta": {lens.id: _lens_meta(lens) for lens in lens_rows},
               "lens_status": {lens.id: {"available": lens.available, "hidden": False, "reason": lens.reason}
                               for lens in lens_rows},
               "default_lens": self.lens_registry.ids[0],
               "reading_levels": list(lenses.READING_LEVELS),
               "default_reading_level": "standard",
               "insights": {"minimum": low, "maximum": high, "min": low, "max": high, "default": DEFAULT_INSIGHTS},
               "extraction_tiers": html_extract.available_tiers()}
        out.update(options_fragment(self.settings))
        return out

    def source_ids(self) -> dict:
        return {e.label: e.id for e in self.sources().entries()}

    def _resolve_lens(self, raw: object, reading_level: object = None) -> lenses.Lens:
        """A public lens by id, a saved lens by id, or else the words themselves as a lens for this brief."""
        value = lenses.validate_text(raw)
        found = None
        try:
            found = self.lens_registry.get(value)
        except lenses.LensError:
            for entry in (self.lens_store.entries() if self.lens_store is not None else ()):
                if entry.id == value:
                    found = entry
                    break
        if found is None:
            found = lenses.Lens("ad-hoc", "Your words", "A lens written for this brief.", value)
        if reading_level is not None:
            if reading_level not in lenses.READING_LEVELS:
                raise lenses.LensError("reading_level must be plain, standard, or technical")
            found = dataclasses.replace(found, reading_level=reading_level)
        return found

    def _models(self):
        """(writer, checker or None), each checked for its key before any feed is read."""
        model = self.make_model()
        if hasattr(model, "ready"):
            model.ready()
        checker = self.make_checker() if self.make_checker is not None else None
        if checker is not None and hasattr(checker, "ready"):
            checker.ready()
        return model, checker

    def _job_worker(self, job: dict, draft_ready) -> dict:
        request = job["request"]
        sources = self.sources().pick(request["sources"])
        lens = self._resolve_lens(request["lens"], request.get("reading_level"))
        model, checker = self._models()
        extra = {"checker": checker} if checker is not None else {}
        run = self.compose(lens=lens.instruction, lens_definition=lens, sources=sources, model=model,
                           count=request.get("insights", DEFAULT_INSIGHTS), **extra)
        draft_ready(run["edition"])
        evidence = (run.get("result") or {}).get("claim_evidence")
        if isinstance(evidence, dict):  # kept so `composer doctor --seals` can re-verify the seal later
            self.jobs.write_artifact(job["job"], "check.json", {"claim_evidence": evidence})
        self.jobs.write_artifact(job["job"], "receipts.json",
                                 receipts.build_receipt(run, requested=request["sources"]))
        return {"status": "ok", "claim_evidence": {"job": job["job"],
                                                        "draft_sha256": job["draft_sha256"]}}

    @staticmethod
    def _json_body(body: bytes) -> dict:
        try:
            value = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ValueError("send a JSON object") from None
        if not isinstance(value, dict):
            raise ValueError("send a JSON object")
        return value

    def _authorize(self, headers) -> tuple[int, dict] | None:
        if self.passphrase:
            sent = headers.get("X-Composer-Pass", "")
            if not hmac.compare_digest(sent.encode("utf-8"), self.passphrase.encode("utf-8")):
                return 403, {"error": "wrong or missing pass phrase"}
        return None

    def _compose_request(self, body: bytes, extra: set) -> tuple[dict | None, tuple[int, dict] | None]:
        """The checked fields of a compose request, or the refusal. Nothing is fetched before this passes."""
        try:
            req = self._json_body(body)
        except ValueError as exc:
            return None, (400, {"error": str(exc)})
        if set(req) - ({"sources", "lens", "insights", "reading_level"} | extra):
            return None, (400, {"error": "send {\"sources\": [...], \"lens\": \"...\"}"})
        ids = req.get("sources")
        count = req.get("insights", DEFAULT_INSIGHTS)
        try:
            lens = self._resolve_lens(req.get("lens"), req.get("reading_level"))
        except lenses.LensError as exc:
            return None, (400, {"error": str(exc)})
        if not isinstance(ids, list) or not ids or len(ids) > 8 or not all(isinstance(x, str) for x in ids):
            return None, (400, {"error": "name 1 to 8 sources"})
        if not isinstance(count, int) or isinstance(count, bool) or count not in INSIGHT_RANGE:
            return None, (400, {"error": f"insights must be from {INSIGHT_RANGE.start} to {INSIGHT_RANGE.stop - 1}"})
        try:
            sources = self.sources().pick(ids)
        except RegistryError as exc:
            return None, (400, {"error": str(exc)})
        return {"req": req, "ids": ids, "count": count, "lens": lens, "sources": sources}, None

    def submit_job(self, headers, body: bytes) -> tuple[int, dict]:
        denied = self._authorize(headers)
        if denied:
            return denied
        checked, refused = self._compose_request(body, {"voice"})
        if refused:
            return refused
        voice = checked["req"].get("voice")
        if voice is not None and voice not in self.narration_voices():
            return 400, {"error": "that voice is not available; narration may be off"}
        try:
            self._models()  # no key: say so now, in a plain sentence, before any job starts or feed is read
        except ProviderError as exc:
            return 503, {"error": str(exc)[:300]}
        request = {"sources": checked["ids"], "lens": checked["req"]["lens"].strip(), "insights": checked["count"]}
        if checked["req"].get("reading_level") is not None:
            request["reading_level"] = checked["req"]["reading_level"]
        if voice is not None:
            request["voice"] = voice
        try:
            return 202, self.jobs.submit(request)
        except RuntimeError:
            return 409, {"error": "compose capacity is full"}

    def change_job(self, headers, path: str, request: object) -> tuple[int, dict]:
        denied = self._authorize(headers)
        if denied:
            return denied
        if not isinstance(request, dict):
            return 400, {"error": "send a JSON object"}
        try:
            if path.startswith("/save/") and request == {}:
                return 200, self.jobs.save(path.removeprefix("/save/"))
            if path.startswith("/delete/") and request == {}:
                self.jobs.delete(path.removeprefix("/delete/"))
                return 200, {"deleted": path.removeprefix("/delete/")}
            if path.startswith("/restore/") and request == {}:
                return 200, self.jobs.restore(path.removeprefix("/restore/"))
            if path == "/retention" and set(request) <= {"apply"} and isinstance(request.get("apply", False), bool):
                return 200, self.jobs.retention(apply=request.get("apply", False))
            if path == "/update/migrate" and request == {"schema": "2"}:
                self.jobs.migrate_copy("2")
                return 200, {"generation": self.jobs.current_generation(), "migration": "ready"}
            if path == "/update/switch" and set(request) == {"target"} and isinstance(request["target"], str):
                self.jobs.switch(request["target"])
                return 200, {"generation": self.jobs.current_generation()}
            if path == "/update/rollback" and request == {}:
                result = self.jobs.rollback()
                return 200, {"exported_jobs": result["exported_jobs"]}
        except StoreError as exc:
            return 409 if "active jobs" in str(exc) else 400, {"error": str(exc)}
        return 400, {"error": "request does not match this change route"}

    def handle_source_probe(self, headers, body: bytes) -> tuple[int, dict]:
        """The page's "Check the address": {"url"} gives the candidate feeds behind a pasted address (none chosen).
        A full registry entry instead is read once as it stands. Nothing is saved either way; every request goes
        through the same guarded fetch as a brief."""
        denied = self._authorize(headers)
        if denied:
            return denied
        if not isinstance(self.source_service, sources_registry.SourceService):
            return 503, {"error": "this server has no sources file to add to"}
        try:
            request = self._json_body(body)
            if set(request) == {"url"}:
                return 200, self.source_service.discover(request["url"])
            return 200, self.source_service.probe(request)
        except discovery.Busy as exc:
            return 409, {"error": str(exc)}
        except (ValueError, sources_registry.SourceServiceError) as exc:
            return 400, {"error": str(exc)}

    def handle_source_register(self, headers, body: bytes) -> tuple[int, dict]:
        """The page's "Add to my sources": {candidate, label, pasted_url}, the candidate read again before it is
        written; or a full registry entry, probed first. Live on the next request, without a restart."""
        denied = self._authorize(headers)
        if denied:
            return denied
        if not isinstance(self.source_service, sources_registry.SourceService):
            return 503, {"error": "this server has no sources file to add to"}
        try:
            request = self._json_body(body)
            if "candidate" in request:
                return 201, self.source_service.register_candidate(request)
            return 201, {"source": self.source_service.register(request)}
        except (ValueError, sources_registry.SourceServiceError) as exc:
            return 400, {"error": str(exc)}

    def handle_lens_save(self, headers, body: bytes) -> tuple[int, dict]:
        """The page's lens form: {name, looks_for, register, reading_level, replaces}. A new lens gets its own id; an
        edit (`replaces` names one of your lenses) becomes that lens's newest revision, and briefs already made keep
        the revision they used. The older recipe shape {name, instruction, reading_level, previous} still works."""
        denied = self._authorize(headers)
        if denied:
            return denied
        if self.lens_store is None:
            return 503, {"error": "lens storage is not configured"}
        try:
            request = self._json_body(body)
            if "looks_for" in request:
                entry, written = self.lens_store.save_form(request)
            else:
                previous = request.pop("previous", None)
                entry, written = self.lens_store.save(request, previous=previous), True
        except lenses.StaleRevision as exc:
            return 409, {"error": str(exc)}
        except (ValueError, lenses.LensError) as exc:
            return 400, {"error": str(exc)}
        return (201 if written else 200), {"lens": entry.option(), "changed": written}

    def page(self) -> bytes:
        return page.build(self.latest, live=True, sources=self.sources().entries(),
                          needs_pass=bool(self.passphrase)).encode("utf-8")

    def handle_compose(self, headers, body: bytes) -> tuple[int, dict]:
        """The classic page's compose: one brief, composed while the request waits."""
        denied = self._authorize(headers)
        if denied:
            return denied
        checked, refused = self._compose_request(body, set())
        if refused:
            return refused
        try:
            model, checker = self._models()  # no key: say so before any feed is fetched
        except ProviderError as exc:
            return 503, {"error": str(exc)[:300]}
        if not self.lock.acquire(blocking=False):
            return 429, {"error": "a brief is already being composed; try again in a minute"}
        lens = checked["lens"]
        try:
            extra = {"checker": checker} if checker is not None else {}
            run = self.compose(lens=lens.instruction, lens_definition=lens, sources=checked["sources"], model=model,
                               count=checked["count"], **extra)
        except (pipeline.ComposeError, ProviderError, ValueError) as exc:
            return 502, {"error": str(exc)[:300]}
        finally:
            self.lock.release()
        self.latest = run["edition"]
        if self.out_dir is not None:
            self.out_dir.mkdir(parents=True, exist_ok=True)
            (self.out_dir / "latest-edition.json").write_text(
                json.dumps(self.latest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        return 200, self.latest


def _lens_meta(lens: lenses.Lens) -> dict:
    """What the page shows for one lens; your own lenses carry what the edit form needs."""
    meta = {"title": lens.name, "blurb": lens.blurb, "reading_level": lens.reading_level,
            "shape": dict(lens.shape or {}), "revision": lens.revision,
            "looks_for": lens.instruction if lens.editable else "", "editable": lens.editable,
            "register": lens.register.capitalize(), "register_choice": lens.register}
    if lens.editable:
        meta["revision_number"] = lens.number
        meta["previous"] = lens.previous or None
        meta["blurb"] = f"Your lens \u00b7 revision {lens.number}" + (f" \u00b7 {lens.register}" if lens.register else "")
    return meta


def proxy_problem(client_ip: str, method: str, headers, trusted, public_origin: str) -> str | None:
    """Behind a reverse proxy (`composer up` in the container): only the proxy's network may connect, the
    Host must be the public origin's, and a POST's Origin (when sent) must be exactly the public origin."""
    try:
        if ipaddress.ip_address(client_ip.split("%", 1)[0]) not in trusted:
            return "this server only answers its proxy"
    except ValueError:
        return "this server only answers its proxy"
    want = urlsplit(public_origin)
    host = (headers.get("Host") or "").strip().lower()
    if host_name(host) != (want.hostname or "") or (want.port and host != want.netloc.lower()):
        return "this server only answers requests for its public address"
    if method == "POST":
        origin = headers.get("Origin")
        if origin is not None and origin.rstrip("/").lower() != public_origin.rstrip("/").lower():
            return "change requests are only accepted from this server's own page"
        site = (headers.get("Sec-Fetch-Site") or "").strip().lower()
        if site and site not in ("same-origin", "none"):
            return "change requests are only accepted from this server's own page"
    return None


def _is_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip.split("%", 1)[0]).is_loopback
    except ValueError:
        return False


def parse_trusted(value: str):
    try:
        return ipaddress.ip_network(value.strip(), strict=False)
    except ValueError:
        raise SystemExit(f"refused: COMPOSER_TRUSTED_PROXY must be a network such as 172.30.65.0/24, not {value!r}")


def check_public_origin(value: str) -> str:
    o = urlsplit((value or "").strip())
    if o.scheme not in ("http", "https") or not o.hostname or o.path not in ("", "/") or o.query or o.username:
        raise SystemExit("refused: COMPOSER_PUBLIC_ORIGIN must be the address people open, such as "
                         "https://brief.example.com (with :port if it is not the default)")
    return f"{o.scheme}://{o.netloc}".lower()


def handler_for(app: App, *, local_only: bool = True, trusted=None, public_origin: str = ""):
    class Handler(BaseHTTPRequestHandler):
        server_version = "composer"
        sys_version = ""
        timeout = 30  # a client that stops sending is dropped, not waited on forever

        def _refused(self, method: str) -> bool:
            problem = request_problem(method, self.headers, local_only=local_only)
            if not problem and trusted is not None:
                if (method == "GET" and self.path == "/health" and _is_loopback(self.client_address[0])
                        and host_name(self.headers.get("Host", "")) in LOOPBACK_NAMES):
                    # the container's own health check: only /health, only from inside, only by a local name
                    problem = None
                else:
                    problem = proxy_problem(self.client_address[0], method, self.headers, trusted, public_origin)
            if problem:
                self._json(403, {"error": problem})
                return True
            return False

        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            self.end_headers()
            self.wfile.write(body)

        def _live_file(self) -> None:
            found = live_files.parse(self.path)
            got = live_files.read(app.jobs, *found, source_ids=app.source_ids()) if found else None
            if got is None:
                return self._json(404, {"error": "not found"})
            body, ctype = got
            if not ctype.startswith("audio/"):
                return self._send(200, body, ctype)
            try:
                handle = open(body, "rb")
            except OSError:
                return self._json(404, {"error": "not found"})
            with handle:
                self._send_audio(handle, os.fstat(handle.fileno()).st_size, ctype)

        def _send_audio(self, handle, size: int, ctype: str) -> None:
            start, end, status = 0, size - 1, 200
            rng = (self.headers.get("Range") or "").strip()
            m = re.fullmatch(r"bytes=(\d{0,15})-(\d{0,15})", rng)
            if m and (m.group(1) or m.group(2)):
                if m.group(1):
                    start = int(m.group(1))
                    end = min(int(m.group(2)), end) if m.group(2) else end
                else:
                    start = max(0, size - int(m.group(2)))
                if start > end:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{size}")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                status = 206
            length = max(0, end - start + 1)
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(length))
            self.send_header("Accept-Ranges", "bytes")
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cross-Origin-Resource-Policy", "same-origin")
            self.end_headers()
            handle.seek(start)
            while length > 0:
                block = handle.read(min(length, 1 << 16))
                if not block:
                    break
                self.wfile.write(block)
                length -= len(block)

        def _json(self, status: int, obj: dict) -> None:
            self._send(status, json.dumps(obj, ensure_ascii=False).encode("utf-8"), "application/json")

        def do_GET(self):  # noqa: N802
            if self._refused("GET"):
                return
            if app_static.send(self, self.path):
                return
            if self.path == "/":
                self.send_response(302)  # the app page; the 0.1 page with its compose form stays at /classic
                self.send_header("Location", app_static.PREFIX)
                self.send_header("Content-Length", "0")
                self.end_headers()
            elif self.path in ("/classic", "/index.html"):
                self._send(200, app.page(), "text/html; charset=utf-8")
            elif self.path == "/data/options.json":
                self._json(200, app.options())
            elif self.path.startswith(live_files.PREFIX):
                self._live_file()
            elif self.path == "/schedule":
                self._json(200, app.scheduler.status() if app.scheduler else {"enabled": False})
            elif self.path == "/api/latest":
                self._json(200, app.latest)
            elif self.path == "/health":
                self._json(200, app.jobs.health())
            elif self.path == "/shelf":
                self._json(200, app.jobs.index())
            elif self.path == "/latest":
                latest = app.jobs.latest()
                self._json(200, latest) if latest else self._json(404, {"error": "not found"})
            elif self.path.startswith("/status/"):
                try:
                    self._json(200, app.jobs.status(self.path.removeprefix("/status/")))
                except (OSError, ValueError, StoreError):
                    self._json(404, {"error": "not found"})
            else:
                self._json(404, {"error": "not found"})

        def do_POST(self):  # noqa: N802
            if self._refused("POST"):
                return
            routes = {"/api/compose", "/compose", "/retention", "/update/migrate", "/update/switch", "/update/rollback"}
            routes |= set(SERVICE_ROUTES)
            if self.path not in routes and not any(self.path.startswith(prefix) for prefix in ("/save/", "/delete/", "/restore/")):
                return self._json(404, {"error": "not found"})
            if self.path in ("/compose", *SERVICE_ROUTES) and not self.headers.get("Origin"):
                return self._json(403, {"error": "compose requests need a same-origin Origin header"})
            try:
                length = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                length = -1
            if length <= 0 or length > MAX_BODY:
                return self._json(413 if length > MAX_BODY else 400, {"error": "body missing or over 16 KB"})
            body = self.rfile.read(length)
            if self.path == "/compose":
                status, obj = app.submit_job(self.headers, body)
            elif self.path == "/api/compose":
                status, obj = app.handle_compose(self.headers, body)
            elif self.path in SERVICE_ROUTES:
                status, obj = getattr(app, SERVICE_ROUTES[self.path])(self.headers, body)
            else:
                try:
                    request = json.loads(body.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    status, obj = 400, {"error": "send a JSON object"}
                else:
                    status, obj = app.change_job(self.headers, self.path, request)
            self._json(status, obj)

        def log_message(self, fmt, *args):  # one short line per request, no headers or bodies
            print(f"{self.address_string()} {self.command} {self.path[:200]} {args[1] if len(args) > 1 else ''}",
                  flush=True)

    return Handler


def check_bind(host: str, passphrase: str, trusted=None) -> None:
    if host not in LOOPBACK and not passphrase and trusted is None:
        raise SystemExit("refused: to listen on a non-local address, name the proxy in front of it "
                         "(COMPOSER_TRUSTED_PROXY and COMPOSER_PUBLIC_ORIGIN) or set COMPOSER_SERVER_PASS "
                         "(anyone who can compose spends your API credit)")


def serve(app: App, host: str, port: int, *, trusted=None, public_origin: str = "", on_ready=None) -> None:
    check_bind(host, app.passphrase, trusted)
    httpd = ThreadingHTTPServer((host, port), handler_for(app, local_only=host in LOOPBACK, trusted=trusted,
                                                          public_origin=public_origin))
    if on_ready is not None:
        on_ready(httpd)
    _stop_on_sigterm()
    shown = "127.0.0.1" if host == "localhost" else (f"[{host}]" if ":" in host else host)
    print(f"composer serving on http://{shown}:{port}/  (Ctrl+C to stop)", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def _stop_on_sigterm() -> None:
    """`docker compose stop` and service managers send SIGTERM: stop the same clean way as Ctrl+C (a container's
    first process would otherwise ignore it until it is killed)."""
    import signal

    def stop(_signum, _frame):
        raise KeyboardInterrupt
    try:
        signal.signal(signal.SIGTERM, stop)
    except (ValueError, OSError, AttributeError):  # not the main thread, or no SIGTERM on this platform
        pass


def passphrase_from_env() -> str:
    return os.environ.get("COMPOSER_SERVER_PASS", "")
