"""Make a lens and edit it from the app page; the reading level and register written into the prompt.

The page's lens form posts {name, looks_for, register, reading_level, replaces} to /lens/save and then reads
/data/options.json: a saved lens must appear with editable true and what the edit form fills in, and an edit must
become the same lens's newest revision. The reading level the brief asks for (and a lens's register) must reach the
model as rules in the prompt."""
import http.client
import json
import multiprocessing
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from composer import lenses, pipeline, prompt as P, server, sources_registry
from composer.registry import BUNDLED

from helpers import JUDGE_ANSWERS, ScriptedGet, ScriptedModel, brief_for_fixtures, fixture, source

try:
    from claim_seal.adapters import ReplayJudge
except ImportError:  # the check step needs claim-seal: `pip install -e .`
    ReplayJudge = None

HARBOR = source()
QUARRY = source(id="quarry", label="Quarry Street Studio", url="https://example.org/quarry/feed.atom")


def form(**over):
    body = {"name": "Risk desk", "looks_for": "Look for risks a small team would miss.", "register": "sceptical",
            "reading_level": "plain", "replaces": None}
    body.update(over)
    return body


class LensFormRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.captured = []

        def compose(**kwargs):
            self.captured.append(kwargs)
            return {"edition": {"lens": kwargs["lens"], "cards": [], "sources": []}}
        sources = sources_registry.SourceService(Path(self.tmp.name) / "sources.json", bundled=BUNDLED,
                                                 get=ScriptedGet({}))
        self.app = server.App(sources.snapshot(), lambda: "model", source_service=sources, compose=compose,
                              lens_store=lenses.LensStore(Path(self.tmp.name) / "lenses"),
                              data_root=Path(self.tmp.name) / "data")
        quiet = type("Quiet", (server.handler_for(self.app),), {"log_message": lambda *a: None})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), quiet)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.port = self.httpd.server_address[1]

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.tmp.cleanup()

    def call(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {"Host": f"127.0.0.1:{self.port}"}
        if body is not None:
            headers.update({"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{self.port}",
                            server.CSRF_HEADER: server.CSRF_VALUE})
        conn.request(method, path, body=None if body is None else json.dumps(body), headers=headers)
        reply = conn.getresponse()
        doc = json.loads(reply.read())
        conn.close()
        return reply.status, doc

    def test_the_page_form_saves_a_lens_the_picker_and_the_edit_form_can_use(self):
        status, saved = self.call("POST", "/lens/save", form())
        self.assertEqual(status, 201, saved)
        lens = saved["lens"]
        self.assertEqual((lens["title"], lens["revision"], lens["register"]), ("Risk desk", 1, "sceptical"))
        status, options = self.call("GET", "/data/options.json")
        self.assertIn(lens["id"], options["lenses"])
        meta = options["lens_meta"][lens["id"]]
        self.assertTrue(meta["editable"])
        self.assertEqual(meta["looks_for"], "Look for risks a small team would miss.")
        self.assertEqual((meta["register_choice"], meta["reading_level"]), ("sceptical", "plain"))
        recipe = json.loads((Path(self.tmp.name) / "lenses" / lens["digest"] / "recipe.json").read_text())
        self.assertEqual(recipe["register"], "sceptical")
        for builtin in ("system-improvements", "second-order-effects", "raised-eyebrow"):
            self.assertFalse(options["lens_meta"][builtin]["editable"])

    def test_an_edit_is_the_same_lens_newest_revision_with_its_lineage(self):
        _, first = self.call("POST", "/lens/save", form())
        lens_id = first["lens"]["id"]
        status, edited = self.call("POST", "/lens/save", form(looks_for="Look for risks and who pays for them.",
                                                              register="deadpan", replaces=lens_id))
        self.assertEqual(status, 201, edited)
        self.assertEqual(edited["lens"]["id"], lens_id)
        self.assertEqual(edited["lens"]["revision"], 2)
        self.assertEqual(edited["lens"]["previous"], first["lens"]["digest"])
        _, options = self.call("GET", "/data/options.json")
        self.assertEqual(options["lenses"].count(lens_id), 1)  # one lens, its newest revision
        self.assertEqual(options["lens_meta"][lens_id]["looks_for"], "Look for risks and who pays for them.")
        self.assertEqual(options["lens_meta"][lens_id]["revision_number"], 2)
        # the older revision is kept unchanged: a brief made with it can still name it
        old = json.loads((Path(self.tmp.name) / "lenses" / first["lens"]["digest"] / "recipe.json").read_text())
        self.assertEqual(old["instruction"], "Look for risks a small team would miss.")
        # composing by the lens id uses the newest revision
        status, _ = self.call("POST", "/api/compose", {"sources": ["google-ai"], "lens": lens_id})
        self.assertEqual(status, 200)
        used = self.captured[-1]["lens_definition"]
        self.assertEqual((used.revision, used.register), (edited["lens"]["digest"], "deadpan"))
        # saving the same words again writes nothing new
        status, same = self.call("POST", "/lens/save", form(looks_for="Look for risks and who pays for them.",
                                                            register="deadpan", replaces=lens_id))
        self.assertEqual((status, same["changed"], same["lens"]["revision"]), (200, False, 2))

    def test_two_edits_of_the_same_revision_cannot_fork_the_lens(self):
        first = {"name": "Team focus", "instruction": "Look for durable team improvements.", "reading_level": "plain"}
        status, a = self.call("POST", "/lens/save", first)
        self.assertEqual(status, 201)
        base = a["lens"]["digest"]
        status, b = self.call("POST", "/lens/save", {**first, "instruction": "Edit one.", "previous": base})
        self.assertEqual(status, 201)
        status, c = self.call("POST", "/lens/save", {**first, "instruction": "Edit two.", "previous": base})
        self.assertEqual(status, 409, c)
        self.assertIn(b["lens"]["digest"], c["error"])  # it names the newest revision to edit instead
        revisions = sorted(p.parent.name for p in (Path(self.tmp.name) / "lenses").glob("*/recipe.json"))
        self.assertEqual(revisions, sorted([base, b["lens"]["digest"]]))  # nothing was written for the refused edit
        _, options = self.call("GET", "/data/options.json")
        self.assertEqual(options["lens_meta"][a["lens"]["id"]]["looks_for"], "Edit one.")
        # editing the newest revision still works
        status, d = self.call("POST", "/lens/save", {**first, "instruction": "Edit three.",
                                                       "previous": b["lens"]["digest"]})
        self.assertEqual((status, d["lens"]["revision"]), (201, 3))

    def test_the_form_is_checked(self):
        for body, words in ((form(register="snarky"), "register"), (form(reading_level="graduate"), "reading_level"),
                            (form(name=""), "name"), (form(looks_for="<<<LENS"), "delimiters"),
                            (form(replaces="raised-eyebrow"), "built-in"), (form(replaces="custom-000000000000"),
                                                                           "no lens"),
                            ({**form(), "extra": 1}, "send")):
            with self.subTest(body=body):
                status, doc = self.call("POST", "/lens/save", body)
                self.assertEqual(status, 400)
                self.assertIn(words, doc["error"])
        self.assertFalse(any((Path(self.tmp.name) / "lenses").glob("*/recipe.json")))


def _race_edit(root, previous, instruction, barrier, results):
    """One process's legacy edit of `previous`. Its write waits (up to 5 s) for the other process to reach its own
    write, so without a lock shared between processes both edits pass their "is this the newest revision" check."""
    store = lenses.LensStore(Path(root))
    write = store._write

    def gated(recipe):
        try:
            barrier.wait(5)
        except threading.BrokenBarrierError:
            pass
        return write(recipe)
    store._write = gated
    try:
        saved = store.save({"name": "Race", "instruction": instruction, "reading_level": "plain"}, previous=previous)
        results.put(("ok", saved.revision))
    except lenses.StaleRevision:
        results.put(("stale", ""))


class CrossProcessLensTests(unittest.TestCase):
    def test_two_processes_editing_the_same_revision_cannot_fork_the_lens(self):
        ctx = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as d:
            base = lenses.LensStore(Path(d)).save({"name": "Race", "instruction": "Look at the start.",
                                                    "reading_level": "plain"})
            barrier, results = ctx.Barrier(2), ctx.Queue()
            workers = [ctx.Process(target=_race_edit, args=(d, base.revision, f"Edit from process {n}.", barrier,
                                                            results)) for n in range(2)]
            for w in workers:
                w.start()
            outcomes = sorted(results.get(timeout=60)[0] for _ in workers)
            for w in workers:
                w.join(30)
            revisions = sorted(p.parent.name for p in Path(d).glob("*/recipe.json"))
            heads = lenses.LensStore(Path(d)).entries()
        self.assertEqual([w.exitcode for w in workers], [0, 0])
        self.assertEqual(outcomes, ["ok", "stale"])  # one edit lands, the other is told the lens changed
        self.assertEqual(len(revisions), 2)  # the first revision and one edit: no hidden fork
        self.assertEqual([(h.number, h.previous) for h in heads], [(2, base.revision)])


class ReadingLevelPromptTests(unittest.TestCase):
    def fetched(self):
        from composer.adapters import rss_or_atom
        return {HARBOR.id: rss_or_atom.fetch(HARBOR, ScriptedGet({HARBOR.url: fixture("feed-rss.xml")})),
                QUARRY.id: rss_or_atom.fetch(QUARRY, ScriptedGet({QUARRY.url: fixture("feed-atom.xml")}))}

    def test_each_level_writes_its_own_rule_into_the_prompt(self):
        texts = {}
        for level in lenses.READING_LEVELS:
            text, info = P.build("what changed", [HARBOR, QUARRY], self.fetched(), 3, reading_level=level)
            head = text.split(P.MATERIAL_MARKER, 1)[0]
            self.assertIn(f"READING LEVEL: {level}. {P.READING_LEVEL_TEXT[level]}", head)
            self.assertEqual(info["reading_level"], level)
            texts[level] = head
        self.assertIn("at most 20 words a sentence", texts["plain"])
        self.assertNotIn("at most 20 words a sentence", texts["technical"])
        self.assertEqual(len(set(texts.values())), 3)
        with self.assertRaises(ValueError):
            P.build("x", [HARBOR], self.fetched(), 3, reading_level="graduate")

    def test_a_register_is_a_rule_too_and_absent_when_not_set(self):
        text, _ = P.build("x", [HARBOR, QUARRY], self.fetched(), 3, register="sceptical")
        self.assertIn("REGISTER: Sceptical:", text)
        text, _ = P.build("x", [HARBOR, QUARRY], self.fetched(), 3)
        self.assertNotIn("REGISTER:", text)

    def test_the_compose_request_level_reaches_the_model(self):
        prompts = []

        def model(prompt, timeout=None):
            prompts.append(prompt)
            raise pipeline.ComposeError("stop after the first prompt")
        definition = lenses.Lens("ad-hoc", "Your words", "", "what changed", "technical", register="deadpan")
        with self.assertRaises(pipeline.ComposeError):
            pipeline.write("what changed", [HARBOR, QUARRY], self.fetched(), model, 3, lens_definition=definition)
        self.assertIn("READING LEVEL: technical.", prompts[0])
        self.assertIn("REGISTER: Deadpan:", prompts[0])
        prompts.clear()
        with self.assertRaises(pipeline.ComposeError):
            pipeline.write("what changed", [HARBOR, QUARRY], self.fetched(), model, 3)
        self.assertIn("READING LEVEL: standard.", prompts[0])


@unittest.skipIf(ReplayJudge is None, "claim-seal is not installed (pip install -e .)")
class NamedLensBriefTests(unittest.TestCase):
    def test_a_brief_under_a_saved_lens_shows_its_name_and_records_its_revision_level_and_register(self):
        quarry = source(id="quarry", label="Quarry Street Studio", url="https://example.org/quarry/atom.xml")
        get = ScriptedGet({HARBOR.url: fixture("feed-rss.xml"), quarry.url: fixture("feed-atom.xml")})
        with tempfile.TemporaryDirectory() as d:
            lens, _ = lenses.LensStore(Path(d)).save_form(form(reading_level="standard"))
        model = ScriptedModel([brief_for_fixtures()], ReplayJudge(JUDGE_ANSWERS))
        run = pipeline.compose(lens=lens.instruction, sources=[HARBOR, quarry], model=model, count=3, get=get,
                               lens_definition=lens)
        edition = run["edition"]
        self.assertEqual(edition["lens"], "Risk desk")
        self.assertEqual((edition["lens_definition"]["revision"], edition["lens_definition"]["reading_level"],
                          edition["lens_definition"]["register"]), (lens.revision, "standard", "sceptical"))
        self.assertIn("REGISTER: Sceptical:", model.prompts[0])
        # words of your own (no named lens) are still shown as they were written
        model = ScriptedModel([brief_for_fixtures()], ReplayJudge(JUDGE_ANSWERS))
        run = pipeline.compose(lens="local data handling", sources=[HARBOR, quarry], model=model, count=3, get=get)
        self.assertEqual(run["edition"]["lens"], "local data handling")


if __name__ == "__main__":
    unittest.main()
