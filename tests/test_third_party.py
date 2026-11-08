"""THIRD-PARTY.md names every package Composer pins: each `name==version` in the lock files (and the pins in
pyproject.toml) must have a row in its section of THIRD-PARTY.md, with that version and a licence. A package added
to a lock file without a row here fails this test."""
import re
import unittest

from helpers import ROOT

DOC = ROOT / "THIRD-PARTY.md"

# Each pinned file, and the THIRD-PARTY.md section whose table must list its packages.
LOCKS = {
    "composer/narration/requirements.lock": "## Narration (optional)",
    "composer/extraction-requirements.lock": "## Article parser (optional)",
    "scripts/release/release-tools.txt": "## Release and CI tools (not part of Composer)",
}
PACKAGE_SECTION = "## The package: what `pip install .` installs (required)"


def normal(name: str) -> str:
    """PEP 503 name: lower case, runs of '-', '_' and '.' as one '-'."""
    return re.sub(r"[-_.]+", "-", name).lower()


def lock_pins(text: str) -> list[tuple[str, str]]:
    """Every `name==version` requirement line (markers ignored; a name may appear once per Python version)."""
    pins = []
    for line in text.splitlines():
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;\\]+)", line)
        if m:
            pins.append((normal(m.group(1)), m.group(2)))
    return pins


def pyproject_pins(text: str) -> list[tuple[str, str]]:
    """setuptools==X from build-system.requires and claim-seal's version from its pinned archive."""
    pins = [(normal(n), v) for n, v in re.findall(r'"([A-Za-z0-9._-]+)==([^"]+)"', text)]
    for name in re.findall(r'"([A-Za-z0-9._-]+) @ https://', text):
        pins.append((normal(name), None))
    return pins


def section_rows(doc: str, heading: str) -> dict[str, list[list[str]]]:
    """The table rows under one heading (up to the next '## '), keyed by the normalised package name in the first
    cell (a link's text, or the cell's first word)."""
    start = doc.index(heading)
    end = doc.find("\n## ", start + len(heading))
    rows: dict[str, list[list[str]]] = {}
    for line in doc[start:end if end != -1 else None].splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        first = cells[0]
        link = re.match(r"\[([^\]]+)\]", first)
        name = link.group(1) if link else first.split(" ")[0]
        rows.setdefault(normal(name), []).append(cells)
    return rows


def missing(doc: str, heading: str, pins) -> list[str]:
    """What is absent: a pin with no row, a row without that version, or a row with an empty licence cell."""
    rows = section_rows(doc, heading)
    problems = []
    for name, version in pins:
        found = rows.get(name)
        if not found:
            problems.append(f"{name}: no row under {heading!r}")
            continue
        if version is not None and not any(re.search(rf"(?<![\w.]){re.escape(version)}(?![\w])", r[1])
                                           for r in found):
            problems.append(f"{name}=={version}: the row under {heading!r} does not name this version")
        if not all(len(r) > 2 and r[2] for r in found):
            problems.append(f"{name}: a row under {heading!r} has no licence")
    return problems


class ThirdPartyListTests(unittest.TestCase):
    def setUp(self):
        self.doc = DOC.read_text(encoding="utf-8")

    def test_every_locked_package_has_a_row_with_its_version_and_licence(self):
        for path, heading in LOCKS.items():
            with self.subTest(lock=path):
                pins = lock_pins((ROOT / path).read_text(encoding="utf-8"))
                self.assertGreater(len(pins), 10, f"no pins read from {path}")
                self.assertEqual(missing(self.doc, heading, pins), [])

    def test_every_pyproject_pin_has_a_row(self):
        pins = pyproject_pins((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual({n for n, _ in pins}, {"setuptools", "claim-seal", "certifi"})
        self.assertEqual(missing(self.doc, PACKAGE_SECTION, pins), [])

    def test_the_check_fails_when_a_package_is_left_out(self):
        heading = LOCKS["composer/narration/requirements.lock"]
        pins = lock_pins((ROOT / "composer/narration/requirements.lock").read_text(encoding="utf-8"))
        without = "\n".join(ln for ln in self.doc.splitlines() if not ln.startswith("| [phonemizer-fork]"))
        self.assertIn("phonemizer-fork: no row under '## Narration (optional)'", missing(without, heading, pins))
        wrong = re.sub(r"(\| \[soundfile\]\([^)]*\) \| )0\.13\.1", r"\g<1>0.13.0", self.doc)
        self.assertNotEqual(wrong, self.doc)
        self.assertIn("soundfile==0.13.1: the row under '## Narration (optional)' does not name this version",
                      missing(wrong, heading, pins))

    def test_the_gpl_parts_are_named_as_gpl(self):
        rows = section_rows(self.doc, LOCKS["composer/narration/requirements.lock"])
        self.assertIn("GPL-3.0-or-later", rows["phonemizer-fork"][0][2])
        self.assertIn("GPL-3.0-or-later", rows["espeak"][0][2])
        self.assertIn("phonemizer-fork", self.doc[:self.doc.index(PACKAGE_SECTION)])


if __name__ == "__main__":
    unittest.main()
