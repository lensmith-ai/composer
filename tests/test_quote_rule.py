"""The quote rule (composer.quotes and the pipeline's write step), from an invented fixture feed.

At most 25 words per quoted run copied from an article, at most 2 quotes from one article per brief, never the
article's opening sentence. A brief that breaks it is sent back to the writer once; if that does not fix it, the
parts that break it are dropped, and the edition and receipt say what was dropped and why (no article text)."""
import json
import unittest

from composer import adapters, pipeline, prompt as P, quotes as Q, receipts

from helpers import ScriptedGet, fixture, source

LANTERN = source(id="lantern", label="Lantern Works journal", url="https://example.org/lantern/feed.xml")
LAMP = "Lantern Works releases a solar lamp that charges in cloudy weather"
COATING = "Why the coating works"
TRANSCRIPT = ("Here is your brief. Lantern Works has a new solar lamp that still charges when the sky is grey. "
              "Its trick is a coating that catches light coming from all sides, not just from the sun overhead. "
              "In trials up north it gave several hours of light after dull days, and two school towns want it "
              "on their walking routes before winter arrives. The coating is cheap and can go onto older lamps "
              "too. That is the brief for today.")


def fetched():
    get = ScriptedGet({LANTERN.url: fixture("feed-quotes.xml")})
    return {LANTERN.id: adapters.fetch(LANTERN, get)}


def brief(*items, transcript=TRANSCRIPT, connection=None):
    out = {"items": [dict({"insight": "A lamp", "why_it_matters": "It matters.", "detail": [],
                           "sources": [{"id": "lantern", "ref": LAMP}]}, **it) for it in items],
           "transcript": transcript}
    if connection:
        out["connection"] = connection
    return out


def words(n_from: str, start_word: int, n: int) -> str:
    return " ".join(n_from.split()[start_word:start_word + n])


def article_text(i: int = 0) -> str:
    items, _ = fetched()["lantern"]
    return items[i]["description"]


class FindTests(unittest.TestCase):
    def check(self, b):
        return Q.check(b, [LANTERN], fetched())

    def rules(self, b):
        return sorted({x["rule"] for x in self.check(b)["breaches"]})

    def test_the_fixture_is_what_the_tests_assume(self):
        text = article_text(0)
        self.assertTrue(text.startswith("Lantern Works released a solar lamp on Tuesday"))
        self.assertEqual(Q.articles([LANTERN], fetched())[0]["opening_words"], 15)

    def test_own_words_are_not_quotes(self):
        b = brief({"why_it_matters": "A coating that catches light from all sides lets the lamp charge on grey days."})
        self.assertEqual(self.check(b), {"runs": 0, "passages": 0, "breaches": []})

    def test_a_quote_of_25_words_passes_and_26_does_not(self):
        middle = words(article_text(0), 15, 25)  # starts right after the opening sentence
        ok = brief({"detail": [f'The company says "{middle}".']})
        self.assertEqual(self.rules(ok), [])
        self.assertEqual(self.check(ok)["runs"], 1)
        long = words(article_text(0), 15, 26)
        self.assertEqual(self.rules(brief({"detail": [f'The company says "{long}".']})), ["over_25_words"])

    def test_copying_without_quotation_marks_is_quoting(self):
        long = words(article_text(0), 15, 26)
        self.assertEqual(self.rules(brief({"why_it_matters": long})), ["over_25_words"])
        twelve = words(article_text(0), 15, 12)
        self.assertEqual(self.check(brief({"why_it_matters": f"In short, {twelve}, it seems."}))["runs"], 0)
        thirteen = words(article_text(0), 15, 13)
        self.assertEqual(self.check(brief({"why_it_matters": f"In short, {thirteen}, it seems."}))["runs"], 1)

    def test_never_the_opening_sentence(self):
        lede = "Lantern Works released a solar lamp on Tuesday that keeps charging under thick cloud cover."
        self.assertEqual(self.rules(brief({"detail": [f'"{lede}"']})), ["opening_sentence"])
        self.assertEqual(self.rules(brief({"why_it_matters": lede})), ["opening_sentence"])
        # three words of the opening sentence in quotation marks are a term, not the sentence
        self.assertEqual(self.rules(brief({"detail": ['It keeps charging under "thick cloud cover" too.']})), [])
        # most of a short opening sentence, reworded around, is not the sentence; all of it is
        short = "Scattered light reaches the panel from many angles at once."
        self.assertEqual(self.rules(brief({"detail": ["Scattered light reaches the panel from many angles, they say."]})),
                         [])
        self.assertEqual(self.rules(brief({"detail": [f'"{short}"']})), ["opening_sentence"])

    def test_at_most_two_quotes_from_one_article(self):
        text = article_text(0)
        q1, q2, q3 = words(text, 15, 10), words(text, 40, 10), words(text, 60, 10)
        two = brief({"detail": [f'"{q1}"', f'"{q2}"']})
        self.assertEqual(self.rules(two), [])
        three = brief({"detail": [f'"{q1}"', f'"{q2}"']}, {"detail": [f'"{q3}"']})
        found = self.check(three)
        self.assertEqual(sorted({x["rule"] for x in found["breaches"]}), ["over_2_per_article"])
        self.assertEqual({x["where"] for x in found["breaches"]}, {("item", 1, "detail[0]")})  # the third, not the first

    def test_the_same_words_quoted_again_are_one_quote(self):
        text = article_text(0)
        q1, q2 = words(text, 15, 10), words(text, 40, 10)
        b = brief({"detail": [f'"{q1}"', f'"{q2}"']}, transcript=TRANSCRIPT + f' As they put it, "{q1}".')
        found = self.check(b)
        self.assertEqual(found["breaches"], [])
        self.assertEqual((found["runs"], found["passages"]), (3, 2))

    def test_quotes_from_two_articles_are_counted_apart(self):
        a, b_ = article_text(0), article_text(1)
        b = brief({"detail": [f'"{words(a, 15, 10)}"', f'"{words(a, 40, 10)}"', f'"{words(b_, 10, 10)}"']})
        self.assertEqual(self.rules(b), [])

    def test_naming_the_title_is_a_citation_not_a_quote(self):
        b = brief({"insight": LAMP, "detail": [f'The post is called "{LAMP}".']})
        self.assertEqual(self.check(b)["runs"], 0)

    def test_the_connection_and_transcript_are_checked_too(self):
        long = words(article_text(0), 15, 30)
        conn = {"headline": long, "confidence": "plausible", "why": "x", "sources": [{"id": "lantern", "ref": LAMP}]}
        found = self.check(brief({}, connection=conn, transcript=TRANSCRIPT + " " + long))
        self.assertEqual({x["where"] for x in found["breaches"]}, {("connection", "headline"), ("transcript",)})

    def test_the_result_holds_no_article_text(self):
        long = words(article_text(0), 15, 30)
        dumped = json.dumps(self.check(brief({"why_it_matters": long})))
        self.assertNotIn(words(article_text(0), 15, 4), dumped)


def writer_brief(n=3, **over):
    """A usable brief with n items, all in its own words; `over` maps item index -> field changes."""
    items = [{"insight": f"Lamp point {i + 1}", "why_it_matters": f"Point {i + 1} in our own words.",
              "detail": ["A short note of our own."], "sources": [{"id": "lantern", "ref": LAMP}]} for i in range(n)]
    for i, change in over.items():
        items[int(i)].update(change)
    return {"items": items, "transcript": TRANSCRIPT}


class WriterModel:
    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def __call__(self, prompt, timeout=None):
        self.prompts.append(prompt)
        a = self.answers.pop(0)
        return a if isinstance(a, str) else json.dumps(a)


class WriteStepTests(unittest.TestCase):
    LONG = None

    def setUp(self):
        self.long = words(article_text(0), 15, 30)
        self.events = []

    def write(self, answers):
        model = WriterModel(answers)
        b, info = pipeline.write("cheap light", [LANTERN], fetched(), model, 3,
                                 log=lambda kind, text: self.events.append((kind, text)))
        return b, info, model

    def test_the_prompt_asks_for_own_words_and_the_limits(self):
        text, _ = P.build("x", [LANTERN], fetched(), 3)
        for words_ in ("Write in your own words.", "at most 25 words in one quote",
                       "at most 2 quotes from one article", "never the article's opening sentence",
                       "Copying words without\n  quotation marks counts as quoting"):
            self.assertIn(words_, text)

    def test_a_clean_brief_makes_one_call_and_says_so(self):
        b, info, model = self.write([writer_brief()])
        self.assertEqual(len(model.prompts), 1)
        self.assertEqual(info["quotes"]["breaches"], 0)
        self.assertFalse(info["quotes"]["repair_call"])
        self.assertEqual(len(b["items"]), 3)

    def test_a_breach_is_repaired_by_one_more_call(self):
        bad = writer_brief(**{"1": {"why_it_matters": self.long}})
        b, info, model = self.write([bad, writer_brief()])
        self.assertEqual(len(model.prompts), 2)
        self.assertIn("IT BREAKS THE QUOTE RULE: item 2 (why_it_matters) copies 30 words in a row", model.prompts[1])
        self.assertIn(f'from "{LAMP}"', model.prompts[1])
        self.assertEqual((info["quotes"]["repaired"], info["quotes"]["breaches"]), (True, 1))
        self.assertNotIn("dropped", info["quotes"])
        self.assertEqual(len(b["items"]), 3)
        self.assertIn("quote.repaired", [k for k, _ in self.events])

    def test_if_the_repair_still_breaks_it_the_insight_is_dropped_with_a_note(self):
        bad = writer_brief(**{"1": {"why_it_matters": self.long}})
        b, info, model = self.write([bad, bad])
        self.assertEqual(len(model.prompts), 2)
        self.assertEqual([it["insight"] for it in b["items"]], ["Lamp point 1", "Lamp point 3"])
        note = info["quotes"]
        self.assertFalse(note["repaired"])
        self.assertEqual(note["breaches_after_repair"], 1)
        self.assertEqual(note["dropped"], {"dropped_items": [2], "dropped_connection": False,
                                           "dropped_transcript": False, "rules": {"item 2": ["over_25_words"]}})
        self.assertIn(("quote.dropped", "dropped 1 insight that copied too much of an article"), self.events)

    def test_an_unusable_repair_answer_also_drops(self):
        bad = writer_brief(**{"0": {"detail": [f'"{self.long}"']}})
        b, info, _ = self.write([bad, "not json at all"])
        self.assertEqual(len(b["items"]), 2)
        self.assertIn("no JSON object", info["quotes"]["repair_unusable"])

    def test_a_transcript_that_copies_is_dropped_and_the_insights_stay(self):
        bad = writer_brief()
        bad["transcript"] = TRANSCRIPT + " " + self.long
        b, info, _ = self.write([bad, bad])
        self.assertNotIn("transcript", b)
        self.assertEqual(len(b["items"]), 3)
        self.assertTrue(info["quotes"]["dropped"]["dropped_transcript"])

    def test_when_every_insight_breaks_it_nothing_is_kept(self):
        bad = writer_brief(**{str(i): {"why_it_matters": self.long} for i in range(3)})
        with self.assertRaisesRegex(pipeline.ComposeError, "every insight copied too much"):
            self.write([bad, bad])


class ReceiptTests(unittest.TestCase):
    def test_the_note_reaches_the_receipt_without_text(self):
        note = {"rule": dict(Q.RULES), "runs": 2, "passages": 1, "breaches": 1, "repaired": False,
                "repair_call": True, "dropped": {"dropped_items": [2], "dropped_connection": False,
                                                 "dropped_transcript": False, "rules": {"item 2": ["over_25_words"]}}}
        out = receipts.build_receipt({"edition": {"quotes": note}, "fetched": fetched()})
        self.assertEqual(out["quotes"], note)
        self.assertNotIn("thick cloud", json.dumps(out))


if __name__ == "__main__":
    unittest.main()
