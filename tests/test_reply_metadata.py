"""An endpoint's success reply must not carry the key into anything Composer records or serves. A reflecting (or
hostile) OpenAI-compatible or Anthropic endpoint answers HTTP 200 with `model` set to the very key the call was
made with; Counted copies the model into per_call and models, and build_receipt copies those into receipts.json,
which the app page reads. No real provider is contacted: the transport is scripted."""
import json
import os
import unittest
from unittest import mock

from composer import receipts
from composer.providers import Anthropic, Counted, OpenAICompatible, ProviderError

from helpers import ScriptedTransport

KEY = "FAKE-KEY-0308-REFLECTED"


def openai_reply(model=KEY, content="OK", usage=None):
    return 200, {"model": model, "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                 "usage": usage if usage is not None else {"prompt_tokens": 12, "completion_tokens": 3}}


def anthropic_reply(model=KEY, text="OK", usage=None):
    return 200, {"model": model, "stop_reason": "end_turn", "content": [{"type": "text", "text": text}],
                 "usage": usage if usage is not None else {"input_tokens": 12, "output_tokens": 3}}


def providers(answer_openai, answer_anthropic):
    return (("openai", OpenAICompatible(model="fixture-model", base_url="https://example.org/v1",
                                        transport=ScriptedTransport([answer_openai]))),
            ("anthropic", Anthropic(model="claude-sonnet-5-5", transport=ScriptedTransport([answer_anthropic]))))


class ReplyMetadataTests(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": KEY, "ANTHROPIC_API_KEY": KEY})
        env.start()
        self.addCleanup(env.stop)

    def test_a_reflected_key_in_model_never_reaches_the_served_receipt(self):
        for name, provider in providers(openai_reply(), anthropic_reply()):
            with self.subTest(provider=name):
                writer, checker = Counted(provider), None
                writer("hello")
                for role in ("writer", "checker"):
                    run = {"receipt": writer.receipt(), "edition": {}}
                    if role == "checker":  # the separate checker's receipt goes into the same file
                        checker_provider = providers(openai_reply(), anthropic_reply())[0 if name == "openai" else 1][1]
                        checker = Counted(checker_provider)
                        checker("check")
                        run["checker_receipt"] = checker.receipt()
                    served = json.dumps(receipts.build_receipt(run))
                    self.assertNotIn(KEY, served)
                self.assertEqual(writer.models, [provider.model])  # the configured id stands in
                self.assertEqual(writer.per_call[0]["model"], provider.model)
                self.assertEqual((writer.input_tokens, writer.output_tokens), (12, 3))

    def test_usage_that_is_not_a_count_is_unknown_not_recorded(self):
        bad = {"prompt_tokens": KEY, "completion_tokens": {"x": KEY}, "input_tokens": KEY, "output_tokens": [KEY]}
        for name, provider in providers(openai_reply(model="gpt-ok", usage=bad),
                                        anthropic_reply(model="claude-ok", usage=bad)):
            with self.subTest(provider=name):
                counted = Counted(provider)
                counted("hello")
                served = json.dumps(receipts.build_receipt({"receipt": counted.receipt(), "edition": {}}))
                self.assertNotIn(KEY, served)
                self.assertIsNone(counted.summary()["input_tokens"])  # unknown, as for an endpoint that sends none

    def test_a_reply_whose_text_holds_the_key_is_refused(self):
        for name, provider in providers(openai_reply(model="gpt-ok", content=f"your key is {KEY}"),
                                        anthropic_reply(model="claude-ok", text=f"your key is {KEY}")):
            with self.subTest(provider=name):
                counted = Counted(provider)
                with self.assertRaises(ProviderError) as ctx:
                    counted("hello")
                self.assertNotIn(KEY, str(ctx.exception))
                self.assertNotIn(KEY, json.dumps(receipts.build_receipt({"receipt": counted.receipt(),
                                                                          "edition": {}})))

    def test_an_honest_model_id_is_still_recorded(self):
        for name, provider in providers(openai_reply(model="gpt-5.6-terra-2026-10"),
                                        anthropic_reply(model="claude-sonnet-5-5-20261001")):
            with self.subTest(provider=name):
                counted = Counted(provider)
                counted("hello")
                self.assertEqual(counted.models, ["gpt-5.6-terra-2026-10" if name == "openai"
                                                  else "claude-sonnet-5-5-20261001"])


if __name__ == "__main__":
    unittest.main()
