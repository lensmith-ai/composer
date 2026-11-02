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



LONG_KEY = "FAKE-KEY-0309-0123456789-abcdefghijk"
FRAGMENTS = {"prefix": LONG_KEY[:24], "suffix": LONG_KEY[-12:], "inner": LONG_KEY[7:19], "whole": LONG_KEY}


class KeyFragmentTests(unittest.TestCase):
    """A reflecting endpoint that echoes only part of the key: any run of 12 or more of its characters (start, end
    or inside) counts as the key, for the model id and for the text, writer and checker."""

    def setUp(self):
        env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": LONG_KEY, "ANTHROPIC_API_KEY": LONG_KEY,
                                           "COMPOSER_CHECKER_API_KEY": LONG_KEY})
        env.start()
        self.addCleanup(env.stop)

    def test_a_fragment_as_the_model_never_reaches_the_receipt(self):
        for part, fragment in FRAGMENTS.items():
            for name, provider in providers(openai_reply(model=fragment), anthropic_reply(model=fragment)):
                with self.subTest(fragment=part, provider=name):
                    writer = Counted(provider)
                    writer("hello")
                    checker = Counted(providers(openai_reply(model=fragment),
                                                anthropic_reply(model=fragment))[0 if name == "openai" else 1][1])
                    checker("check")
                    served = json.dumps(receipts.build_receipt({"receipt": writer.receipt(), "edition": {},
                                                                "checker_receipt": checker.receipt()}))
                    self.assertNotIn(fragment, served)
                    self.assertEqual(writer.models, [provider.model])

    def test_a_fragment_in_the_text_is_refused(self):
        for part, fragment in FRAGMENTS.items():
            for name, provider in providers(openai_reply(model="gpt-ok", content=f"here: {fragment}"),
                                            anthropic_reply(model="claude-ok", text=f"here: {fragment}")):
                with self.subTest(fragment=part, provider=name):
                    counted = Counted(provider)
                    with self.assertRaises(ProviderError) as ctx:
                        counted("hello")
                    self.assertNotIn(fragment, str(ctx.exception))

    def test_short_overlaps_and_the_public_prefix_are_not_a_key(self):
        from composer.providers import holds_key
        self.assertFalse(holds_key(LONG_KEY[:11], LONG_KEY))          # 11 characters: below the policy
        self.assertFalse(holds_key("claude-sonnet-5-5", LONG_KEY))
        anthropic_style = "sk-ant-api03-" + "Qx7" * 30
        self.assertFalse(holds_key("keys look like sk-ant-api03-", anthropic_style))  # the published prefix alone
        self.assertTrue(holds_key("sk-ant-api03-Q", anthropic_style))  # one character past it


PROJ_KEY = "sk" + "-proj-" + "FAKEab" + "123456789012" + "cdEFghIJklMN"  # built in parts: not a real key's shape


class PrefixAndCountTests(unittest.TestCase):
    """Only the exact published prefixes are exempt, and a token count whose digits hold a piece of the key is unknown."""

    def env(self, key):
        env = mock.patch.dict(os.environ, {"OPENAI_API_KEY": key, "ANTHROPIC_API_KEY": key,
                                           "COMPOSER_CHECKER_API_KEY": key})
        env.start()
        self.addCleanup(env.stop)

    def test_a_custom_key_shaped_like_a_published_one_is_protected_from_its_start(self):
        key = "sk" + "-ant-" + "abcdefghijklmnop" + "-0123456789XYZ"  # not a published prefix: the middle is private
        self.env(key)
        for name, provider in providers(openai_reply(model="abcdefghijklmnop"),
                                        anthropic_reply(model="abcdefghijklmnop")):
            with self.subTest(provider=name):
                counted = Counted(provider)
                counted("hello")
                self.assertNotIn("abcdefghijklmnop", json.dumps(receipts.build_receipt(
                    {"receipt": counted.receipt(), "edition": {}})))
        for name, provider in providers(openai_reply(model="gpt-ok", content="see abcdefghijklmnop"),
                                        anthropic_reply(model="claude-ok", text="see abcdefghijklmnop")):
            with self.subTest(provider=name, field="text"):
                with self.assertRaises(ProviderError):
                    Counted(provider)("hello")

    def test_a_count_made_of_the_key_digits_is_not_recorded(self):
        key = PROJ_KEY
        self.env(key)
        usage_openai = {"prompt_tokens": 123456789012, "completion_tokens": 3}
        usage_anthropic = {"input_tokens": 123456789012, "output_tokens": 3}
        for name, provider in providers(openai_reply(model="gpt-ok", usage=usage_openai),
                                        anthropic_reply(model="claude-ok", usage=usage_anthropic)):
            with self.subTest(provider=name):
                writer = Counted(provider)
                writer("hello")
                checker = Counted(providers(openai_reply(model="gpt-ok", usage=usage_openai),
                                            anthropic_reply(model="claude-ok", usage=usage_anthropic))[
                    0 if name == "openai" else 1][1])
                checker("check")
                served = json.dumps(receipts.build_receipt({"receipt": writer.receipt(), "edition": {},
                                                            "checker_receipt": checker.receipt()}))
                self.assertNotIn("123456789012", served)
                self.assertIsNone(writer.summary()["input_tokens"])  # unknown, as for a count that was not sent

    def test_ordinary_counts_are_kept(self):
        self.env(PROJ_KEY)
        counted = Counted(providers(openai_reply(model="gpt-ok"), anthropic_reply(model="claude-ok"))[0][1])
        counted("hello")
        self.assertEqual((counted.input_tokens, counted.output_tokens), (12, 3))


if __name__ == "__main__":
    unittest.main()
