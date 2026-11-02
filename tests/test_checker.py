"""An optional separate checker model: the writer writes, the checker makes every claim-seal call.

Setup asks "Check claims with the same model?" after the writer's key; an answers file takes a [checker] table with
the same keys as [provider]. The checker's key is stored in the same 0600 key file under its own name."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from install_helpers import FAKE_KEY, fake_home

from composer import cli, doctor, home as H, installer, pipeline, providers, receipts, server, settings as S
from composer.registry import Registry

from helpers import (JUDGE_ANSWERS, WRITER_MARK, ScriptedGet, ScriptedModel, ScriptedTransport, brief_for_fixtures,
                     fixture, source)

try:
    from claim_seal.adapters import ReplayJudge
except ImportError:  # the check step needs claim-seal: `pip install -e .`
    ReplayJudge = None

CHECKER_VALUE = "test-checker-value-for-setup-only"
HARBOR = source()
QUARRY = source(id="quarry", label="Quarry Street Studio", url="https://example.org/quarry/atom.xml")
GET = {HARBOR.url: fixture("feed-rss.xml"), QUARRY.url: fixture("feed-atom.xml")}


def install(home: Path, answers: str = "", **kw) -> Path:
    target = home / ".lensmith-composer"
    path = None
    if answers:
        path = home.parent / "answers.toml"
        path.write_text(answers, encoding="utf-8")
    installer.run(home=target, data=None, answers_file=str(path) if path else None, assume_yes=not answers and
                  not kw.get("interactive"), reconfigure=[], data_only=False, out=kw.pop("out", lambda *_: None),
                  interactive=kw.pop("interactive", False), **kw)
    return target


SEPARATE = """[provider]
kind = "anthropic"
key_from_env = "ANTHROPIC_API_KEY"

[checker]
kind = "openai"
base_url = "https://api.openai.com/v1"
model = "gpt-test-checker"
key_from_env = "COMPOSER_CHECKER_API_KEY"
"""


class SetupTests(unittest.TestCase):
    def test_answers_file_checker_table(self):
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY, COMPOSER_CHECKER_API_KEY=CHECKER_VALUE) as home:
            data = install(home, SEPARATE) / "data"
            cfg = S.load(data)
            self.assertEqual((cfg["checker"]["same"], cfg["checker"]["kind"], cfg["checker"]["model"]),
                             (False, "openai", "gpt-test-checker"))
            self.assertEqual(S.read_secrets(data), {"ANTHROPIC_API_KEY": FAKE_KEY, S.CHECKER_KEY: CHECKER_VALUE})
            self.assertEqual(S.checker_env(cfg), {"COMPOSER_CHECKER_PROVIDER": "openai",
                                                  "COMPOSER_CHECKER_MODEL": "gpt-test-checker",
                                                  "COMPOSER_CHECKER_OPENAI_BASE_URL": "https://api.openai.com/v1"})

    def test_a_checker_table_cannot_name_the_writers_key(self):
        # the writer's key must never go to the checker's endpoint (nor be stored as the checker's key)
        for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
            hostile = ('[provider]\nkind = "anthropic"\nkey_from_env = "ANTHROPIC_API_KEY"\n\n[checker]\n'
                       'kind = "openai"\nbase_url = "https://checker.example.net/v1"\nmodel = "m"\n'
                       f'key_from_env = "{name}"\n')
            with self.subTest(name=name), fake_home(ANTHROPIC_API_KEY=FAKE_KEY, OPENAI_API_KEY=FAKE_KEY) as home:
                sent = []
                with self.assertRaises(installer.SetupError) as cm:
                    install(home, hostile, test_call=lambda *a: sent.append(a) or (True, "ok"))
                self.assertIn("COMPOSER_CHECKER_API_KEY", str(cm.exception))
                self.assertFalse([a for a in sent if a[2] == "https://checker.example.net/v1"])
                self.assertFalse((home / ".lensmith-composer" / "data" / "secrets.env").exists())

    def test_no_checker_table_means_the_same_model(self):
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY) as home:
            data = install(home, '[provider]\nkind = "anthropic"\nkey_from_env = "ANTHROPIC_API_KEY"\n') / "data"
            cfg = S.load(data)
            self.assertTrue(cfg["checker"]["same"])
            self.assertEqual(S.checker_env(cfg), {})
            self.assertNotIn(S.CHECKER_KEY, S.read_secrets(data))

    def test_interactive_no_asks_provider_model_and_a_hidden_key(self):
        replies = {"choose 1-3": "1", "Check claims with the same model?": "n", "choose 1-2": "2",
                   "Checker endpoint base URL": "", "Checker model id": "gpt-test-checker", "Hacker News": "n",
                   "article parser": "n", "narration": "n", "daily brief": "n"}
        asked, secrets = [], []

        def read(prompt):
            asked.append(prompt)
            return next((v for k, v in replies.items() if k in prompt), "")

        def secret(prompt):
            secrets.append(prompt)
            typed = {"key: ": FAKE_KEY}.get(prompt, CHECKER_VALUE)  # the writer's key, then the checker's
            return typed
        printed = []
        with fake_home() as home:
            data = install(home, interactive=True, read=read, secret=secret, out=printed.append) / "data"
            cfg = S.load(data)
            stored = S.read_secrets(data)
        self.assertEqual(secrets, ["key: ", "checker key: "])
        self.assertTrue(any("Check claims with the same model? [Y/n]" in p for p in asked))
        self.assertEqual((cfg["checker"]["same"], cfg["checker"]["kind"], cfg["checker"]["base_url"]),
                         (False, "openai", "https://api.openai.com/v1"))
        self.assertEqual(stored, {"ANTHROPIC_API_KEY": FAKE_KEY, S.CHECKER_KEY: CHECKER_VALUE})
        self.assertFalse(any(CHECKER_VALUE in line or FAKE_KEY in line for line in printed))
        self.assertTrue(any("checker" in line and "key stored" in line for line in printed))

    def test_reconfigure_checker_alone(self):
        self.assertIn("checker", installer.SECTIONS)
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY, COMPOSER_CHECKER_API_KEY=CHECKER_VALUE) as home:
            target = install(home, '[provider]\nkind = "anthropic"\nkey_from_env = "ANTHROPIC_API_KEY"\n')
            path = home.parent / "checker.toml"
            path.write_text(SEPARATE.split("\n\n", 1)[1], encoding="utf-8")
            installer.run(home=target, data=None, answers_file=str(path), assume_yes=False,
                          reconfigure=["checker"], data_only=False, out=lambda *_: None, interactive=False)
            cfg = S.load(target / "data")
        self.assertFalse(cfg["checker"]["same"])
        self.assertEqual(cfg["provider"]["kind"], "anthropic")

    def test_the_checker_key_never_reaches_a_child_process(self):
        with mock.patch.dict(os.environ, {S.CHECKER_KEY: CHECKER_VALUE}):
            self.assertNotIn(S.CHECKER_KEY, H.private_env(Path(tempfile.gettempdir())))


class RoutingTests(unittest.TestCase):
    def test_each_provider_is_built_with_its_own_key(self):
        env = {"COMPOSER_PROVIDER": "anthropic", "COMPOSER_CHECKER_PROVIDER": "openai",
               "COMPOSER_CHECKER_MODEL": "gpt-test-checker",
               "COMPOSER_CHECKER_OPENAI_BASE_URL": "https://api.openai.com/v1"}
        writer_wire = ScriptedTransport([(200, {"content": [{"type": "text", "text": "written"}],
                                                "model": "claude-sonnet-5-5", "usage": {}})])
        checker_wire = ScriptedTransport([(200, {"choices": [{"message": {"content": "checked"}}],
                                                 "model": "gpt-test-checker", "usage": {}})])
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY, S.CHECKER_KEY: CHECKER_VALUE,
                                          "OPENAI_API_KEY": ""}), mock.patch.object(providers, "_KEY_FILE", None):
            writer = providers.from_env(env=env, transport=writer_wire)
            checker = providers.checker_from_env(env=env, transport=checker_wire)
            writer("write")
            checker("check")
        self.assertEqual(writer_wire.requests[0]["url"], providers.ANTHROPIC_URL)
        self.assertEqual(writer_wire.requests[0]["headers"]["x-api-key"], FAKE_KEY)
        self.assertEqual(checker_wire.requests[0]["url"], "https://api.openai.com/v1/chat/completions")
        self.assertEqual(checker_wire.requests[0]["headers"]["authorization"], f"Bearer {CHECKER_VALUE}")
        self.assertIsNone(providers.checker_from_env(env={}))

    @unittest.skipIf(ReplayJudge is None, "claim-seal is not installed (pip install -e .)")
    def test_the_writer_writes_and_the_checker_checks_every_claim(self):
        def no_judging(*_args, **_kwargs):
            raise AssertionError("the writer was asked to check a claim")
        writer = ScriptedModel([brief_for_fixtures()], no_judging)
        writer.name = "writer-model"
        judged = []

        class Checker:
            name = "checker-model"
            judge = ReplayJudge(JUDGE_ANSWERS)

            def __call__(self, prompt, timeout=None):
                judged.append(prompt)
                return self.judge(prompt, timeout=timeout)
        run = pipeline.compose(lens="local data handling", sources=[HARBOR, QUARRY], model=writer, count=3,
                               get=ScriptedGet(GET), checker=Checker())
        self.assertEqual(len(writer.prompts), 1)
        self.assertTrue(writer.prompts[0].startswith(WRITER_MARK))
        self.assertEqual(len(judged), 4)  # 3 insights and the connection
        self.assertFalse(any(p.startswith(WRITER_MARK) for p in judged))
        edition = run["edition"]
        self.assertEqual((edition["model"]["provider"], edition["model"]["calls"]), ("writer-model", 1))
        self.assertEqual((edition["checker"]["provider"], edition["checker"]["same_as_writer"],
                          edition["checker"]["calls"]), ("checker-model", False, 4))
        self.assertTrue(edition["check"]["seal_verified"])
        receipt = receipts.build_receipt(run, requested=["harbor", "quarry"])
        self.assertEqual(receipt["models"]["writer"]["provider"], "writer-model")
        self.assertEqual(receipt["models"]["checker"], {"provider": "checker-model", "models": ["replay-judge/v1"],
                                                        "same_as_writer": False})
        self.assertEqual((receipt["model_calls"]["calls"], receipt["checker_calls"]["calls"]), (1, 4))

    @unittest.skipIf(ReplayJudge is None, "claim-seal is not installed (pip install -e .)")
    def test_without_a_checker_the_writer_checks_and_the_receipt_says_so(self):
        model = ScriptedModel([brief_for_fixtures()], ReplayJudge(JUDGE_ANSWERS))
        run = pipeline.compose(lens="local data handling", sources=[HARBOR, QUARRY], model=model, count=3,
                               get=ScriptedGet(GET))
        self.assertEqual(run["edition"]["checker"]["same_as_writer"], True)
        receipt = receipts.build_receipt(run)
        self.assertTrue(receipt["models"]["checker"]["same_as_writer"])
        self.assertNotIn("checker_calls", receipt)
        self.assertEqual(receipt["model_calls"]["calls"], 5)

    def test_the_server_hands_the_checker_to_the_brief(self):
        seen = []

        class Ready:
            def __init__(self, name):
                self.name = name

            def ready(self):
                seen.append(f"{self.name} ready")

        def compose(**kw):
            seen.append((kw["model"].name, kw["checker"].name))
            return {"edition": {"lens": "x", "cards": [], "sources": []}}
        with tempfile.TemporaryDirectory() as d:
            app = server.App(Registry.load(None), lambda: Ready("writer"), make_checker=lambda: Ready("checker"),
                             compose=compose, data_root=Path(d) / "data")
            status, _ = app.handle_compose({}, json.dumps({"sources": ["google-ai"], "lens": "x"}).encode())
        self.assertEqual(status, 200)
        self.assertEqual(seen, ["writer ready", "checker ready", ("writer", "checker")])


class UpSettingsTests(unittest.TestCase):
    INHERITED = {"COMPOSER_CHECKER_PROVIDER": "openai", "COMPOSER_CHECKER_MODEL": "elsewhere",
                 "COMPOSER_CHECKER_OPENAI_BASE_URL": "https://checker.example.net/v1"}

    def test_the_same_model_setting_wins_over_inherited_checker_variables(self):
        cfg = json.loads(json.dumps(S.DEFAULTS))
        env = cli.up_env(cfg, {**self.INHERITED, "PATH": "/bin"})
        self.assertIsNone(providers.checker_from_env(env=env))
        self.assertEqual(env["PATH"], "/bin")
        # and the scheduler (the same wiring `composer up` uses) needs only the writer's key
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY, **self.INHERITED) as home, \
                mock.patch.object(providers, "_KEY_FILE", None):
            data = home / "data"
            S.generation_dir(data)
            cfg["schedule"] = dict(cfg["schedule"], enabled=True, time="07:00", timezone="UTC")
            submitted = []

            class Store:
                def submit(self, request):
                    submitted.append(request)
                    return {"job": "job-0000000000000001"}
            from datetime import datetime, timezone
            sched = cli.build_scheduler(data, cfg, cli.up_env(cfg, os.environ), store=Store(), log=lambda *_: None,
                                        clock=lambda: datetime(2026, 11, 2, 7, 5, tzinfo=timezone.utc))
            self.assertEqual(sched.tick(), "started")
        self.assertEqual(len(submitted), 1)

    def test_a_separate_checker_setting_is_used(self):
        cfg = json.loads(json.dumps(S.DEFAULTS))
        cfg["checker"] = dict(cfg["checker"], same=False, kind="anthropic", model="claude-opus-5-5")
        checker = providers.checker_from_env(env=cli.up_env(cfg, self.INHERITED))
        self.assertEqual((checker.name, checker.api_key_env), ("anthropic:claude-opus-5-5", S.CHECKER_KEY))


class DoctorTests(unittest.TestCase):
    def lines(self, target):
        out = []
        doctor.run(target, target / "data", out=out.append)
        return out

    def test_doctor_names_the_checker_and_never_its_key(self):
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY, COMPOSER_CHECKER_API_KEY=CHECKER_VALUE) as home:
            target = install(home, SEPARATE)
            os.environ.pop("COMPOSER_CHECKER_API_KEY")
            lines = self.lines(target)
            line = next(ln for ln in lines if ln.startswith(("PASS checker", "FAIL checker")))
            self.assertEqual(line, "PASS checker: a different model: openai, model gpt-test-checker; "
                                   "COMPOSER_CHECKER_API_KEY present: yes (key file)")
            self.assertFalse(any(CHECKER_VALUE in ln or FAKE_KEY in ln for ln in lines))
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY) as home:
            target = install(home, '[provider]\nkind = "anthropic"\nkey_from_env = "ANTHROPIC_API_KEY"\n')
            self.assertIn("PASS checker: same model as the writer (it checks its own brief)", self.lines(target))


class OnlineReflectionTests(unittest.TestCase):
    def test_doctor_online_never_prints_what_the_endpoint_echoes(self):
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY, COMPOSER_CHECKER_API_KEY=CHECKER_VALUE) as home:
            target = install(home, SEPARATE)

            def transport(url, headers, body, timeout):
                key = headers.get("x-api-key") or headers.get("authorization", "").removeprefix("Bearer ")
                if "chat/completions" in url:
                    return 200, json.dumps({"model": key, "choices": [{"message": {"content": key}}],
                                            "usage": {}}).encode()
                return 200, json.dumps({"model": key, "stop_reason": "end_turn",
                                        "content": [{"type": "text", "text": key}], "usage": {}}).encode()
            lines = []
            doctor.run(target, target / "data", out=lines.append, online=True, transport=transport,
                       get=lambda url, timeout: (_ for _ in ()).throw(OSError("offline")))
        online = [ln for ln in lines if "online: model" in ln or "online: checker" in ln]
        self.assertEqual(len(online), 2, lines)
        self.assertTrue(all(ln.startswith("PASS") for ln in online), online)
        self.assertFalse(any(FAKE_KEY in ln or CHECKER_VALUE in ln for ln in lines), lines)


if __name__ == "__main__":
    unittest.main()
