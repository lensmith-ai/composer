"""Optional narration: detect-and-reuse without changing anything, the script the page shows is the script that
was rendered, every failure leaves a text-only brief, and narration off leaves no player or voice picker."""
import hashlib
import http.client
import json
import os
import threading
import time
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest import mock

from helpers import FIXTURE_TRANSCRIPT
from install_helpers import FakeRender, fake_check, fake_home, fake_model_pair, snapshot

from composer import demo, home as H, installer, lifecycle as L, narration as N, settings as S
from composer.registry import Registry
from composer.scheduler import chain
from composer.server import CSRF_VALUE, App, handler_for

ON = {"enabled": True, "engine": "kokoro-onnx", "voices": list(N.VOICES), "max_bytes": 120000, "max_seconds": 30}
OFF = dict(S.DEFAULTS["narration"])


def edition(transcript=FIXTURE_TRANSCRIPT):
    ed = demo.load()
    ed = dict(ed, transcript=transcript) if transcript is not None else {k: v for k, v in ed.items()
                                                                         if k != "transcript"}
    return ed


class Served:
    """A real server with the real job store, narration hooked to finished jobs, and a fixture compose."""

    def __init__(self, tmp: Path, ncfg: dict, render, transcript=FIXTURE_TRANSCRIPT):
        self.narrator = N.Narrator(ncfg, tmp, render=render)
        ed = edition(transcript)
        self.app = App(Registry.load(None), lambda: object(), data_root=tmp / "data", settings={"narration": ncfg},
                       compose=lambda **_: {"edition": ed, "result": {}, "fetched": {}},
                       on_finished=chain(lambda j: self.narrator.on_finished(j)))
        self.narrator.attach(self.app.jobs)
        quiet = type("Q", (handler_for(self.app, local_only=True),), {"log_message": lambda *a: None})
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), quiet)
        self.port = self.httpd.server_address[1]
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def req(self, method, path, body=None, headers=None):
        c = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        h = {"Host": f"127.0.0.1:{self.port}"}
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            h.update({"Content-Type": "application/json", "X-Composer-CSRF": CSRF_VALUE,
                      "Origin": f"http://127.0.0.1:{self.port}"})
        h.update(headers or {})
        c.request(method, path, body=data, headers=h)
        r = c.getresponse()
        out = (r.status, r.read(), dict(r.getheaders()))
        c.close()
        return out

    def compose(self, **extra):
        status, body, _ = self.req("POST", "/compose", {"sources": ["google-ai"], "lens": "test", "insights": 5,
                                                         **extra})
        assert status == 202, body
        job = json.loads(body)["job"]
        self.app.jobs.wait(job, 10)
        deadline = time.monotonic() + 10  # the narration hook runs just after the job's final phase is written
        while self.app.jobs.status(job).get("audio_state") in (None, "generating") and time.monotonic() < deadline:
            time.sleep(0.02)
        return job

    def job(self, job):
        return json.loads(self.req("GET", f"/data/live/{job}/job.json")[1])


class TranscriptParityTests(unittest.TestCase):
    """The words the page's transcript sheet shows are the words the engine rendered."""

    def test_the_transcript_the_page_shows_is_the_text_that_was_rendered(self):
        with fake_home() as home:
            render = FakeRender()
            s = Served(home, ON, render)
            try:
                job = s.compose(voice="bf_emma")
                rec = s.job(job)
                self.assertEqual(rec["audio_state"], "ready")
                self.assertEqual(rec["audio"]["voice"], "bf_emma")
                composed = json.loads(s.req("GET", f"/data/live/{job}/composed.json")[1])
                shown = composed["transcript"].strip()  # what the page puts in the sheet: record.transcript.trim()
                txt = s.req("GET", f"/data/live/{job}/transcript.txt")[1].decode("utf-8").strip()
                status, audio, headers = s.req("GET", f"/data/live/{job}/{rec['audio']['file']}")
                self.assertEqual(status, 200)
                rendered = audio[3:].decode("utf-8")  # the fake engine wrote exactly the text it was given
                self.assertEqual(len(render.calls), 1)
                self.assertEqual(rendered, render.calls[0]["text"])
                self.assertEqual(shown, FIXTURE_TRANSCRIPT)
                self.assertEqual(txt, shown)
                self.assertEqual(N.canonical_words(shown), N.canonical_words(rendered))
                self.assertEqual(rec["audio"]["text_sha256"], hashlib.sha256(rendered.encode()).hexdigest())
                self.assertEqual(headers["Content-Type"], "audio/mpeg")
            finally:
                s.close()

    def test_the_page_reads_the_transcript_from_the_record_and_keeps_it_apart_from_the_player(self):
        from helpers import ROOT
        js = (ROOT / "composer" / "web" / "app" / "app.js").read_text(encoding="utf-8")
        self.assertIn('var transcript=(LIVE.record&&typeof LIVE.record.transcript==="string")'
                      '?LIVE.record.transcript.trim():"";', js)
        self.assertIn('transcriptBtn.addEventListener("click",function(){openTranscript(transcript);});', js)
        self.assertIn("transcriptBody.textContent=text;", js)
        self.assertIn('var dir=DATA_ROOT+"/live/"+job+"/";', js)
        self.assertIn('jget(dir+"composed.json")', js)
        self.assertIn('var audioFile=c.voice?("composer-"+c.voice+".mp3"):null;', js)

    def test_a_long_script_is_cut_the_same_for_the_page_and_the_engine(self):
        script = "word " * 50000
        display, render, truncated = N.prepare_text(script, budget=2000)
        self.assertTrue(truncated)
        self.assertLessEqual(len(render.encode()), 2000)
        self.assertEqual(N.canonical_words(display), N.canonical_words(render))
        display, render, truncated = N.prepare_text("one  two\n\nthree")
        self.assertEqual((display, render, truncated), ("one  two\n\nthree", "one two three", False))


class FailureIsTextOnlyTests(unittest.TestCase):
    def assert_text_only(self, s, job, reason_part):
        rec = s.job(job)
        self.assertEqual(rec["audio_state"], "failed")
        self.assertIn(reason_part, rec["audio"]["reason"])
        self.assertEqual(rec["phase"], "verified")  # the brief itself is fine
        self.assertEqual(s.req("GET", f"/data/live/{job}/composer-af_heart.mp3")[0], 404)
        self.assertEqual(list(Path(s.app.jobs.job_dir(job)).glob("*narration*")), [])
        self.assertEqual(s.req("POST", f"/save/{job}", {})[0], 200)  # and it can still be saved
        self.assertEqual(json.loads(s.req("GET", f"/data/live/{job}/composed.json")[1])["transcript"].strip(),
                         FIXTURE_TRANSCRIPT)

    def test_engine_failure(self):
        with fake_home() as home:
            s = Served(home, ON, FakeRender(fail=True))
            try:
                self.assert_text_only(s, s.compose(), "crashed")
            finally:
                s.close()

    def test_engine_says_ok_but_writes_nothing(self):
        def liar(**kw):
            return {"ok": True, "file": str(kw["out_base"]) + ".mp3", "format": "mp3"}
        with fake_home() as home:
            s = Served(home, ON, liar)
            try:
                self.assert_text_only(s, s.compose(), "not there")
            finally:
                s.close()

    def test_a_brief_without_a_script(self):
        with fake_home() as home:
            s = Served(home, ON, FakeRender(), transcript=None)
            try:
                job = s.compose()
                rec = s.job(job)
                self.assertEqual(rec["audio_state"], "failed")
                self.assertIn("no narration script", rec["audio"]["reason"])
            finally:
                s.close()

    def test_the_real_runtime_missing_and_a_timeout(self):
        with fake_home() as home:
            cfg = dict(ON, model_path=str(home / "none.onnx"), voices_path=str(home / "none.bin"), python="")
            with mock.patch.object(N, "has_runtime_here", return_value=False):
                s = Served(home, cfg, None)
                try:
                    self.assert_text_only(s, s.compose(), "runtime is not installed")
                finally:
                    s.close()
            slow = home / "slow.py"
            slow.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
            with mock.patch.object(N, "WORKER", slow):
                with self.assertRaises(N.NarrationError) as caught:
                    N.run_worker(Path(os.sys.executable), {"mode": "render"}, home=home, timeout=1)
                self.assertIn("longer than 1 s", str(caught.exception))

    def test_a_restart_during_narration_leaves_a_text_only_brief(self):
        with fake_home() as home:
            gate = threading.Event()

            def stuck(**kw):
                gate.wait(5)
                raise N.NarrationError("stopped")
            s = Served(home, ON, stuck)
            try:
                status, body, _ = s.req("POST", "/compose", {"sources": ["google-ai"], "lens": "x", "insights": 5})
                job = json.loads(body)["job"]
                s.app.jobs.wait(job, 10)
                deadline = time.monotonic() + 5
                while s.job(job).get("audio_state") != "generating" and time.monotonic() < deadline:
                    time.sleep(0.02)
                from composer.job_store import JobStore
                JobStore(home / "data", worker=None)  # what a restart does first
                rec = json.loads((Path(s.app.jobs.job_dir(job)) / "job.json").read_text())
                self.assertEqual(rec["audio_state"], "failed")
                self.assertIn("restart", rec["audio"]["reason"])
            finally:
                gate.set()
                s.close()


class NarrationOffTests(unittest.TestCase):
    def test_off_means_no_voices_no_player_and_no_voice_accepted(self):
        with fake_home() as home:
            render = FakeRender()
            s = Served(home, OFF, render)
            try:
                opts = json.loads(s.req("GET", "/data/options.json")[1])
                self.assertEqual(opts["voices"], [])
                self.assertFalse(opts["narration"]["enabled"])
                job = s.compose()
                self.assertEqual(s.job(job)["audio_state"], "off")
                self.assertEqual(render.calls, [])
                status, body, _ = s.req("POST", "/compose", {"sources": ["google-ai"], "lens": "x", "voice": "af_heart"})
                self.assertEqual(status, 400)
            finally:
                s.close()

    def test_on_lists_the_working_voices(self):
        frag = N.options_fragment({"narration": dict(ON, voices=["am_michael"])})
        self.assertEqual(frag["voices"], ["am_michael"])
        self.assertTrue(frag["narration"]["enabled"])
        self.assertEqual(N.options_fragment({"narration": dict(ON, enabled=False)})["voices"], [])


class AudioRouteTests(unittest.TestCase):
    def test_ranges_and_only_allowed_names(self):
        with fake_home() as home:
            s = Served(home, ON, FakeRender())
            try:
                job = s.compose()
                name = s.job(job)["audio"]["file"]
                full = s.req("GET", f"/data/live/{job}/{name}")[1]
                status, part, headers = s.req("GET", f"/data/live/{job}/{name}", headers={"Range": "bytes=0-9"})
                self.assertEqual((status, part), (206, full[:10]))
                self.assertEqual(headers["Content-Range"], f"bytes 0-9/{len(full)}")
                self.assertEqual(s.req("GET", f"/data/live/{job}/{name}", headers={"Range": "bytes=-5"})[1], full[-5:])
                self.assertEqual(s.req("GET", f"/data/live/{job}/{name}", headers={"Range": "bytes=99999-"})[0], 416)
                for path in (f"/data/live/{job}/check.json", f"/data/live/{job}/../{job}/job.json",
                             f"/data/live/{job}/composer-xx_evil.mp3", f"/data/live/{job}/composer-am_michael.mp3",
                             "/data/live/job-zzzz/job.json", f"/data/live/{job}/saved.json", "/data/options.json/x"):
                    with self.subTest(path=path):
                        self.assertEqual(s.req("GET", path)[0], 404)
            finally:
                s.close()


class DetectAndReuseTests(unittest.TestCase):
    def test_detect_finds_pairs_and_names_what_it_cannot_use(self):
        with fake_home() as home:
            fake_model_pair(home / "models" / "kokoro")
            (home / "Downloads" / "old").mkdir(parents=True)
            (home / "Downloads" / "old" / "kokoro-v1_0.pth").write_bytes(b"torch")
            (home / ".cache" / "huggingface" / "hub" / "models--hexgrad--Kokoro-82M").mkdir(parents=True)
            own = home / ".lensmith-composer"
            fake_model_pair(own / "models" / "kokoro")
            before = snapshot(home)
            found = N.detect(user_home=home, env={}, skip=(str(own),), probe_servers=False)
            self.assertEqual(snapshot(home), before)
            kinds = [(c["kind"], Path(c.get("model") or c.get("path")).parent.name) for c in found]
            self.assertIn(("files", "kokoro"), kinds)
            self.assertEqual(len([c for c in found if c["kind"] == "files"]), 1)  # not our own copy
            self.assertTrue(any(c["kind"] == "unusable" and c["path"].endswith(".pth") for c in found))
            self.assertTrue(any(c["kind"] == "unusable" and "huggingface" in c["path"] for c in found))
            env_found = N.detect(user_home=home / "nowhere", env={"KOKORO_MODEL_PATH": str(home / "models" / "kokoro")},
                                 probe_servers=False)
            self.assertEqual([c["found_by"] for c in env_found], ["KOKORO_MODEL_PATH"])

    def test_check_files_matches_the_pinned_release_and_only_reads(self):
        with fake_home() as home:
            model, voices, pinned = fake_model_pair(home / "k")
            with mock.patch.dict(N.PINNED, pinned):
                before = snapshot(home / "k")
                ok, why, info = N.check_files(model, voices)
                self.assertTrue(ok, why)
                self.assertEqual(snapshot(home / "k"), before)
                model.write_bytes(model.read_bytes()[:-1] + b"!")
                self.assertFalse(N.check_files(model, voices)[0])

    def answers(self, home, use="existing", accept=True):
        path = home.parent / "answers.toml"
        path.write_text(f"[provider]\nkind = \"none\"\n[narration]\nenabled = true\naccept_licences = "
                        f"{'true' if accept else 'false'}\nuse = \"{use}\"\n", encoding="utf-8")
        return str(path)

    def setup(self, home, answers_file, **kw):
        return installer.run(home=home / ".lensmith-composer", data=None, answers_file=answers_file,
                             assume_yes=False, reconfigure=[], data_only=False, out=lambda *_: None,
                             interactive=False, install=lambda base, log: Path(os.sys.executable), **kw)

    def test_existing_kokoro_is_reused_read_only_and_survives_uninstall(self):
        with fake_home() as home:
            model, voices, pinned = fake_model_pair(home / "models" / "kokoro")
            before = snapshot(home / "models")
            detect = lambda skip: N.detect(user_home=home, env={}, skip=skip, probe_servers=False)  # noqa: E731
            with mock.patch.dict(N.PINNED, pinned):
                self.setup(home, self.answers(home), detect=detect, check=fake_check)
            target = home / ".lensmith-composer"
            cfg = S.load(target / "data")
            self.assertEqual((cfg["narration"]["engine"], cfg["narration"]["reused"]), ("kokoro-onnx", True))
            self.assertEqual(cfg["narration"]["model_path"], str(model))
            self.assertFalse((target / "models").exists())  # no second copy
            reused = [e for e in H.load_manifest(target)["entries"] if e["kind"] == "reused"]
            self.assertEqual(sorted(e["path"] for e in reused), sorted([str(model.resolve()), str(voices.resolve())]))
            self.assertEqual({e["sha256"] for e in reused}, {pinned[N.MODEL_FILE][0], pinned[N.VOICES_FILE][0]})
            self.assertEqual(snapshot(home / "models"), before)  # checksums and times unchanged
            L.uninstall(target, target / "data", delete_data=True, confirm=lambda q: True)
            self.assertEqual(snapshot(home / "models"), before)

    def test_a_mismatched_existing_kokoro_is_reported_and_left_alone(self):
        with fake_home() as home:
            fake_model_pair(home / "models" / "kokoro")
            before = snapshot(home / "models")
            lines = []
            detect = lambda skip: N.detect(user_home=home, env={}, skip=skip, probe_servers=False)  # noqa: E731
            installer.run(home=home / ".lensmith-composer", data=None, answers_file=self.answers(home),
                          assume_yes=False, reconfigure=[], data_only=False, out=lines.append, interactive=False,
                          detect=detect, check=fake_check, install=lambda base, log: Path(os.sys.executable))
            self.assertFalse(S.load(home / ".lensmith-composer" / "data")["narration"]["enabled"])
            self.assertTrue(any("SHA-256 does not match" in ln or "pinned size" in ln or "is " in ln for ln in lines))
            self.assertEqual(snapshot(home / "models"), before)

    def test_licences_must_be_accepted(self):
        with fake_home() as home:
            self.setup(home, self.answers(home, use="download", accept=False),
                       download=lambda *a, **k: self.fail("downloaded without the licences accepted"))
            self.assertFalse(S.load(home / ".lensmith-composer" / "data")["narration"]["enabled"])

    def test_nothing_found_means_text_only_and_no_download(self):
        with fake_home() as home:
            self.setup(home, self.answers(home), detect=lambda skip: [],
                       download=lambda *a, **k: self.fail("downloaded without being asked"))
            self.assertFalse(S.load(home / ".lensmith-composer" / "data")["narration"]["enabled"])

    def test_licences_are_shown_before_the_question(self):
        text = "\n".join(N.LICENCES)
        for part in ("Apache-2.0", "GPL-3.0", "eSpeak NG", "MIT"):
            self.assertIn(part, text)


if __name__ == "__main__":
    unittest.main()
