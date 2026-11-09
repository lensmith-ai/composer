"""The pages Composer serves carry `style-src 'self'` (no 'unsafe-inline'). An inline style set from a string is what that
policy refuses in WebKit (Safari): `el.style.cssText = "..."` (the sand canvas, 2026-11-09), `el.setAttribute("style", ...)`,
and a `style="..."` attribute written into HTML by a script. Setting one property at a time (`el.style.left = "0"`,
`el.style.setProperty(...)`) is allowed everywhere. This reads every script the pages load and refuses the string forms.
The browser side of it, in WebKit and Chromium, is tests/browser/csp_flow.mjs."""
import re
import unittest
from pathlib import Path

from helpers import ROOT

SCRIPT_DIRS = ("composer/web", "docs/demo")
FORMS = [
    ("a cssText assignment", re.compile(r"\.cssText\s*\+?=(?!=)")),
    ("the style object assigned a string", re.compile(r"\.style\s*=(?!=)")),
    ("a <style> element made by a script", re.compile(r"""createElement\(\s*["']style["']""")),
    ("setAttribute of a style", re.compile(r"setAttribute\(\s*[\"']style[\"']")),
    ("a style attribute written into HTML", re.compile(r"""style=\\?["'][^"']""")),
]


def scripts():
    for d in SCRIPT_DIRS:
        for p in sorted((ROOT / d).rglob("*.js")):
            yield p


class InlineStyleTests(unittest.TestCase):
    def test_no_script_sets_an_inline_style_from_a_string(self):
        found = []
        for p in scripts():
            text = p.read_text(encoding="utf-8")
            for what, rx in FORMS:
                for m in rx.finditer(text):
                    line = text.count("\n", 0, m.start()) + 1
                    found.append(f"{p.relative_to(ROOT)}:{line}: {what}")
        # The one allowed: the entry animation's fallback, which only runs when its <link> stylesheet (every page carries
        # it, with the same id) is missing; under style-src 'self' a <style> it made would be refused, and is not relied on.
        found = [f for f in found if not (f.endswith("a <style> element made by a script") and "composer-entry-transition.js" in f)]
        self.assertEqual(found, [], "\n".join(found))

    def test_the_scan_has_teeth(self):
        for bad in ('cv.style.cssText+="a:b"', 'el.style = "a:b"', "document.createElement('style')", 'cv.style.cssText="position:absolute"', 'x.setAttribute("style","a:b")', "h='<i style=\"a:b\">'"):
            self.assertTrue(any(rx.search(bad) for _, rx in FORMS), bad)
        for good in ('cv.style.position="absolute"', 'el.style.setProperty("z-index","3")', 'r.style.cssText+"}"', "if(a.cssText==b)", "if(el.style==null)"):
            self.assertFalse(any(rx.search(good) for _, rx in FORMS), good)

    def test_the_served_pages_really_have_no_unsafe_inline(self):
        for rel in ("composer/app_static.py", "composer/window.py"):
            self.assertNotIn("unsafe-inline", (ROOT / rel).read_text(encoding="utf-8"), rel)


if __name__ == "__main__":
    unittest.main()
