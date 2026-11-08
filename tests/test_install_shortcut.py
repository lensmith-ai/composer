"""The installer's shortcut (`lensmith composer` from any terminal): PATH detection, the shell-profile fallback, and the
collision cases. The shell code under test is the pathlib region of scripts/install/install.sh.in, run in a sandbox with
its own HOME, PATH and SHELL."""
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

TEMPLATE = (ROOT / "scripts" / "install" / "install.sh.in").read_text(encoding="utf-8")
PATHLIB = re.search(r"^# BEGIN pathlib.*?^# END pathlib\n", TEMPLATE, re.S | re.M).group(0)


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class ShortcutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="composer-shortcut-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.home = self.tmp / "home"
        self.home.mkdir()
        self.app = self.tmp / "app home"
        (self.app / "bin").mkdir(parents=True)
        self.target = self.app / "bin" / "lensmith"
        self.target.write_text("#!/bin/sh\n")
        self.target.chmod(0o755)
        self.sysbin = self.tmp / "sysbin"
        self.sysbin.mkdir()
        for tool in "sh find id uname readlink grep ln cat printf tr awk ls".split():
            real = shutil.which(tool)
            if real and not (self.sysbin / tool).exists():
                (self.sysbin / tool).symlink_to(real)

    def run_sc(self, mode="ask", path_dirs=(), shell="/bin/bash", tty=False, reply="", extra_setup=""):
        path = ":".join([*map(str, path_dirs), str(self.sysbin)])
        has_tty = "has_tty() { return 0; }" if tty else "has_tty() { return 1; }"
        script = (f'{PATHLIB}\n{has_tty}\n{extra_setup}\nshortcut_setup {shlex.quote(str(self.target))} {mode} < /dev/null\n'
                  'printf "HOW=%s\\nNOTE=%s\\n" "$SHORTCUT_HOW" "$SHORTCUT_NOTE"\n')
        if tty:  # answer the question through the fake /dev/tty replacement
            script = script.replace("> /dev/tty", "> /dev/null").replace("< /dev/tty", f"< {self.tmp / 'tty'}")
            (self.tmp / "tty").write_text(reply + "\n")
        run = subprocess.run([str(self.sysbin / "sh"), "-c", script], capture_output=True, text=True, timeout=20,
                             env={"PATH": path, "HOME": str(self.home), "SHELL": shell, "LANG": "C"})
        out = dict(re.findall(r"^(HOW|NOTE)=(.*)$", run.stdout, re.M))
        return out, run

    def test_a_folder_you_own_that_is_on_path_gets_a_link(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        out, run = self.run_sc(path_dirs=[local])
        self.assertEqual(out["HOW"], "link", run.stdout + run.stderr)
        self.assertEqual(os.readlink(local / "lensmith"), str(self.target))
        self.assertFalse((self.home / ".zshrc").exists() or (self.home / ".bashrc").exists())

    def test_a_folder_that_is_not_on_path_is_not_used_and_nothing_is_written_without_a_yes(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        out, _ = self.run_sc(path_dirs=[], mode="ask", tty=False)
        self.assertEqual(out["HOW"], "none")
        self.assertIn("no terminal to ask on", out["NOTE"])
        self.assertFalse((local / "lensmith").exists())
        self.assertEqual(list(self.home.glob(".*rc")) + list(self.home.glob(".profile")) + list(self.home.glob(".bash_profile")), [])

    def test_saying_no_writes_nothing(self):
        out, _ = self.run_sc(mode="ask", tty=True, reply="n", shell="/bin/zsh")
        self.assertEqual(out["HOW"], "none")
        self.assertFalse((self.home / ".zshrc").exists())

    def test_yes_adds_three_marked_lines_to_the_zsh_profile_once(self):
        out, _ = self.run_sc(mode="ask", tty=True, reply="", shell="/bin/zsh")  # Enter = yes
        self.assertEqual(out["HOW"], "profile")
        text = (self.home / ".zshrc").read_text()
        self.assertEqual(text.count("# >>> lensmith"), 1)
        q, b = chr(39), chr(92)
        self.assertIn("alias lensmith=" + q + q + b + q + q + str(self.target) + q + b + q + q + q, text)  # quoted twice; the space survives
        self.assertIn("delete these 3 lines to undo", text)
        again, _ = self.run_sc(mode="yes", shell="/bin/zsh")  # idempotent
        self.assertEqual(again["HOW"], "profile")
        self.assertEqual((self.home / ".zshrc").read_text().count("# >>> lensmith"), 1)

    def test_the_profile_file_follows_the_shell(self):
        self.run_sc(mode="yes", shell="/bin/bash")
        self.assertTrue((self.home / ".bashrc").exists() or (self.home / ".bash_profile").exists())
        self.run_sc(mode="yes", shell="/usr/bin/fish")
        self.assertTrue((self.home / ".profile").exists())

    def test_no_path_makes_no_shortcut_at_all(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        out, _ = self.run_sc(mode="no", path_dirs=[local])
        self.assertEqual(out["HOW"], "none")
        self.assertFalse((local / "lensmith").exists())

    def test_an_existing_other_lensmith_on_path_is_never_shadowed_or_replaced(self):
        other = self.tmp / "other"
        other.mkdir()
        (other / "lensmith").write_text("#!/bin/sh\necho someone else's\n")
        (other / "lensmith").chmod(0o755)
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        out, _ = self.run_sc(path_dirs=[other, local], mode="yes")
        self.assertEqual(out["HOW"], "other")
        self.assertIn("left alone", out["NOTE"])
        self.assertFalse((local / "lensmith").exists())
        self.assertFalse((self.home / ".bashrc").exists())

    def test_a_file_already_named_lensmith_in_the_folder_is_left_alone(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "lensmith").write_text("not ours")
        # not executable, so `command -v` does not see it; the link must still not overwrite it
        out, _ = self.run_sc(path_dirs=[local], mode="ask", tty=False)
        self.assertEqual((local / "lensmith").read_text(), "not ours")
        self.assertFalse((local / "lensmith").is_symlink())

    def test_our_own_link_already_there_counts_as_done(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        (local / "lensmith").symlink_to(self.target)
        out, _ = self.run_sc(path_dirs=[local])
        self.assertEqual(out["HOW"], "have")

    def test_php_composer_is_untouched_and_no_bare_composer_is_ever_made(self):
        php = self.tmp / "php"
        php.mkdir()
        (php / "composer").write_text("#!/bin/sh\necho PHP Composer\n")
        (php / "composer").chmod(0o755)
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        self.run_sc(path_dirs=[php, local])
        self.run_sc(path_dirs=[], mode="yes", shell="/bin/zsh")
        self.assertEqual((php / "composer").read_text(), "#!/bin/sh\necho PHP Composer\n")
        self.assertFalse((local / "composer").exists())
        for rc in self.home.glob(".*"):
            if rc.is_file():
                self.assertNotRegex(rc.read_text(), r"alias composer\b")
                self.assertNotIn("/bin:$PATH", rc.read_text())  # and the app's bin folder (which holds composer) is never put on PATH

    def test_a_newline_or_quote_in_the_install_folder_means_no_profile_line(self):
        for bad in ("/x/a\nb/bin/lensmith", "/x/it's/bin/lensmith", "/x/a\tb/bin/lensmith", "/x/trail\n"):
            with self.subTest(bad=bad):
                self.target = Path(bad)
                out, _ = self.run_sc(mode="yes", shell="/bin/zsh")
                self.assertEqual(out["HOW"], "none")
                self.assertFalse((self.home / ".zshrc").exists())

    def test_the_alias_runs_for_hostile_folder_names_without_running_them(self):
        """A shell reads an alias's text again as commands: a folder named with ; or $( ) or a space must still be one word."""
        for name in ("my user", "a;touch PWNED_SEMI;b", "x$(touch PWNED_DOLLAR)y", "back`touch PWNED_TICK`tick", 'dq"x'):
            with self.subTest(name=name):
                app = self.tmp / name
                (app / "bin").mkdir(parents=True)
                script = app / "bin" / "lensmith"
                script.write_text('#!/bin/sh\necho "lensmith ran with $*"\n')
                script.chmod(0o755)
                self.target = script
                home = self.tmp / ("h" + str(abs(hash(name))))
                home.mkdir()
                self.home = home
                out, _ = self.run_sc(mode="yes", shell="/bin/bash")
                self.assertEqual(out["HOW"], "profile", out)
                rc = next(p for p in home.iterdir() if p.name in (".bashrc", ".bash_profile"))
                run = subprocess.run(["bash", "-c", f"shopt -s expand_aliases\n. {shlex.quote(str(rc))}\nlensmith composer\n"],
                                     capture_output=True, text=True, cwd=self.tmp, timeout=20, env={"PATH": os.environ["PATH"], "HOME": str(home)})
                self.assertIn("lensmith ran with composer", run.stdout + run.stderr)
                self.assertEqual([p.name for p in self.tmp.iterdir() if p.name.startswith("PWNED")], [])

    def test_the_shell_and_python_write_the_same_alias_line(self):
        import sys
        sys.path.insert(0, str(ROOT))
        from composer import installer as I
        for name in ("plain", "my user", "a;b", "x$(y)", "q`z`", 'dq"x', "caf\u00e9"):
            home = self.tmp / name
            script = f'{PATHLIB}\nalias_line {shlex.quote(str(home / "bin" / "lensmith"))}\n'
            run = subprocess.run([str(self.sysbin / "sh"), "-c", script], capture_output=True, text=True,
                                 env={"PATH": str(self.sysbin), "LC_ALL": "C.UTF-8"})
            self.assertEqual(run.stdout.rstrip("\n"), I.alias_line(home), name)

    def test_a_group_writable_link_folder_is_fine_but_an_other_writable_one_is_not(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        local.chmod(0o775)
        out, _ = self.run_sc(path_dirs=[local])
        self.assertEqual(out["HOW"], "link")

    def test_a_folder_with_spaces_and_accents_is_fine(self):
        self.target = self.tmp / "café app" / "bin" / "lensmith"
        out, _ = self.run_sc(mode="yes", shell="/bin/zsh")
        self.assertEqual(out["HOW"], "profile")

    def test_lines_for_another_install_are_left_alone_and_said(self):
        (self.home / ".zshrc").write_text("# >>> lensmith (added by the Composer installer; delete these 3 lines to undo)\n"
                                         "alias lensmith='/somewhere/else/bin/lensmith'\n# <<< lensmith\n")
        before = (self.home / ".zshrc").read_text()
        out, _ = self.run_sc(mode="yes", shell="/bin/zsh")
        self.assertEqual(out["HOW"], "none")
        self.assertIn("another install", out["NOTE"])
        self.assertEqual((self.home / ".zshrc").read_text(), before)

    def test_a_profile_that_is_a_link_is_not_edited(self):
        real = self.tmp / "dotfiles"
        real.write_text("export A=1\n")
        (self.home / ".zshrc").symlink_to(real)
        out, _ = self.run_sc(mode="yes", shell="/bin/zsh")
        self.assertEqual(out["HOW"], "none")
        self.assertEqual(real.read_text(), "export A=1\n")

    def test_a_new_profile_is_made_world_readable_not_private(self):
        self.run_sc(mode="yes", shell="/bin/zsh", extra_setup="umask 077")
        self.assertEqual(os.stat(self.home / ".zshrc").st_mode & 0o044, 0o044)

    def test_a_link_folder_that_others_can_write_is_not_used(self):
        local = self.home / ".local" / "bin"
        local.mkdir(parents=True)
        local.chmod(0o777)
        out, _ = self.run_sc(path_dirs=[local], mode="ask", tty=False)
        self.assertEqual(out["HOW"], "none")
        self.assertFalse((local / "lensmith").exists())

    def test_the_shared_folder_check_reads_selinux_and_acl_marks_correctly(self):
        shim = self.tmp / "shim"
        shim.mkdir()
        for mode, unsafe in (("drwxrwxrwt.", False), ("drwxrwxrwt+", False), ("drwxrwxrwt@", False), ("drwxrwxrwx.", True),
                             ("drwxrwxr-x", True), ("drwxr-xr-x", False), ("drwx------", False), ("drwxr-xrwx@", True)):
            (shim / "ls").write_text(f'#!/bin/sh\necho "{mode} 2 0 0 4096 Nov 8 10:00 $3"\n')
            (shim / "ls").chmod(0o755)
            script = f'PATH="{shim}:$PATH"\n{PATHLIB}\nif unsafe_tmp_parent /tmp; then echo unsafe; else echo ok; fi\n'
            run = subprocess.run([str(self.sysbin / "sh"), "-c", script], capture_output=True, text=True,
                                 env={"PATH": f"{self.sysbin}", "HOME": str(self.home)})
            self.assertEqual(run.stdout.strip(), "unsafe" if unsafe else "ok", (mode, run.stderr))

    def test_the_template_never_puts_the_app_bin_folder_on_path(self):
        self.assertNotRegex(PATHLIB, r"export PATH")


if __name__ == "__main__":
    unittest.main()
