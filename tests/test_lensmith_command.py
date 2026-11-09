"""`lensmith`, the umbrella command: `lensmith composer` starts the app and opens the browser, the rest map to
composer's own subcommands, and no bare `composer` is ever made for the PATH."""
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import sys

from helpers import ROOT

sys.path.insert(0, str(ROOT))
from composer import installer as I  # noqa: E402


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class LensmithCommandTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="composer-lensmith-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "app home"  # a space in the path on purpose
        (self.home / "bin").mkdir(parents=True)
        fake = self.home / "bin" / "composer"
        fake.write_text('#!/bin/sh\nif [ "$1" = --version ]; then echo "composer 9.9.9"; exit 0; fi\n'
                        'if [ "$1" = uninstall ] && [ "${FAKE_NOREMOVE:-}" != 1 ] && [ "${FAKE_RC:-0}" = 0 ]; then rm -f "$0"; fi\n'
                        'echo "composer called with: $*"\nexit "${FAKE_RC:-0}"\n')
        fake.chmod(0o755)
        self.script = self.home / "bin" / "lensmith"
        self.script.write_text(I.lensmith_text(self.home))
        self.script.chmod(0o755)
        self.user = self.tmp / "user"
        self.user.mkdir()

    def run_lensmith(self, *args, **env):
        return subprocess.run([str(self.script), *args], capture_output=True, text=True, timeout=20,
                              env={"PATH": os.environ["PATH"], "HOME": str(self.user), **env})

    def test_alone_prints_three_lines_naming_lensmith_composer(self):
        run = self.run_lensmith()
        self.assertEqual(run.returncode, 0)
        lines = run.stdout.strip().splitlines()
        self.assertEqual(len(lines), 3, run.stdout)
        self.assertIn("lensmith composer", lines[1])
        self.assertEqual(self.run_lensmith("help").stdout, run.stdout)

    def test_version(self):
        run = self.run_lensmith("--version")
        self.assertEqual(run.stdout.strip(), "lensmith (composer 9.9.9)")

    def test_lensmith_composer_starts_the_app_and_opens_the_browser(self):
        self.assertIn("composer called with: up --open", self.run_lensmith("composer").stdout)
        self.assertIn("composer called with: up --open --port 9000", self.run_lensmith("composer", "up", "--port", "9000").stdout)

    def test_no_open_is_honoured(self):
        out = self.run_lensmith("composer", "--no-open").stdout
        self.assertIn("composer called with: up", out)
        self.assertNotIn("--open", out)

    def test_subcommands_map_to_composer(self):
        for sub in ("doctor", "update", "rollback", "--version", "setup"):
            with self.subTest(sub=sub):
                out = self.run_lensmith("composer", sub).stdout
                self.assertTrue("composer 9.9.9" in out if sub == "--version" else f"composer called with: {sub}" in out, out)

    def test_an_unknown_product_is_a_clear_error(self):
        run = self.run_lensmith("nonsense")
        self.assertEqual(run.returncode, 2)
        self.assertIn("no product called 'nonsense'", run.stderr)
        self.assertIn("lensmith composer", run.stderr)

    def test_uninstall_removes_only_the_shortcuts_it_can_prove_are_its_own(self):
        local = self.user / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "lensmith").symlink_to(self.home / "bin" / "lensmith")
        other = self.user / "bin"
        other.mkdir()
        (other / "lensmith").write_text("someone else's program")  # a different file: not ours, not removed
        rc = self.user / ".zshrc"
        rc.write_text(f"export A=1\n{I.SHORTCUT_BEGIN}\n{self._alias(self.home)}\n{I.SHORTCUT_END}\nexport B=2\n")
        run = self.run_lensmith("composer", "uninstall")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertFalse((local / "lensmith").exists() or (local / "lensmith").is_symlink())
        self.assertTrue((other / "lensmith").exists())
        self.assertEqual(rc.read_text(), "export A=1\nexport B=2\n")

    def _alias(self, home):
        q, b = chr(39), chr(92)  # the line install.sh writes: the path quoted twice (alias_line)
        return "alias lensmith=" + q + q + b + q + q + f"{home}/bin/lensmith" + q + b + q + q + q

    def _profile_with_block(self, extra_before="", extra_after="", name=".zshrc", home=None):
        rc = self.user / name
        block = f"{I.SHORTCUT_BEGIN}\n{self._alias(home or self.home)}\n{I.SHORTCUT_END}\n"
        rc.write_text(extra_before + block + extra_after)
        return rc

    def test_a_block_with_no_end_marker_is_left_whole(self):
        rc = self.user / ".zshrc"
        text = f"export A=1\n{I.SHORTCUT_BEGIN}\n{self._alias(self.home)}\nexport IMPORTANT=2\nexport MORE=3\n"
        rc.write_text(text)
        self.run_lensmith("composer", "uninstall")
        self.assertEqual(rc.read_text(), text)

    def test_your_own_section_with_a_similar_marker_is_not_touched(self):
        rc = self.user / ".zshrc"
        text = "# >>> lensmith notes\nmy own things\n# <<< lensmith notes end\nexport A=1\n"
        rc.write_text(text)
        self.run_lensmith("composer", "uninstall")
        self.assertEqual(rc.read_text(), text)

    def test_the_block_of_another_install_is_left_alone(self):
        rc = self._profile_with_block(home=self.tmp / "other install")
        before = rc.read_text()
        self.run_lensmith("composer", "uninstall")
        self.assertEqual(rc.read_text(), before)

    def test_zdotdir_profile_is_cleaned_and_the_mode_is_kept(self):
        zd = self.tmp / "zd"
        zd.mkdir()
        rc = zd / ".zshrc"
        rc.write_text(f"export A=1\n{I.SHORTCUT_BEGIN}\n{self._alias(self.home)}\n{I.SHORTCUT_END}\n")
        rc.chmod(0o640)
        self.run_lensmith("composer", "uninstall", ZDOTDIR=str(zd))
        self.assertEqual(rc.read_text(), "export A=1\n")
        self.assertEqual(stat.S_IMODE(rc.stat().st_mode), 0o640)
        self.assertEqual([p.name for p in zd.iterdir()], [".zshrc"])  # no temp file left

    def test_a_symlinked_profile_is_never_rewritten(self):
        real = self.tmp / "dotfiles-zshrc"
        real.write_text(f"{I.SHORTCUT_BEGIN}\n{self._alias(self.home)}\n{I.SHORTCUT_END}\n")
        (self.user / ".zshrc").symlink_to(real)
        self.run_lensmith("composer", "uninstall")
        self.assertIn("alias lensmith", real.read_text())

    def test_a_link_to_another_install_is_not_removed(self):
        local = self.user / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "lensmith").symlink_to(self.tmp / "elsewhere" / "bin" / "lensmith")
        self.run_lensmith("composer", "uninstall")
        self.assertTrue((local / "lensmith").is_symlink())

    def test_uninstall_help_or_another_home_removes_no_shortcut_because_this_install_is_still_there(self):
        rc = self._profile_with_block()
        local = self.user / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "lensmith").symlink_to(self.home / "bin" / "lensmith")
        run = self.run_lensmith("composer", "uninstall", "--help", FAKE_NOREMOVE="1")
        self.assertEqual(run.returncode, 0)
        self.assertTrue((local / "lensmith").is_symlink())
        self.assertIn("alias lensmith", rc.read_text())

    def test_a_home_with_the_placeholder_text_or_shell_characters_is_one_quoted_word(self):  # vnf-allow: "placeholder" names the __HOME__ template token this test attacks
        evil = self.tmp / "x__HOME__;touch PWNED;x $(touch PWNED2) `touch PWNED3`"
        (evil / "bin").mkdir(parents=True)
        script = evil / "bin" / "lensmith"
        script.write_text(I.lensmith_text(evil))
        script.chmod(0o755)
        fake = evil / "bin" / "composer"
        fake.write_text('#!/bin/sh\necho "ran composer $*"\n')
        fake.chmod(0o755)
        run = subprocess.run([str(script), "composer", "doctor"], capture_output=True, text=True, timeout=20, cwd=self.tmp,
                             env={"PATH": os.environ["PATH"], "HOME": str(self.user)})
        self.assertIn("ran composer doctor", run.stdout, run.stderr)
        for name in ("PWNED", "PWNED2", "PWNED3"):
            self.assertFalse((self.tmp / name).exists())

    def test_a_failed_uninstall_removes_no_shortcut(self):
        rc = self.user / ".zshrc"
        rc.write_text(f"{I.SHORTCUT_BEGIN}\n{self._alias(self.home)}\n{I.SHORTCUT_END}\n")
        run = self.run_lensmith("composer", "uninstall", FAKE_RC="3")
        self.assertEqual(run.returncode, 3)
        self.assertIn("alias lensmith", rc.read_text())

    def test_setup_writes_lensmith_beside_composer_and_no_other_command(self):
        text = I.lensmith_text(Path("/x/home"))
        self.assertIn("/x/home/bin/composer", text)
        self.assertNotIn("alias composer", text)
        mode = stat.S_IMODE(os.stat(self.script).st_mode)
        self.assertEqual(mode & 0o022, 0)


if __name__ == "__main__":
    unittest.main()


EXTRAS_LINE = ("Optional extras, any time: lensmith composer setup --reconfigure "
               "parser | provider (model) | checker | narration | schedule | port")


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class ReconfigureThroughLensmithTests(unittest.TestCase):
    """The extras the install does not ask about are reached with `lensmith composer setup --reconfigure PART`: each part,
    through the real launcher `composer setup` wrote, on a real (offline, no key) install."""

    PARTS = ("parser", "provider", "checker", "narration", "schedule", "port", "sources")

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="composer-reconf-"))
        cls.user = cls.tmp / "user"
        cls.user.mkdir(mode=0o700)
        cls.home = cls.user / ".lensmith-composer"
        cls.env = {"PATH": os.environ["PATH"], "HOME": str(cls.user), "COMPOSER_NO_TEST_CALL": "1", "LANG": "C"}
        run = subprocess.run([sys.executable, "-m", "composer", "setup", "--yes", "--home", str(cls.home)], cwd=ROOT,
                             capture_output=True, text=True, timeout=120, env={**cls.env, "PYTHONPATH": str(ROOT)})
        assert run.returncode == 0, run.stdout + run.stderr

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def lensmith(self, *args):
        return subprocess.run([str(self.home / "bin" / "lensmith"), *args], capture_output=True, text=True, timeout=120,
                              env=self.env, stdin=subprocess.DEVNULL)

    def test_each_part_reconfigures_through_the_lensmith_launcher(self):
        for part in self.PARTS:
            with self.subTest(part=part):
                run = self.lensmith("composer", "setup", "--reconfigure", part, "--yes", "--no-test-call")
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertIn("setup. App folder:", run.stdout)
                self.assertNotIn("takes one of", run.stdout + run.stderr)

    def test_an_unknown_part_is_refused_and_names_the_parts(self):
        run = self.lensmith("composer", "setup", "--reconfigure", "nonsense", "--yes")
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("--reconfigure takes one of", run.stdout + run.stderr)

    def test_help_prints_the_extras_lines_and_they_match_the_installer_and_the_readme(self):
        run = self.lensmith("composer", "--help")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn(EXTRAS_LINE, run.stdout)
        shell = (ROOT / "scripts" / "install" / "install.sh.in").read_text(encoding="utf-8")
        self.assertIn("setup --reconfigure parser | provider (model) | checker | narration | schedule | port", shell)
        for line in run.stdout.splitlines():
            if line.startswith("  parser = ") or line.startswith("  narration = ") or line.startswith("  Each one asks"):
                self.assertIn(line, shell)
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("lensmith composer setup --reconfigure parser | provider (model) | checker | narration | schedule | port", readme)
