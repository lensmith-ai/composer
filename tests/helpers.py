"""Shared test helpers: everything here is offline. No network, no key, no model."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from composer.fetch import Response
from composer.home import HomeError, check_trust
from composer.registry import parse_entry

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _trusted_temp() -> None:
    """Composer refuses to work in a folder that another account could change (home.check_trust), and the system's
    temporary folder (/tmp) is writable by every account. So the tests' temporary folders go under a private folder
    in your own home (or COMPOSER_TEST_TMP), for this process and the programs it starts."""
    if os.name != "posix":
        return
    # folders the tests make must not be group-writable either (some systems give every account umask 002)
    os.umask(0o022)
    try:
        check_trust(Path(tempfile.gettempdir()) / "probe")
        return
    except HomeError:
        pass
    # one level under your home, made private here: a parent made with a permissive umask (such as ~/.cache at 0775)
    # would itself be refused
    base = Path(os.environ.get("COMPOSER_TEST_TMP") or Path.home() / ".composer-tests")
    base.mkdir(mode=0o700, exist_ok=True)
    os.chmod(base, 0o700)
    check_trust(base / "probe")  # if your home itself is open to others, say so here rather than in every test
    tempfile.tempdir = str(base)
    os.environ["TMPDIR"] = str(base)


_trusted_temp()


def fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


class ScriptedGet:
    """A `get(url, timeout)` that answers from a table: url -> bytes, (status, bytes) or an exception."""

    def __init__(self, table: dict):
        self.table = table
        self.calls: list[str] = []

    def __call__(self, url: str, timeout: float) -> Response:
        self.calls.append(url)
        if url not in self.table:
            raise AssertionError(f"unexpected fetch of {url}")
        value = self.table[url]
        if isinstance(value, BaseException):
            raise value
        if isinstance(value, tuple):
            return Response(url, value[0], value[1])
        return Response(url, 200, value)


class ScriptedTransport:
    """A provider transport that records each request and answers from a list of (status, dict)."""

    def __init__(self, answers: list):
        self.answers = list(answers)
        self.requests: list[dict] = []

    def __call__(self, url, headers, body, timeout):
        self.requests.append({"url": url, "headers": dict(headers), "body": json.loads(body), "timeout": timeout})
        status, doc = self.answers.pop(0)
        return status, json.dumps(doc).encode("utf-8")


def source(**over):
    raw = {"id": "harbor", "label": "Harbor Lab notes", "kind": "rss-or-atom",
           "url": "https://example.org/harbor/feed.xml", "max_items": 5}
    raw.update(over)
    return parse_entry(raw)


WRITER_MARK = "You write a short, sourced brief"


class ScriptedModel:
    """Answers the writing prompt with `briefs` (in order) and claim-seal's prompts through `judge`."""

    def __init__(self, briefs: list, judge):
        self.briefs = list(briefs)
        self.judge = judge
        self.prompts: list[str] = []
        self.name = "scripted"

    def __call__(self, prompt: str, timeout=None):
        self.prompts.append(prompt)
        if prompt.startswith(WRITER_MARK):
            reply = self.briefs.pop(0)
            return reply if isinstance(reply, str) else json.dumps(reply)
        return self.judge(prompt, timeout=timeout)


def brief_for_fixtures(n_items: int = 3) -> dict:
    """A brief citing the two fixture feeds by their exact titles."""
    items = [
        {"insight": "Harbor Lab maps its tide sensors in public",
         "why_it_matters": "Anyone can now see readings from 40 sensors along the bay.",
         "detail": ["The map updates hourly."],
         "sources": [{"id": "harbor", "ref": "Harbor Lab opens a tide-sensor map"}]},
        {"insight": "Small on-device models keep text at home",
         "why_it_matters": "The phone model means no text leaves the device.",
         "detail": ["The studio calls it a smaller model."],
         "sources": [{"id": "quarry", "ref": "Quarry Street Studio ships a smaller model for phones"}]},
        {"insight": "Cheap mounts decide where sensors go",
         "why_it_matters": "Old piers give a stable mount and power.",
         "detail": ["Street lights supply the power."],
         "sources": [{"id": "harbor", "ref": "Why the sensors sit on old piers"},
                     {"id": "quarry", "ref": "A title that is in no feed"}]},
    ][:n_items]
    return {"items": items,
            "connection": {"headline": "Both sources keep data close to where it is made.",
                           "confidence": "plausible", "why": "Sensors and phones both process locally.",
                           "sources": [{"id": "harbor", "ref": "Harbor Lab opens a tide-sensor map"},
                                       {"id": "quarry", "ref": "Quarry Street Studio ships a smaller model for phones"}]},
            "transcript": FIXTURE_TRANSCRIPT}


FIXTURE_TRANSCRIPT = (
    "Here is your brief for today. Harbor Lab has opened a public map of its tide sensors, so anyone can now "
    "see readings from forty sensors along the bay, and the map updates every hour. Over at Quarry Street "
    "Studio, a smaller model now runs on phones, which means the text you type never has to leave the "
    "device.\n\nThe sensors sit on old piers, and that is no accident: the piers give a stable mount, and "
    "nearby lamp posts give them electricity. What links these stories is simple. Both teams keep "
    "data close to where it is made, on the pier and on the phone. That is the brief.")


JUDGE_ANSWERS = {
    "Harbor Lab maps its tide sensors in public": {
        "verdict": "supported", "why": "The feed says the map shows 40 sensors.", "relation": "says", "strength": 90,
        "citation_spans": [{"citation_index": 0, "span_quote": "readings from 40 sensors along the bay",
                            "span_relation": "says"}],
        "evidence_spans": [{"citation_index": 0, "support_span": "readings from 40 sensors along the bay"}]},
    "Small on-device models keep text at home": {
        "verdict": "partial", "why": "The feed says no text leaves the device, not that it stays at home.",
        "relation": "suggests", "strength": 60,
        "citation_spans": [{"citation_index": 0, "span_quote": "no text leaves the device", "span_relation": "says"}],
        "evidence_spans": [{"citation_index": 0, "support_span": "no text leaves the device"}]},
    "Cheap mounts decide where sensors go": {
        "verdict": "partial", "why": "Stable mounts and power are named; cost is not.", "relation": "suggests",
        "strength": 55,
        "citation_spans": [{"citation_index": 0, "span_quote": "Old piers give a stable mount and power",
                            "span_relation": "says"}],
        "evidence_spans": [{"citation_index": 0, "support_span": "Old piers give a stable mount and power"}]},
    "Both sources keep data close to where it is made.": {
        "verdict": "partial", "why": "Each source shows local handling in one way.", "relation": "implies",
        "strength": 50},
}
