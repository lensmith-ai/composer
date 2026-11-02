"""Setup's closing note and the README name the three ways to get a brief every day: this computer (only while it
is awake), your own server with a domain (always on, read anywhere), or the emailed brief (no setup)."""
import unittest
from pathlib import Path

from composer import installer

from helpers import ROOT
from install_helpers import fake_home

ANSWERS = """
[provider]
kind = "none"

[narration]
enabled = false

[schedule]
enabled = {enabled}
time = "06:30"
timezone = "UTC"

[server]
port = {port}
"""


def setup_output(home: Path, schedule_on: bool) -> list[str]:
    lines: list[str] = []
    path = home.parent / "answers.toml"
    path.write_text(ANSWERS.format(enabled="true" if schedule_on else "false",
                                   port=installer.next_free_port(18800)), encoding="utf-8")
    code = installer.run(home=home / ".lensmith-composer", data=None, answers_file=str(path), assume_yes=False,
                         reconfigure=[], data_only=False, out=lines.append, interactive=False)
    assert code == 0, lines
    return lines


class SetupClosingNoteTests(unittest.TestCase):
    def test_setup_ends_with_the_three_ways(self):
        with fake_home() as home:
            lines = setup_output(home, schedule_on=False)
        start = lines.index("To get this every day, pick one:")
        tail = lines[start:]
        self.assertEqual(len(tail), 4, tail)
        self.assertIn("This computer", tail[1])
        self.assertIn("only while `composer up` runs and this computer is awake", tail[1])
        self.assertIn("setup --reconfigure schedule", tail[1])
        self.assertIn("Your own server with a domain: always on, and you can read it from anywhere", tail[2])
        self.assertIn("docs/deploy-vps.md", tail[2])
        self.assertIn("No setup", tail[3])
        self.assertIn("lensmith.ai", tail[3])

    def test_with_the_daily_brief_on_it_says_so_instead_of_how_to_turn_it_on(self):
        with fake_home() as home:
            lines = setup_output(home, schedule_on=True)
        laptop = [x for x in lines if x.startswith("  1. This computer")]
        self.assertEqual(len(laptop), 1)
        self.assertIn("your daily brief is on, at 06:30", laptop[0])
        self.assertNotIn("--reconfigure", laptop[0])

    def test_the_deploy_guide_it_names_exists(self):
        self.assertTrue(installer.DEPLOY_GUIDE.endswith("/docs/deploy-vps.md"))
        self.assertTrue((ROOT / "docs" / "deploy-vps.md").is_file())


class ReadmeTests(unittest.TestCase):
    def test_the_readme_names_the_same_three_ways(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        section = text[text.index("## To get this every day"):]
        section = section[:section.index("\n## ", 3)]
        for words in ("only while", "awake", "docs/deploy-vps.md", "Always on", "lensmith.ai"):
            self.assertIn(words, section)


if __name__ == "__main__":
    unittest.main()
