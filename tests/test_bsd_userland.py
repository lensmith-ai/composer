"""The installer must run on macOS, whose userland is BSD, not GNU. Every other test in this suite runs on Linux (GNU
coreutils), which is how `chmod -R go-w -- DIR` shipped: GNU chmod accepts `--` after the mode, BSD chmod reads the mode
first and then takes `--` for a file name ("chmod: --: No such file or directory", seen on a Mac, 2026-11-09).

Two kinds of test here, neither a substitute for the real macOS job in .github/workflows/ci.yml:
- a scan of every shell the installer runs for the GNU-only forms that break on BSD;
- a real setup.sh run on a PATH whose `chmod` refuses what BSD chmod refuses."""
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT
from install_helpers import fake_home
import test_setup_sh_messages as M

# BSD chmod's argument handling, as a shell script over the real chmod: options first, then the mode, then names. Only
# what an installer can trip on: a `--` after the mode is a file name, and so is anything else after it.
BSD_CHMOD = """#!/bin/sh
real=%s
flags=""
while [ $# -gt 0 ]; do
  case "$1" in
    --) shift; break ;;
    -[RHLPfhvx]*) flags="$flags $1"; shift ;;
    -*) break ;;
    *) break ;;
  esac
done
[ $# -ge 2 ] || { echo "usage: chmod [-fhv] [-R [-H | -L | -P]] mode file ..." >&2; exit 1; }
mode=$1; shift
rc=0
for f in "$@"; do
  if [ ! -e "$f" ] && [ ! -L "$f" ]; then echo "chmod: $f: No such file or directory" >&2; rc=1; continue; fi
  $real $flags "$mode" "$f" || rc=1
done
exit $rc
"""

# GNU-only (or Linux-only) forms in shell: (name, regex over one non-comment line)
GNU_ISMS = [
    ("a `--` after a chmod/chown mode (BSD reads it as a file name)", r"\b(chmod|chown|chgrp)\b[^|;&]*\s--(\s|$)"),
    ("sed -i with no suffix argument", r"\bsed\b[^|;&]*\s-i\b"),
    ("readlink -f", r"\breadlink\s+-[a-zA-Z]*f"),
    ("realpath (missing on older macOS)", r"(^|[^A-Za-z_./-])realpath\b"),
    ("stat -c / stat -f -c (BSD stat takes -f FORMAT)", r"\bstat\s+(-f\s+)?-c\b"),
    ("date -d", r"\bdate\s+(-u\s+)?-d\b"),
    ("cp -T / --target-directory / --no-target-directory", r"\b(cp|mv|ln)\b[^|;&]*\s(-T|--target-directory|--no-target-directory)\b"),
    ("cp --parents / --preserve= / -a long forms", r"\bcp\b[^|;&]*\s--(parents|preserve|reflink|archive)\b"),
    ("install -D", r"\binstall\s+(-[a-zA-Z]*D|-D)"),
    ("grep -P", r"\bgrep\s+-[a-zA-Z]*P"),
    ("xargs -r / --no-run-if-empty", r"\bxargs\b[^|;&]*\s(-r|--no-run-if-empty)\b"),
    ("timeout (not on macOS)", r"(^|[|;&(]\s*|\$\(\s*)timeout\s"),
    ("sort -V / sort -R", r"\bsort\s+-[a-zA-Z]*[VR]"),
    ("head/tail with a negative count (head -n -N)", r"\bhead\s+-n\s*-\d"),
    ("tail -n +N is fine; tac is GNU-only", r"(^|[|;&(]\s*)tac\b"),
    ("echo -e / echo -n (differs by sh)", r"\becho\s+-[en]\b"),
    ("find -printf / -regextype", r"\bfind\b[^|;&]*\s(-printf|-regextype|-readable|-executable)\b"),
    ("a bash-ism under sh: [[ ]], <<<, $'..', ${x,,}, arrays, local, function, source, pipefail",
     r"(\[\[ |[^#]\s<<<\s|\$'|\$\{[A-Za-z_]+(,,|\^\^)|\blocal\s|^\s*function\s|^\s*source\s|pipefail)"),
    ("mktemp -t or an empty template (differs between GNU and BSD)", r"\bmktemp\s+(-d\s+)?(-t\b|\"?\)|\$)"),
    ("cp/rm/mv --force-style long options GNU only", r"\b(rm|mv|cp)\b[^|;&]*\s--(force|recursive|verbose|interactive)\b"),
    ("tar --wildcards / --transform / -z with --overwrite-dir (GNU tar only)", r"\btar\b[^|;&]*\s--(wildcards|transform|owner=|group=)\b"),
    ("ls --time-style / --color / -l --block-size", r"\bls\b[^|;&]*\s--(time-style|block-size|color|full-time)\b"),
]


def shell_texts():
    """Every shell script the installer runs or writes: install.sh's template, setup.sh, and the launchers
    `composer setup` writes into the app folder (their text is a Python string in installer.py)."""
    out = {"scripts/install/install.sh.in": (ROOT / "scripts/install/install.sh.in").read_text(encoding="utf-8"),
           "setup.sh": (ROOT / "setup.sh").read_text(encoding="utf-8")}
    import composer.installer as I
    out["composer/installer.py LENSMITH_SH"] = I.LENSMITH_SH
    out["composer/installer.py APP_LAUNCH"] = I.APP_LAUNCH
    out["composer/installer.py launcher"] = I._launcher_text(Path("/x/home"), 'exec "$X"')
    return out


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class GnuIsmScanTests(unittest.TestCase):
    def test_no_shell_the_installer_runs_uses_a_gnu_only_form(self):
        found = []
        for name, text in shell_texts().items():
            text = text.replace("\\\n", " ")  # a command continued on the next line is one command (line numbers then run short)
            for n, line in enumerate(text.splitlines(), 1):
                body = line.strip()
                if not body or body.startswith("#"):
                    continue
                body = re.sub(r"\s#\s.*$", "", body)  # a trailing comment is prose
                for what, rx in GNU_ISMS:
                    if what.startswith("stat -c") and re.search(r'uname -s\)" = Linux \]', body):
                        continue  # the one GNU stat call, run only where uname says Linux
                    if re.search(rx, body):
                        found.append(f"{name}:{n}: {what}: {body[:110]}")
        self.assertEqual(found, [], "\n".join(found))

    def test_the_scan_has_teeth(self):
        """Each bad form below is caught, and each safe twin is not."""
        bad = ['chmod -R go-w -- "$H/app"', 'chown -R me -- "$d"', "sed -i 's/a/b/' f", 'readlink -f "$p"',
               "stat -c %a f", "stat -f -c %T f", "date -d yesterday", "cp -T a b", "grep -P 'x' f", "xargs -r rm",
               "timeout 5 curl x", "x=$(timeout 5 ls)", "[[ a == b ]]", "mktemp -t x"]
        ok = ['chmod -R go-w "$H/app"', 'chmod_go_w "$d"', "sed -n 's/a/b/p' f", 'readlink "$p"', "rm -rf -- \"$d\"",
              'cp -- "$a" "$b"', 'ls -ldn -- "$1"', "find \"$H\" -maxdepth 0 -user 1 -print"]
        for line in bad:
            self.assertTrue(any(re.search(rx, line) for _, rx in GNU_ISMS), line)
        for line in ok:
            self.assertFalse([w for w, rx in GNU_ISMS if re.search(rx, line)], line)


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class BsdChmodRunTests(unittest.TestCase):
    """setup.sh run for real in the setup sandbox, with a `chmod` that behaves like macOS's."""

    sandbox = M.SetupShMessageTests.sandbox
    run_setup = M.SetupShMessageTests.run_setup

    def bsd_sandbox(self, **kw):
        env, log = self.sandbox(**kw)
        bin_dir = Path(env["PATH"])
        real = shutil.which("chmod")
        (bin_dir / "chmod").unlink()
        shim = bin_dir / "chmod"
        shim.write_text(BSD_CHMOD % real, encoding="utf-8")
        shim.chmod(0o755)
        return env, log

    def test_the_shim_refuses_what_macos_refuses(self):
        d = Path(tempfile.mkdtemp(prefix="composer-bsdchmod-"))
        self.addCleanup(shutil.rmtree, d, True)
        shim = d / "chmod"
        shim.write_text(BSD_CHMOD % shutil.which("chmod"), encoding="utf-8")
        shim.chmod(0o755)
        f = d / "f"
        f.write_text("x")
        bad = subprocess.run([str(shim), "-R", "go-w", "--", str(f)], capture_output=True, text=True)
        self.assertNotEqual(bad.returncode, 0)
        self.assertIn("chmod: --: No such file or directory", bad.stderr)
        good = subprocess.run([str(shim), "-R", "go-w", str(f)], capture_output=True, text=True)
        self.assertEqual(good.returncode, 0, good.stderr)

    def test_setup_makes_the_environment_with_group_writable_templates_on_a_bsd_chmod(self):
        with fake_home() as home:
            env, _ = self.bsd_sandbox(py312_works=True)
            run = self.run_setup(home, dict(env, FAKE_VENV_GW="1"), "--home", str(home / "app"), "--python-download", "--yes")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertNotIn("No such file or directory", run.stdout + run.stderr)
            mode = (home / "app" / "app" / M.VERSION_FOLDER(home) / "venv" / "bin" / "Activate.ps1").stat().st_mode & 0o777
            self.assertEqual(mode & 0o022, 0, oct(mode))

    def test_the_old_form_fails_on_a_bsd_chmod_so_this_test_can_tell(self):
        with fake_home() as home:
            env, _ = self.bsd_sandbox(py312_works=True)
            copy = Path(tempfile.mkdtemp(prefix="composer-oldform-"))
            self.addCleanup(shutil.rmtree, copy, True)
            text = (ROOT / "setup.sh").read_text(encoding="utf-8").replace(
                'chmod_go_w "$H/app/$VERSION"\n', 'chmod -R go-w -- "$H/app/$VERSION"\n')
            (copy / "setup.sh").write_text(text, encoding="utf-8")
            for name in ("pyproject.toml", "composer", "README.md", "LICENSE"):
                (copy / name).symlink_to(ROOT / name)
            run = subprocess.run([shutil.which("sh"), str(copy / "setup.sh"), "--home", str(home / "app"), "--python-download",
                                  "--yes"], capture_output=True, text=True, timeout=60, env=dict(env, HOME=str(home)),
                                 cwd=ROOT, start_new_session=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("chmod: --: No such file or directory", run.stdout + run.stderr)
            self.assertIn("stopped unexpectedly during step 4", run.stdout + run.stderr)

    def test_a_half_made_folder_with_read_only_folders_is_removed_on_a_bsd_chmod(self):
        """The rerun path: chmod_u_w opens read-only folders so rm can remove them; no `--` anywhere."""
        with fake_home() as home:
            env, _ = self.bsd_sandbox(py312_works=True)
            base = home / "app"
            folder = base / "app" / M.VERSION_FOLDER(home)
            (folder / "venv" / "lib").mkdir(parents=True)
            (folder / "venv" / "lib" / "x").write_text("x")
            (folder / "venv" / "lib").chmod(0o555)
            (base / ".composer-home").write_text("lensmith-composer home v1\n")
            (base / "app" / f".making-{M.VERSION_FOLDER(home)}").write_text("")
            run = self.run_setup(home, env, "--home", str(base), "--python-download", "--yes")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("removing that half-made folder first", run.stdout)
            self.assertNotIn("No such file or directory", run.stdout + run.stderr)


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class ChmodHelperTests(unittest.TestCase):
    """chmod_go_w and chmod_u_w taken out of setup.sh and run on their own, on a PATH whose chmod is BSD-like. They check
    modes directly, so they hold when the tests run as root (where removing a read-only folder works with or without
    them)."""

    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="composer-chmodhelp-"))
        self.addCleanup(shutil.rmtree, self.d, True)
        bin_dir = self.d / "bin"
        bin_dir.mkdir()
        shim = bin_dir / "chmod"
        shim.write_text(BSD_CHMOD % shutil.which("chmod"), encoding="utf-8")
        shim.chmod(0o755)
        for tool in ("find", "sh"):
            (bin_dir / tool).symlink_to(shutil.which(tool))
        lines = [l for l in (ROOT / "setup.sh").read_text(encoding="utf-8").splitlines() if re.match(r"chmod_(go_w|u_w)\(\)", l)]
        self.assertEqual(len(lines), 2)
        (self.d / "helpers.sh").write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.env = {"PATH": str(bin_dir)}

    def run_helper(self, name, arg, cwd=None):
        return subprocess.run(["sh", "-c", f". {self.d / 'helpers.sh'}; {name} \"$1\"", "sh", arg], capture_output=True, text=True,
                              env=self.env, cwd=cwd or self.d)

    def mode(self, path):
        return stat.S_IMODE(os.lstat(path).st_mode)

    def test_go_w_takes_group_and_other_write_off_files_and_folders_but_not_through_links(self):
        top = self.d / "a folder with spaces"
        (top / "sub").mkdir(parents=True)
        f = top / "sub" / "file one"
        f.write_text("x")
        f.chmod(0o777)
        (top / "sub").chmod(0o775)
        top.chmod(0o777)
        outside = self.d / "outside"
        outside.write_text("y")
        outside.chmod(0o666)
        (top / "link").symlink_to(outside)
        r = self.run_helper("chmod_go_w", str(top))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.mode(f), 0o755)
        self.assertEqual(self.mode(top / "sub"), 0o755)
        self.assertEqual(self.mode(top), 0o755)
        self.assertEqual(self.mode(outside), 0o666)  # the link's target is not touched

    def test_u_w_gives_the_owner_write_back_on_read_only_folders_and_files(self):
        top = self.d / "half made"
        (top / "lib").mkdir(parents=True)
        f = top / "lib" / "x"
        f.write_text("x")
        f.chmod(0o444)
        (top / "lib").chmod(0o555)
        top.chmod(0o555)
        r = self.run_helper("chmod_u_w", str(top))
        self.assertEqual(r.returncode, 0, r.stderr)
        for path in (f, top / "lib", top):
            self.assertTrue(self.mode(path) & 0o200, f"{path} {oct(self.mode(path))}")

    def test_a_folder_whose_name_starts_with_a_dash_and_a_relative_path_are_not_taken_for_options(self):
        top = self.d / "-odd"
        top.mkdir()
        (top / "f").write_text("x")
        (top / "f").chmod(0o666)
        r = self.run_helper("chmod_go_w", "-odd", cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.mode(top / "f"), 0o644)
        r = self.run_helper("chmod_go_w", "-odd/f", cwd=self.d)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_missing_folder_is_an_error_not_a_silent_success(self):
        r = self.run_helper("chmod_go_w", str(self.d / "nothing here"))
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
