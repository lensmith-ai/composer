"""A request the page races against a timer must handle its own rejection.

When the compose screen hands over to the finished brief, it waits at most 700 ms for receipts.json and then
navigates away (location.replace). If the timer wins, the receipts request is cut off by that navigation and rejects;
with no rejection handler, WebKit reports "Unhandled Promise Rejection: TypeError: Load failed" (measured with a
request cut off by navigation: handled, nothing is reported; unhandled, that page error)."""
import re
import unittest

from helpers import ROOT

APP_JS = ROOT / "composer" / "web" / "app" / "app.js"


class LeaveWhileLoadingTests(unittest.TestCase):
    def test_every_raced_fetch_handles_its_rejection(self):
        js = APP_JS.read_text(encoding="utf-8")
        races = [m.start() for m in re.finditer(r"Promise\.race\(\[", js)]
        raced_fetches = 0
        for start in races:
            first = js[start:start + 400]
            m = re.match(r"Promise\.race\(\[\s*(jget\([^)]*\)\.then\(function\(\w*\)\{[^}]*\}(,function\(\)\{\})?\))",
                         first)
            if not m:
                continue
            raced_fetches += 1
            self.assertTrue(m.group(2), f"a raced fetch without a rejection handler: {m.group(1)}")
        self.assertGreaterEqual(raced_fetches, 2)


if __name__ == "__main__":
    unittest.main()
