import os
import unittest
from unittest import mock

from composer import providers
from composer.providers import Anthropic, Counted, OpenAICompatible, ProviderError, from_env

from helpers import ScriptedTransport

KEY = "test-key-not-real-0000"


def anthropic_ok(text="hello", model="claude-sonnet-5-5", stop="end_turn"):
    return 200, {"id": "msg_1", "type": "message", "model": model, "stop_reason": stop,
                 "content": [{"type": "thinking", "thinking": ""}, {"type": "text", "text": text}],
                 "usage": {"input_tokens": 120, "output_tokens": 30}}


class AnthropicTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": KEY}, clear=False)
        self.env.start()

    def tearDown(self):
        self.env.stop()

    def test_request_shape_and_reply(self):
        t = ScriptedTransport([anthropic_ok("brief text")])
        reply = Anthropic(transport=t)("write it", timeout=30)
        self.assertEqual(reply, "brief text")
        self.assertEqual(reply.model, "claude-sonnet-5-5")
        self.assertEqual(reply.usage, {"input_tokens": 120, "output_tokens": 30})
        req = t.requests[0]
        self.assertEqual(req["url"], "https://api.anthropic.com/v1/messages")
        self.assertEqual(req["headers"]["anthropic-version"], "2023-06-01")
        self.assertEqual(req["headers"]["x-api-key"], KEY)
        self.assertEqual(req["body"]["model"], "claude-sonnet-5-5")
        self.assertEqual(req["body"]["messages"], [{"role": "user", "content": "write it"}])
        self.assertEqual(req["body"]["max_tokens"], 16000)
        self.assertEqual(req["timeout"], 30)

    def test_refusal_fallback_is_on_for_models_that_take_it(self):
        t = ScriptedTransport([anthropic_ok(), anthropic_ok()])
        Anthropic(transport=t)("x")
        self.assertEqual(t.requests[0]["body"]["fallbacks"], "default")
        self.assertEqual(t.requests[0]["headers"]["anthropic-beta"], providers.FALLBACK_BETA)
        Anthropic(model="claude-haiku-5-5", transport=t)("x")
        self.assertNotIn("fallbacks", t.requests[1]["body"])
        self.assertNotIn("anthropic-beta", t.requests[1]["headers"])

    def test_key_is_never_kept_on_the_object(self):
        p = Anthropic(transport=ScriptedTransport([anthropic_ok()]))
        p("x")
        self.assertNotIn(KEY, repr(p))
        self.assertNotIn(KEY, repr(vars(p)))

    def test_missing_key(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": ""}):
            with self.assertRaisesRegex(ProviderError, "ANTHROPIC_API_KEY"):
                Anthropic(transport=ScriptedTransport([]))("x")

    def test_error_refusal_and_cutoff(self):
        err = (429, {"type": "error", "error": {"type": "rate_limit_error", "message": "slow down"}})
        with self.assertRaisesRegex(ProviderError, "429 rate_limit_error: slow down"):
            Anthropic(transport=ScriptedTransport([err]))("x")
        with self.assertRaisesRegex(ProviderError, "declined"):
            Anthropic(transport=ScriptedTransport([anthropic_ok("", stop="refusal")]))("x")
        with self.assertRaisesRegex(ProviderError, "ceiling"):
            Anthropic(transport=ScriptedTransport([anthropic_ok("partial", stop="max_tokens")]))("x")
        with self.assertRaisesRegex(ProviderError, "no text"):
            Anthropic(transport=ScriptedTransport([anthropic_ok("  ")]))("x")

    def test_endpoint_checks(self):
        with self.assertRaises(ProviderError):
            Anthropic(url="http://api.example.org/v1/messages", transport=ScriptedTransport([]))("x")
        with self.assertRaises(ProviderError):
            Anthropic(url="https://u:p@api.example.org/v1/messages", transport=ScriptedTransport([]))("x")
        t = ScriptedTransport([anthropic_ok()])
        Anthropic(url="http://127.0.0.1:9000/v1/messages", transport=t)("x")
        self.assertEqual(len(t.requests), 1)


class OpenAITests(unittest.TestCase):
    def test_chat_completions_shape(self):
        t = ScriptedTransport([(200, {"model": "some-model", "choices": [
            {"message": {"content": "hi"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 2}})])
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": KEY}):
            reply = OpenAICompatible(model="some-model", base_url="https://llm.example.org/v1/", transport=t)("q")
        self.assertEqual(reply, "hi")
        self.assertEqual(reply.usage, {"input_tokens": 5, "output_tokens": 2})
        self.assertEqual(t.requests[0]["url"], "https://llm.example.org/v1/chat/completions")
        self.assertEqual(t.requests[0]["headers"]["authorization"], f"Bearer {KEY}")

    def test_bad_answer(self):
        t = ScriptedTransport([(200, {"nope": 1})])
        with mock.patch.dict(os.environ, {"OPENAI_API_KEY": KEY}):
            with self.assertRaisesRegex(ProviderError, "not a chat-completions"):
                OpenAICompatible(model="m", base_url="https://llm.example.org/v1", transport=t)("q")


class FromEnvTests(unittest.TestCase):
    def test_default_is_anthropic_sonnet(self):
        p = from_env(env={})
        self.assertIsInstance(p, Anthropic)
        self.assertEqual(p.model, "claude-sonnet-5-5")

    def test_model_and_ceiling_from_env(self):
        p = from_env(env={"COMPOSER_MODEL": "claude-opus-5-5", "COMPOSER_MAX_TOKENS": "8000",
                          "COMPOSER_ANTHROPIC_FALLBACK": "off"})
        self.assertEqual((p.model, p.max_tokens, p.fallback), ("claude-opus-5-5", 8000, False))

    def test_openai_needs_base_url_and_model(self):
        with self.assertRaisesRegex(ProviderError, "BASE_URL"):
            from_env("openai", env={"COMPOSER_MODEL": "m"})
        with self.assertRaisesRegex(ProviderError, "COMPOSER_MODEL"):
            from_env("openai", env={"COMPOSER_OPENAI_BASE_URL": "https://x.example.org/v1"})
        p = from_env("openai", "m", env={"COMPOSER_OPENAI_BASE_URL": "https://x.example.org/v1"})
        self.assertIsInstance(p, OpenAICompatible)

    def test_unknown_provider_and_bad_ceiling(self):
        with self.assertRaises(ProviderError):
            from_env("other", env={})
        with self.assertRaises(ProviderError):
            from_env(env={"COMPOSER_MAX_TOKENS": "lots"})


class CountedTests(unittest.TestCase):
    def test_numbers_are_unique_when_calls_overlap(self):
        import threading

        class Slow:
            def __call__(self, prompt, timeout=None):
                import time
                time.sleep(0.02)
                return providers.Reply("ok", model="m", usage={"input_tokens": 1, "output_tokens": 1})
        c = Counted(Slow())
        threads = [threading.Thread(target=c, args=("p",)) for _ in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual([x["call"] for x in c.summary()["per_call"]], [1, 2, 3, 4, 5, 6])
        self.assertEqual(c.summary()["input_tokens"], 6)

    def test_counts_calls_tokens_and_failures(self):
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": KEY}):
            t = ScriptedTransport([anthropic_ok(), anthropic_ok(), (500, {"error": {"type": "api_error"}})])
            c = Counted(Anthropic(transport=t))
            c("a")
            c("b")
            with self.assertRaises(ProviderError):
                c("c")
        s = c.summary()
        self.assertEqual((s["calls"], s["failed_calls"], s["input_tokens"], s["output_tokens"]), (3, 1, 240, 60))
        self.assertEqual(s["models"], ["claude-sonnet-5-5"])
        self.assertEqual([(c["call"], c["ok"], c.get("input_tokens")) for c in s["per_call"]],
                         [(1, True, 120), (2, True, 120), (3, False, None)])
        self.assertEqual(s["per_call"][2]["error"], "ProviderError")


if __name__ == "__main__":
    unittest.main()
