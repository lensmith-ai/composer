"""setup.sh's words, run in a sandbox: a fake old python3, a fake uv, curl and sha256sum on a PATH of their own.
Nothing is downloaded and no Python is installed: the point is what a person sees (why Python is downloaded,
numbered steps, the real error and the way forward, the timeout default), not the install itself."""
import io
import os
import re
import shutil
import sys
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT
from install_helpers import fake_home

TOOLS = ("id uname awk df ls find stat sed grep dirname basename cat tar mkdir rm rmdir cp readlink head sleep tr cut "
         "wc sort chmod mv ln date touch tail env mktemp gzip sh").split()

FAKE_PY = """#!/bin/sh
# a fake python: version {version}, usable={ok}
[ "$1" = -I ] && shift
case "$1" in
  -c) case "$2" in
        *'import sys, venv, ensurepip'*) [ "{ok}" = 1 ] && exit 0 || exit 1 ;;
        *'print("%d.%d.%d"'*) echo "{version}"; exit 0 ;;
        *'version_info >= (3, 10)'*) case "{version}" in 3.9*|3.8*|3.7*) exit 1 ;; *) exit 0 ;; esac ;;
      esac ;;
  -m) case "$2" in composer) exit 0 ;; venv) echo "fake python: venv refused" >&2; exit 1 ;; esac ;;
esac
exit 1
"""

FAKE_UV = """#!/bin/sh
[ "$1" = --version ] && { echo "uv 0.5.29"; exit 0; }
echo "$*" >> "$FAKE_LOG/uv-args"
case "$1 $2" in
  "python install")
    echo "timeout=$UV_HTTP_TIMEOUT" >> "$FAKE_LOG/uv-env"
    n=$(cat "$FAKE_LOG/uv-count" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$FAKE_LOG/uv-count"
    echo "Downloading cpython-3.12.9-fake (17.1MiB)" >&2
    case "$FAKE_UV_MODE" in
      fail) echo "error: Failed to download cpython-3.12.9 ... Request failed after 3 retries ... operation timed out" >&2; exit 2 ;;
      failonce) if [ "$n" = 1 ]; then echo "error: fake timeout, first try" >&2; exit 2; fi ;;
    esac
    exit 0 ;;
  "python find") echo "$FAKE_PY312"; exit 0 ;;
esac
exit 1
"""


# a python whose `-m venv DIR` makes a venv of fakes: DIR/bin/python (logs `-m pip install`, passes the symlink step
# to the real python) and DIR/bin/composer (--version, and `setup` which only says it was called)
FAKE_PY_WORKS = FAKE_PY.replace(
    'venv) echo "fake python: venv refused" >&2; exit 1 ;;',
    'venv) mkdir -p "$3/bin"; cp "$FAKE_VENV_PYTHON" "$3/bin/python"; cp "$FAKE_VENV_COMPOSER" "$3/bin/composer"; '
    '[ "$FAKE_VENV_GW" = 1 ] && {{ echo x > "$3/bin/Activate.ps1"; chmod 664 "$3/bin/Activate.ps1"; }}; exit 0 ;;')
FAKE_VENV_PYTHON = """#!/bin/sh
[ "$1" = -I ] && shift
case "$1 $2" in
  "-m pip")
    echo "pip-env timeout=$PIP_DEFAULT_TIMEOUT retries=$PIP_RETRIES args=$*" >> "$FAKE_LOG/pip"
    echo "Processing a fake source folder" >&2
    if [ "$FAKE_PIP_MODE" = fail ]; then echo "ERROR: fake pip: could not reach the index" >&2; exit 1; fi
    exit 0 ;;
esac
exec "$FAKE_REAL_PYTHON" -I "$@"
"""
FAKE_VENV_COMPOSER = """#!/bin/sh
case "$1" in --version) echo composer-fake; exit 0 ;; esac
echo "FAKE COMPOSER $*"
exit 0
"""


def VERSION_FOLDER(_home) -> str:
    """The version folder setup.sh makes: the version in pyproject.toml."""
    return re.search(r'^version = "([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M).group(1)


def write_exe(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)
    return path


def pinned_uv_sha() -> str | None:
    """The SHA-256 setup.sh pins for this computer's uv build, read from setup.sh itself."""
    system = subprocess.run(["uname", "-s"], capture_output=True, text=True).stdout.strip()
    machine = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
    key = f"{system}-{machine}"
    for line in (ROOT / "setup.sh").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s+([A-Za-z0-9_|-]+)\) UV_ASSET=\S+; UV_SHA=([0-9a-f]{64}) ;;", line)
        if m and key in m.group(1).split("|"):
            return m.group(2)
    return None


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "setup.sh is a POSIX shell script")
def pinned_py_sha() -> str | None:
    """The SHA-256 setup.sh pins for the private Python this computer would download."""
    system = subprocess.run(["uname", "-s"], capture_output=True, text=True).stdout.strip()
    machine = subprocess.run(["uname", "-m"], capture_output=True, text=True).stdout.strip()
    key = f"{system}-{machine}"
    arm = False
    for line in (ROOT / "setup.sh").read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s+([A-Za-z0-9_|-]+)$", line.replace(")", "", 1)) if line.rstrip().endswith(")") else None
        if m:
            arm = key in m.group(1).split("|")
            continue
        m = re.search(r"PY_SHA=([0-9a-f]{64}) ;;", line)
        if m and arm:
            return m.group(1)
    return None


@unittest.skipUnless(pinned_uv_sha(), "setup.sh pins no uv build for this computer")
class SetupShMessageTests(unittest.TestCase):
    def sandbox(self, *, version="3.9.6", usable=0, uv_mode="ok", py312_works=False, pip_mode="ok", curl_mode="ok"):
        """A PATH with only the tools setup.sh needs plus the fakes; returns (env, folders)."""
        root = Path(tempfile.mkdtemp(prefix="composer-sandbox-"))
        self.addCleanup(shutil.rmtree, root, True)
        bin_dir, log = root / "bin", root / "log"
        bin_dir.mkdir()
        log.mkdir()
        for tool in TOOLS:
            real = shutil.which(tool)
            if real:
                (bin_dir / tool).symlink_to(real)
        write_exe(bin_dir / "python3", FAKE_PY.format(version=version, ok=usable))
        py312 = write_exe(root / "py312", (FAKE_PY_WORKS if py312_works else FAKE_PY).format(version="3.12.9", ok=1))
        if py312_works:
            write_exe(bin_dir / "python3", FAKE_PY_WORKS.format(version=version, ok=usable))
            write_exe(root / "venv-python", FAKE_VENV_PYTHON)
            write_exe(root / "venv-composer", FAKE_VENV_COMPOSER)
        # the fake checks out as the pinned uv tarball, or as the pinned Python file when the name says cpython
        write_exe(bin_dir / "sha256sum", f"#!/bin/sh\ncase \"$1\" in *cpython*) echo {pinned_py_sha()}  \"$1\" ;; "
                  f"*) echo {pinned_uv_sha()}  \"$1\" ;; esac\n")
        # the "download": a tarball with one folder holding the fake uv, copied to wherever curl is told to write
        tgz = root / "uv.tar.gz"
        with tarfile.open(tgz, "w:gz") as tar:
            data = FAKE_UV.encode()
            info = tarfile.TarInfo("uv-fake/uv")
            info.size, info.mode = len(data), 0o755
            tar.addfile(info, io.BytesIO(data))
        write_exe(bin_dir / "curl", '#!/bin/sh\necho "$*" >> "$FAKE_LOG/curl-args"\n'
                  'n=$(cat "$FAKE_LOG/curl-count" 2>/dev/null || echo 0); n=$((n + 1)); echo $n > "$FAKE_LOG/curl-count"\n'
                  'if [ "$FAKE_CURL_MODE" = failonce ] && [ "$n" = 1 ]; then echo "curl: (28) fake timeout" >&2; exit 28; fi\n'
                  f'while [ $# -gt 0 ]; do [ "$1" = -o ] && out=$2; shift; done\ncp {tgz} "$out"\n')
        env = {"PATH": str(bin_dir), "FAKE_LOG": str(log), "FAKE_UV_MODE": uv_mode, "FAKE_PY312": str(py312),
               "COMPOSER_SETUP_RETRY_WAIT": "0", "COMPOSER_NO_TEST_CALL": "1", "COMPOSER_PYTHON_PATH_ONLY": "1", "LANG": "C",
               "FAKE_PIP_MODE": pip_mode, "FAKE_CURL_MODE": curl_mode, "FAKE_VENV_PYTHON": str(root / "venv-python"),
               "FAKE_VENV_COMPOSER": str(root / "venv-composer"), "FAKE_REAL_PYTHON": sys.executable, "FAKE_VENV_GW": "0"}
        return env, log

    def run_setup(self, home, env, *args):
        env = dict(env, HOME=str(home))
        # no controlling terminal: setup.sh must not wait on a question nobody can answer
        return subprocess.run([shutil.which("sh"), str(ROOT / "setup.sh"), *args], capture_output=True, text=True,
                              timeout=60, env=env, cwd=ROOT, start_new_session=True)

    def test_says_why_before_it_asks_to_download(self):
        with fake_home() as home:
            env, _ = self.sandbox()
            run = self.run_setup(home, env, "--home", str(home / "app"))
            self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
            why = f"Found python3 3.9.6 at {Path(env['PATH']) / 'python3'}; Composer needs 3.10 or newer."
            self.assertIn(why, run.stdout)
            self.assertLess(run.stdout.index(why), run.stdout.index("Setup can download uv"))
            self.assertLess(run.stdout.index("Step 2 of 7: looking for Python 3.10 or newer"), run.stdout.index(why))
            self.assertIn("no Python downloaded", run.stderr)
            self.assertFalse((home / "app").exists())  # nothing was written

    def test_a_python_without_venv_is_named_as_such(self):
        with fake_home() as home:
            env, _ = self.sandbox(version="3.11.4", usable=0)
            run = self.run_setup(home, env, "--home", str(home / "app"))
            self.assertIn("Found python3 3.11.4 at ", run.stdout)
            self.assertIn("but it has no venv module", run.stdout)
            self.assertNotIn("needs 3.10 or newer", run.stdout)

    def test_no_python_at_all(self):
        with fake_home() as home:
            env, _ = self.sandbox()
            (Path(env["PATH"]) / "python3").unlink()
            run = self.run_setup(home, env, "--home", str(home / "app"))
            self.assertIn("No python3 was found on this computer.", run.stdout)

    def test_download_steps_progress_timeout_and_no_quiet(self):
        with fake_home() as home:
            env, log = self.sandbox()
            run = self.run_setup(home, env, "--home", str(home / "app"), "--python-download")
            out = run.stdout
            for n, text in ((1, "checking this computer"), (2, "looking for Python"),
                            (3, "getting a private Python 3.12"), (4, "making a private environment with Python 3.12.9")):
                self.assertIn(f"Step {n} of 7: {text}", out)
            self.assertLess(out.index("Step 3 of 7"), out.index("Step 4 of 7"))
            self.assertIn("The download timeout is 300 seconds", out)
            self.assertIn("Downloading cpython-3.12.9-fake (17.1MiB)", run.stderr)  # uv's own progress is not hidden
            self.assertEqual((log / "uv-env").read_text().strip(), "timeout=300")
            self.assertNotIn("--quiet", (log / "uv-args").read_text())
            self.assertNotEqual(run.returncode, 0)  # the fake python refuses to make a venv: that is where this test stops
            self.assertIn("fake python: venv refused", run.stderr)

    def test_your_own_timeout_is_kept(self):
        with fake_home() as home:
            env, log = self.sandbox()
            self.run_setup(home, dict(env, UV_HTTP_TIMEOUT="45"), "--home", str(home / "app"), "--python-download")
            self.assertEqual((log / "uv-env").read_text().strip(), "timeout=45")

    def test_a_failed_download_shows_the_real_error_retries_and_names_the_ways_forward(self):
        with fake_home() as home:
            env, log = self.sandbox(uv_mode="fail")
            run = self.run_setup(home, env, "--home", str(home / "app"), "--python-download")
            self.assertEqual(run.returncode, 2)
            self.assertIn("operation timed out", run.stderr)  # uv's own error, passed through
            # the checked Python file was handed to uv as a folder: three tries, then it gives up
            self.assertEqual((log / "uv-count").read_text().strip(), "3")
            self.assertIn("attempt 2 of 3", run.stdout)
            self.assertIn("could not download Python 3.12.9", run.stderr)
            self.assertIn("UV_HTTP_TIMEOUT=600 sh setup.sh", run.stderr)
            self.assertIn("python.org", run.stderr)
            self.assertNotIn("Step 4 of 7", run.stdout)
            self.assertFalse((home / "app").exists())  # what it made was removed again

    def test_a_second_try_that_works_carries_on(self):
        with fake_home() as home:
            env, log = self.sandbox(uv_mode="failonce")
            run = self.run_setup(home, env, "--home", str(home / "app"), "--python-download")
            self.assertEqual((log / "uv-count").read_text().strip(), "2")
            self.assertIn("fake timeout, first try", run.stderr)
            self.assertIn("Step 4 of 7: making a private environment with Python 3.12.9", run.stdout)

    def test_a_usable_python_means_no_download_and_the_step_says_so(self):
        with fake_home() as home:
            env, log = self.sandbox(version="3.11.4", usable=1)
            run = self.run_setup(home, env, "--home", str(home / "app"))
            self.assertIn("Step 3 of 7: using Python 3.11.4 (nothing to download)", run.stdout)
            self.assertIn("Step 4 of 7: making a private environment with Python 3.11.4", run.stdout)
            self.assertNotIn("Found python3", run.stdout)
            self.assertFalse((log / "uv-args").exists())

    def test_whole_install_path_steps_pip_progress_and_handover(self):
        with fake_home() as home:
            env, log = self.sandbox(py312_works=True)
            run = self.run_setup(home, env, "--home", str(home / "app"), "--python-download", "--yes")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            for n in range(1, 8):
                self.assertIn(f"Step {n} of 7:", run.stdout)
            self.assertIn("Step 5 of 7: installing Composer", run.stdout)
            self.assertIn("Step 7 of 7: Composer's own setup", run.stdout)
            self.assertIn("Processing a fake source folder", run.stderr)  # pip's own output is not hidden
            pip = (log / "pip").read_text()
            self.assertIn("timeout=120 retries=5", pip)
            self.assertNotIn("--quiet", pip)
            self.assertIn("FAKE COMPOSER setup --home", run.stdout)
            self.assertTrue((home / "app" / "app" / "current").is_symlink())

    def test_pip_failure_shows_the_error_names_the_fix_and_cleans_up(self):
        with fake_home() as home:
            env, _ = self.sandbox(py312_works=True, pip_mode="fail")
            run = self.run_setup(home, env, "--home", str(home / "app"), "--python-download", "--yes")
            self.assertEqual(run.returncode, 2)
            self.assertIn("fake pip: could not reach the index", run.stderr)
            self.assertIn("PIP_DEFAULT_TIMEOUT=300", run.stderr)
            self.assertFalse((home / "app").exists())

    def test_the_uv_download_is_tried_again_and_a_timeout_you_set_reaches_pip(self):
        with fake_home() as home:
            env, log = self.sandbox(py312_works=True, curl_mode="failonce")
            run = self.run_setup(home, dict(env, PIP_DEFAULT_TIMEOUT="7"), "--home", str(home / "app"),
                                 "--python-download", "--yes")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("github.com did not work for uv 0.5.29", run.stdout)  # the one-line note when it switches
            self.assertIn("downloading uv 0.5.29 from GitHub download API", run.stdout)
            self.assertIn("fake timeout", run.stderr)
            self.assertIn("--speed-time 30 ", (log / "curl-args").read_text())  # a stalled download ends too
            self.assertIn("timeout=7 ", (log / "pip").read_text())

    def test_ctrl_c_during_a_download_cleans_up_in_a_shell_that_skips_the_exit_trap(self):
        dash = shutil.which("dash")
        if not dash:
            self.skipTest("no dash here")
        import signal
        import time
        with fake_home() as home:
            env, log = self.sandbox(uv_mode="hang")
            # a uv that hangs in the Python download until it is interrupted
            hang = FAKE_UV.replace('case "$FAKE_UV_MODE" in', 'case "$FAKE_UV_MODE" in\n      hang) touch "$FAKE_LOG/hanging"; sleep 30 ;;')
            with tarfile.open(Path(env["PATH"]).parent / "uv.tar.gz", "w:gz") as tar:
                data = hang.encode()
                info = tarfile.TarInfo("uv-fake/uv")
                info.size, info.mode = len(data), 0o755
                tar.addfile(info, io.BytesIO(data))
            proc = subprocess.Popen([dash, str(ROOT / "setup.sh"), "--home", str(home / "app"), "--python-download"],
                                    env=dict(env, HOME=str(home)), cwd=ROOT, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True, start_new_session=True)
            for _ in range(100):
                if (log / "hanging").exists():
                    break
                time.sleep(0.1)
            os.killpg(proc.pid, signal.SIGINT)
            proc.communicate(timeout=30)
            self.assertNotEqual(proc.returncode, 0)
            self.assertFalse((home / "app").exists())  # what it had made was removed again



    def test_a_venv_with_group_writable_template_files_is_fixed_not_refused(self):
        """python.org's Python copies group-writable template files (Activate.ps1) into every venv; the trust contract
        refuses those, and setup.sh used to refuse its own venv. It now takes the group-write bit off right after."""
        with fake_home() as home:
            env, _ = self.sandbox(py312_works=True)
            run = self.run_setup(home, dict(env, FAKE_VENV_GW="1"), "--home", str(home / "app"), "--python-download", "--yes")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            mode = (home / "app" / "app" / VERSION_FOLDER(home) / "venv" / "bin" / "Activate.ps1").stat().st_mode & 0o777
            self.assertEqual(mode & 0o022, 0, oct(mode))

    def test_the_group_writable_venv_test_has_teeth_without_the_fix(self):
        """The same run with the chmod lines taken out of a copy of setup.sh fails: the test above can tell."""
        with fake_home() as home:
            env, _ = self.sandbox(py312_works=True)
            copy = Path(tempfile.mkdtemp(prefix="composer-nofix-"))
            self.addCleanup(shutil.rmtree, copy, True)
            text = (ROOT / "setup.sh").read_text(encoding="utf-8").replace('chmod -R go-w -- "$H/app/$VERSION"', "true")
            (copy / "setup.sh").write_text(text, encoding="utf-8")
            for name in ("pyproject.toml", "composer", "README.md", "LICENSE"):
                (copy / name).symlink_to(ROOT / name)
            run = subprocess.run([shutil.which("sh"), str(copy / "setup.sh"), "--home", str(home / "app"), "--python-download", "--yes"],
                                 capture_output=True, text=True, timeout=60, env=dict(env, HOME=str(home), FAKE_VENV_GW="1"),
                                 cwd=ROOT, start_new_session=True)
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("can be written by other accounts", run.stdout + run.stderr)

    def _half_made(self, home, *, marker):
        base = home / "app"
        folder = base / "app" / VERSION_FOLDER(home)
        (folder / "venv" / "bin").mkdir(parents=True)
        leftover = folder / "venv" / "bin" / "Activate.ps1"
        leftover.write_text("x")
        leftover.chmod(0o664)
        (base / ".composer-home").write_text("lensmith-composer home v1\n")
        if marker:
            (base / "app" / f".making-{VERSION_FOLDER(home)}").write_text("")
        return base, folder

    def test_a_half_made_version_folder_that_setup_marked_is_removed_and_the_rerun_succeeds(self):
        with fake_home() as home:
            env, _ = self.sandbox(py312_works=True)
            base, folder = self._half_made(home, marker=True)
            run = self.run_setup(home, env, "--home", str(base), "--python-download", "--yes")
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("an earlier setup stopped in the middle of making", run.stdout)
            self.assertTrue((base / "app" / "current").is_symlink())
            self.assertFalse((base / "app" / f".making-{VERSION_FOLDER(home)}").exists())  # the marker went with the folder

    def test_a_version_folder_setup_did_not_mark_is_left_alone(self):
        with fake_home() as home:
            env, _ = self.sandbox(py312_works=True)
            base, folder = self._half_made(home, marker=False)
            folder.joinpath("venv", "bin", "Activate.ps1").chmod(0o600)  # so only the missing marker is in question
            run = self.run_setup(home, env, "--home", str(base), "--python-download", "--yes")
            self.assertEqual(run.returncode, 2)
            self.assertIn("does not start", run.stdout + run.stderr)
            self.assertTrue(folder.exists())  # not ours to remove: nothing marked it

    def test_a_failure_in_the_middle_leaves_nothing_even_when_the_venv_came_out_group_writable(self):
        with fake_home() as home:
            env, _ = self.sandbox(py312_works=True, pip_mode="fail")
            run = self.run_setup(home, dict(env, FAKE_VENV_GW="1"), "--home", str(home / "app"), "--python-download", "--yes")
            self.assertEqual(run.returncode, 2)
            self.assertFalse((home / "app").exists())  # the cleanup could check and remove its own folder

    def test_every_python_the_installer_starts_leaves_the_current_folder_out_of_its_import_path(self):
        """A planted venv.py or pip/ in the folder the command is run from must not run: python -I, every time."""
        text = (ROOT / "setup.sh").read_text(encoding="utf-8")
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#") or "-m composer" in line:
                continue  # the preflight runs Composer from its own folder (the kit, or your checkout) on purpose
            for m in re.finditer(r'"\$(?:p|PY|zp|VENV/bin/python|bd/env/bin/python)"\s+(-\S+)', line):
                self.assertTrue(m.group(1) == "-I", f"setup.sh line {n} starts Python without -I: {line.strip()}")

    def test_a_local_claim_seal_source_keeps_its_real_file_name_so_pip_can_read_it(self):
        text = (ROOT / "setup.sh").read_text(encoding="utf-8")
        self.assertIn('mv -f -- "$GOT" "$kd/$A_S" && CS_SRC=$kd/$A_S', text)  # the copy's .yours name is not a valid sdist name

    def test_the_wget_fallback_tries_once_because_the_retry_loop_is_the_scripts_own(self):
        text = (ROOT / "setup.sh").read_text(encoding="utf-8")
        calls = [line for line in text.splitlines() if line.strip().startswith("wget ")]
        self.assertTrue(calls)
        for line in calls:
            self.assertIn("--tries=1", line)


if __name__ == "__main__":
    unittest.main()
