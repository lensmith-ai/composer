"""Setup's model list (from composer/data/models.json) and its one tiny test call per key.

Offline: the test call goes through the providers' fake transport, or a scripted stand-in for the whole call."""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from install_helpers import FAKE_KEY, fake_home

from composer import cli, installer, providers, settings as S

from helpers import ScriptedTransport


def asker(replies, *, secret=FAKE_KEY, answers=None, interactive=True):
    out, asked = [], []

    def read(prompt):
        asked.append(prompt)
        for key in list(replies):
            if key in prompt:
                value = replies[key]
                if isinstance(value, list):  # successive answers to the same prompt
                    return value.pop(0) if value else ""
                return value
        return ""
    q = installer.Asker(answers or {}, interactive, out=out.append, read=read, secret=lambda _p: secret)
    return q, out, asked


def plan(test_call=None):
    return {"data": Path(tempfile.gettempdir()) / "composer-test-data", "data_only": False, "test_call": test_call}


class ModelListTests(unittest.TestCase):
    def test_the_list_comes_from_the_data_file_and_enter_takes_the_default(self):
        q, out, _ = asker({"choose 1-3": "1"})
        p = plan()
        installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "claude-sonnet-5-5")
        shown = "\n".join(out)
        for line in ("  1) claude-sonnet-5-5 (default)", "  2) claude-opus-5-5", "  3) claude-haiku-5-5",
                     "  4) type another model id"):
            self.assertIn(line, shown)
        doc = json.loads(installer.MODELS_FILE.read_text())
        self.assertEqual(doc["anthropic"]["models"], ["claude-sonnet-5-5", "claude-opus-5-5", "claude-haiku-5-5"])

    def test_a_listed_id_or_a_typed_one(self):
        q, _, _ = asker({"choose 1-3": "1", "choose 1-4": "2"})
        p = plan()
        installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "claude-opus-5-5")
        q, _, asked = asker({"choose 1-3": "1", "choose 1-4": "4", "Model id": "claude-some-new-model"})
        p = plan()
        installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "claude-some-new-model")
        self.assertIn("Model id [claude-sonnet-5-5]: ", asked)

    def test_editing_the_data_file_changes_the_list(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "models.json"
            path.write_text(json.dumps({"anthropic": {"default": "model-b", "models": ["model-a", "model-b"]}}))
            with mock.patch.object(installer, "MODELS_FILE", path):
                q, out, _ = asker({"choose 1-3 [1]": "1"})  # the service; Enter at the list ("choose 1-3 [2]")
                p = plan()
                installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "model-b")
        self.assertIn("  2) model-b (default)", out)
        self.assertIn("  3) type another model id", out)

    def test_an_openai_compatible_endpoint_lists_nothing_and_says_to_type_the_id(self):
        q, out, _ = asker({"choose 1-3": "2", "Model id": "anthropic/claude-opus-5-5"})
        p = plan()
        installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "anthropic/claude-opus-5-5")
        self.assertTrue(any("Type the model id your endpoint uses" in line for line in out))
        self.assertFalse(any(") claude-" in line for line in out))

    def test_an_answers_file_takes_any_model_id(self):
        q, _, asked = asker({}, answers={"provider": {"kind": "anthropic", "model": "claude-not-in-the-list",
                                                      "key": "env"}}, interactive=False)
        p = plan()
        installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "claude-not-in-the-list")
        self.assertEqual(asked, [])

    def test_the_checker_gets_the_same_list(self):
        q, out, _ = asker({"same model": "n", "choose 1-2": "1", "choose 1-4": "3"}, secret="checker-test-value")
        p = plan()
        installer.ask_checker(q, p, "anthropic")
        self.assertEqual((p["checker"]["kind"], p["checker"]["model"]), ("anthropic", "claude-haiku-5-5"))
        self.assertIn("Which checker model?", out)


def reply_ok():
    return (200, {"content": [{"type": "text", "text": "OK"}], "model": "claude-sonnet-5-5", "stop_reason": "end_turn",
                  "usage": {"input_tokens": 12, "output_tokens": 2}})


class TestCallTests(unittest.TestCase):
    def call(self, answer, kind="anthropic"):
        wire = ScriptedTransport([answer]) if not callable(answer) else answer
        return providers.test_call(kind, "claude-sonnet-5-5" if kind == "anthropic" else "m",
                                   "https://api.example.org/v1", FAKE_KEY, transport=wire), wire

    def test_a_working_key_and_model(self):
        (ok, said), wire = self.call(reply_ok())
        self.assertTrue(ok)
        self.assertIn("work", said)
        sent = wire.requests[0]
        self.assertEqual(sent["body"]["max_tokens"], providers.TEST_CALL_TOKENS)
        self.assertEqual(sent["timeout"], providers.TEST_CALL_TIMEOUT_S)
        self.assertNotIn("fallbacks", sent["body"])

    def test_a_successful_reply_cannot_put_the_key_in_the_sentence(self):
        echo = (200, {"content": [{"type": "text", "text": "OK"}], "model": f"model {FAKE_KEY}",
                      "stop_reason": "end_turn", "usage": {}})
        (ok, said), _ = self.call(echo)
        self.assertTrue(ok)
        self.assertNotIn(FAKE_KEY, said)
        self.assertEqual(said, "the key and the model id work (claude-sonnet-5-5 answered)")
        # and setup prints nothing that holds the key
        q, out, _ = asker({"choose 1-3": "1"})
        installer.ask_provider(q, plan(lambda kind, model, base, key: providers.test_call(
            kind, model, base, key, transport=ScriptedTransport([echo]))))
        self.assertFalse(any(FAKE_KEY in line for line in out), out)

    def test_each_failure_says_which(self):
        cases = [
            ((401, {"error": {"type": "authentication_error", "message": f"invalid x-api-key {FAKE_KEY}"}}),
             "the key was refused"),
            ((404, {"error": {"type": "not_found_error", "message": "model: claude-sonnet-5-5"}}),
             "the model id was not found"),
            ((400, {"error": {"type": "invalid_request_error", "message": "model not found: m"}}),
             "the model id was not found"),
        ]
        for answer, words in cases:
            with self.subTest(words=words):
                (ok, said), _ = self.call(answer)
                self.assertFalse(ok)
                self.assertTrue(said.startswith(words), said)
                self.assertNotIn(FAKE_KEY, said)

        def unreachable(*_args):
            raise providers.ProviderError("could not reach the endpoint: URLError")
        (ok, said), _ = self.call(unreachable, kind="openai")
        self.assertEqual((ok, said.split(" (")[0]), (False, "the endpoint could not be reached"))

    def test_setup_says_so_and_offers_to_enter_them_again(self):
        results = [(False, "the key was refused (HTTP 401 authentication_error)"), (True, "the key and the model id work")]
        calls = []

        def test_call(kind, model, base_url, key):
            calls.append((kind, model, base_url, key))
            return results.pop(0)
        q, out, asked = asker({"choose 1-3": "1", "choose 1-4": ["", "2"], "Enter the model and key again?": "y"})
        p = plan(test_call)
        installer.ask_provider(q, p)
        self.assertEqual([c[1] for c in calls], ["claude-sonnet-5-5", "claude-opus-5-5"])
        self.assertEqual(p["provider"]["model"], "claude-opus-5-5")
        self.assertIn("  test call (writer): the key was refused (HTTP 401 authentication_error)", out)
        self.assertTrue(any("Enter the model and key again?" in a for a in asked))
        self.assertFalse(any(FAKE_KEY in line for line in out))

    def test_keep_going_after_a_failure(self):
        q, out, _ = asker({"choose 1-3": "1", "Enter the model and key again?": "n"})
        p = plan(lambda *a: (False, "the endpoint could not be reached (could not reach the endpoint: URLError)"))
        installer.ask_provider(q, p)
        self.assertEqual(p["provider"]["model"], "claude-sonnet-5-5")
        q, out, _ = asker({}, answers={"provider": {"kind": "anthropic", "key_from_env": "ANTHROPIC_API_KEY"}},
                          interactive=False)
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": FAKE_KEY}):
            installer.ask_provider(q, plan(lambda *a: (False, "the model id was not found (HTTP 404)")))
        self.assertIn("  keeping these settings; composing will fail until this is fixed", out)

    def test_no_key_no_call(self):
        q, _, _ = asker({"choose 1-3": "1"}, secret="")
        installer.ask_provider(q, plan(lambda *a: self.fail("a call was made with no key")))


class SkipTests(unittest.TestCase):
    def run_cli(self, argv, env):
        seen = {}
        with mock.patch.object(installer, "run", side_effect=lambda **kw: seen.update(kw) or 0), \
                mock.patch.dict(os.environ, env):
            cli.main(argv)
        return seen["test_call"]

    def test_the_flag_and_test_mode_skip_it_and_otherwise_it_runs(self):
        with fake_home() as home:
            argv = ["setup", "--yes", "--home", str(home / "x")]
            self.assertIsNone(self.run_cli(argv + ["--no-test-call"], {"COMPOSER_NO_TEST_CALL": ""}))
            self.assertIsNone(self.run_cli(argv, {"COMPOSER_NO_TEST_CALL": "1"}))
            self.assertIs(self.run_cli(argv, {"COMPOSER_NO_TEST_CALL": ""}), providers.test_call)

    def test_setup_with_a_test_call_given_to_the_library_runs_it_once_per_key(self):
        made = []
        with fake_home(ANTHROPIC_API_KEY=FAKE_KEY) as home:
            path = home.parent / "answers.toml"
            path.write_text('[provider]\nkind = "anthropic"\nkey_from_env = "ANTHROPIC_API_KEY"\n')
            installer.run(home=home / ".lensmith-composer", data=None, answers_file=str(path), assume_yes=False,
                          reconfigure=[], data_only=False, out=lambda *_: None, interactive=False,
                          test_call=lambda *a: made.append(a[:3]) or (True, "ok"))
            cfg = S.load(home / ".lensmith-composer" / "data")
        self.assertEqual(made, [("anthropic", "claude-sonnet-5-5", "")])
        self.assertTrue(cfg["checker"]["same"])


if __name__ == "__main__":
    unittest.main()
