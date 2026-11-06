"""The app page (composer/web/app): what it may load, what it may send, and how it is served.

All offline: the page's files are read as text and the server is started on 127.0.0.1 with no key.
"""
import http.client
import json
import re
import threading
import unittest
from html.parser import HTMLParser
from http.server import ThreadingHTTPServer

from composer import app_static, server
from composer.registry import BUNDLED, Registry, read_file

from helpers import ROOT

APP = ROOT / "composer" / "web" / "app"
WINDOW = ROOT / "composer" / "web" / "window"
ROUTES = {"/compose", "/health", "/status/", "/source/probe", "/source/register", "/lens/save", "/lens/delete"}
DATA_FILES = {"options.json", "index.json", "composed.json", "receipts.json", "job.json", "transcript.txt"}


def text(name):
    return (APP / name).read_text(encoding="utf-8")


class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.data_in = []
        self._open = None

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))
        self._open = (tag, dict(attrs))

    def handle_data(self, data):
        if self._open and self._open[0] == "script" and data.strip():
            self.data_in.append((self._open[1], data))

    def handle_endtag(self, tag):
        self._open = None


def parsed():
    p = Tags()
    p.feed(text("index.html"))
    return p


class AppFilesTests(unittest.TestCase):
    def test_served_list_is_exactly_the_folder(self):
        on_disk = sorted(f.name for f in APP.iterdir() if f.is_file())
        self.assertEqual(on_disk, sorted(app_static.FILES))

    def test_unchanged_scripts_are_the_reviewed_window_copies(self):
        for name in ("sand-engine.js", "composer-entry-transition.js", "entry-transition.css"):
            self.assertEqual((APP / name).read_bytes(), (WINDOW / name).read_bytes(), name)

    def test_page_loads_only_its_own_files(self):
        p = parsed()
        for tag, attrs in p.tags:
            for key in ("src", "href"):
                if tag in ("script", "link", "img", "iframe", "audio", "source") and attrs.get(key):
                    ref = attrs[key]
                    self.assertNotRegex(ref, r"^[a-z][a-z0-9+.-]*:|^//", f"{tag} {key}={ref}")
                    self.assertIn(ref, app_static.FILES, f"{tag} {key}={ref} is not an app file")
        scripts = [a.get("src") for t, a in p.tags if t == "script" and a.get("src")]
        self.assertEqual(scripts, ["boot.js", "boot-note.js", "app.js", "sand-engine.js", "composer-entry-transition.js"])

    def test_no_inline_script_style_or_handlers(self):
        p = parsed()
        for attrs, data in p.data_in:
            self.assertEqual(attrs.get("type"), "application/json", "inline script code: " + data[:60])
            json.loads(data)
        for tag, attrs in p.tags:
            self.assertNotIn("style", attrs, f"style attribute on <{tag}>")
            self.assertFalse([k for k in attrs if k.startswith("on")], f"handler attribute on <{tag}>")
        self.assertFalse([t for t, a in p.tags if t == "style"])

    def test_scripts_inject_no_inline_style_and_no_handler_attributes(self):
        for name in ("app.js", "boot.js", "boot-note.js"):
            js = text(name)
            with self.subTest(name):
                self.assertNotRegex(js, r'createElement\(\s*["\']style["\']\s*\)')
                self.assertNotRegex(js, r'\sstyle=\\?["\']')
                self.assertNotRegex(js, r'\son[a-z]+=\\?["\']')
                self.assertNotRegex(js, r"\beval\(|new Function\(|setTimeout\(\s*[\"']|setInterval\(\s*[\"']")
                self.assertNotRegex(js, r"setAttribute\(\s*[\"']style")

    def test_every_request_is_same_origin_and_known(self):
        js = text("app.js")
        self.assertNotRegex(js, r"""fetch\(\s*["'](?:https?:)?//""")
        self.assertNotIn("XMLHttpRequest", js)
        self.assertNotIn("sendBeacon", js)
        self.assertNotIn("WebSocket", js)
        self.assertIn('var DATA_ROOT="/data";', js)
        for path in re.findall(r"""fetch\(\s*["'](/[^"'?]*)""", js):
            self.assertTrue(any(path == r or (r.endswith("/") and path.startswith(r)) for r in ROUTES | {"/data/live/"}),
                            path)
        top = re.findall(r"""DATA_ROOT\+["']/([a-z.]+)["']""", js)
        per_job = re.findall(r"""DATA_ROOT\+["']/live/["']\+(?:job|self\.job|this\.job)\+["']/([a-z.]*)["']""", js)
        self.assertEqual(set(top), {"options.json", "index.json"})
        self.assertTrue(per_job)
        for name in per_job:
            self.assertIn(name, DATA_FILES | {"", "composer-"}, name)

    def test_every_change_request_carries_the_anti_forgery_header(self):
        js = text("app.js")
        posts = re.findall(r'method:"POST"[^}]{0,80}', js)
        self.assertGreaterEqual(len(posts), 3)
        self.assertNotIn('headers:{"Content-Type":"application/json"}', js)
        self.assertEqual(js.count("headers:cwHeaders()"), len(posts))
        boot = text("boot.js")
        self.assertIn("'X-Composer-Pass'", boot)
        self.assertIn("'X-Composer-CSRF': 'same-origin'", boot)  # the engine's anti-forgery header
        self.assertIn("'Content-Type': 'application/json'", boot)

    def test_the_page_links_offer_sends_only_the_kind_and_the_address_and_sets_text_not_markup(self):
        js = text("app.js")
        start = js.index("function showPageLinks(o){")
        end = js.index("check.onclick=function()", start)
        offer = js[start:end]
        self.assertIn('picked={kind:"html-index",url:o.url}', offer)
        self.assertEqual(offer.count("picked="), 1)  # the only thing a pick records is the kind and the address
        self.assertNotIn("innerHTML", offer)
        self.assertNotIn("href", offer)  # addresses are shown as text, never made links
        self.assertIn("Nothing is saved until you add it.", offer)

    def test_escape_helpers_cover_quotes(self):
        js = text("app.js")
        self.assertIn('.replace(/"/g,"&quot;").replace(/\'/g,"&#39;")', js)
        self.assertEqual(js.count(r"""replace(/[&<>"']/g"""), 3)

    def test_private_and_test_only_material_is_gone(self):
        blob = "\n".join(text(n) for n in ("index.html", "app.js", "app.css", "boot.js", "boot-note.js")).lower()
        for word in ("?uat=", "/staging/", "sop-runs", "/runs?run=", "america/chicago", "actor:",
                     "satire.json", "claims.json", "lensmith", "test retrieval", "mock row", "stand-in"):
            self.assertNotIn(word, blob, word)
        raw = "\n".join(text(n) for n in ("index.html", "app.js", "app.css"))
        self.assertNotRegex(raw, r"(?<![A-Za-z])(?:uat|UAT)(?=[A-Z_\-=]|\b)")
        js = text("app.js")
        self.assertNotRegex(js, r'\bid==="(?:runs|hn)"|s\.id==="runs"|feed==="runs"')

    def test_only_the_bundled_sources_appear_in_the_demo_edition(self):
        p = parsed()
        data = json.loads([d for a, d in p.data_in if a.get("id") == "ed-data"][0])
        allowed = {s["id"] for s in json.loads((ROOT / "composer" / "sources.json").read_text())["sources"]}
        used = {x.get("feed") for sec in data.get("sections", []) for x in sec.get("sources", []) if x.get("feed")}
        self.assertLessEqual(used, allowed)

    def test_text_only_mode_hides_the_player_and_voice(self):
        css = text("app.css")
        for sel in ("html.cw-text-only .aplay", "html.cw-text-only .speedrow"):
            self.assertIn(sel, css)
        js = text("app.js")
        self.assertIn('if(!cwNarrationOn(CMP.opts))return [{t:"Compose from "},{slot:"sources"},{t:" through the "},'
                      '{slot:"lens"},{t:" lens"}];', js)
        self.assertIn("voice:cwNarrationOn(o)?(o.voices||[])[0]:null,", js)
        boot = text("boot.js")
        self.assertIn("o.voices.length > 0", boot)

    def test_no_wordmark_inside_the_phone(self):
        html = text("index.html")
        self.assertNotIn('class="cmpmast"', html)
        self.assertIn('<div class="mk" aria-hidden="true">&nbsp;</div>', html)


class AppServingTests(unittest.TestCase):
    def setUp(self):
        app = server.App(Registry(read_file(BUNDLED)), lambda: "model")
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.handler_for(app, local_only=True))
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def get(self, path, host=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        c.request("GET", path, headers={"Host": host or f"127.0.0.1:{self.port}"})
        r = c.getresponse()
        body = r.read()
        c.close()
        return r.status, dict(r.getheaders()), body

    def test_app_page_and_files_with_security_headers(self):
        for path in ["/app/", "/app/index.html", "/app/?job=x&demo=1"] + [f"/app/{n}" for n in app_static.FILES]:
            with self.subTest(path=path):
                status, headers, body = self.get(path)
                self.assertEqual(status, 200)
                csp = headers["Content-Security-Policy"]
                for part in ("default-src 'none'", "script-src 'self'", "style-src 'self'", "connect-src 'self'",
                             "frame-ancestors 'self'", "base-uri 'none'"):
                    self.assertIn(part, csp)
                self.assertNotIn("unsafe-inline", csp)
                self.assertNotIn("http", csp)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
                self.assertEqual(headers["X-Frame-Options"], "SAMEORIGIN")
                self.assertTrue(body)
        status, headers, _ = self.get("/app")
        self.assertEqual((status, headers["Location"]), (301, "/app/"))

    def test_nothing_else_is_served_from_the_app_prefix(self):
        for path in ("/app/../server.py", "/app/%2e%2e/server.py", "/app/window.css", "/app/web/app/app.js",
                     "/app//app.js", "/app/app.js/", "/app/APP.JS"):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)

    def test_rebinding_host_is_refused_for_the_app_too(self):
        self.assertEqual(self.get("/app/", host=f"rebind.example:{self.port}")[0], 403)

    def test_root_opens_the_app_and_the_classic_page_stays(self):
        status, headers, body = self.get("/")
        self.assertEqual(status, 302)
        self.assertEqual(headers.get("Location"), "/app/")
        status, headers, body = self.get("/classic")
        self.assertEqual(status, 200)
        self.assertIn(b"<html", body)


if __name__ == "__main__":
    unittest.main()
