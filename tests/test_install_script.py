"""install.sh and the fetch library it shares with setup.sh: what a person sees, with a fake curl and nothing real
downloaded. (The real downloads, with faults, are tests/install_faults.)"""
import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from helpers import ROOT

sys.path.insert(0, str(ROOT / "scripts" / "install"))
import build_install  # noqa: E402

SETUP = (ROOT / "setup.sh").read_text(encoding="utf-8")
LIB = build_install.fetchlib(SETUP)
FAKE_CURL = """#!/bin/sh
# fake curl: the table FAKE_TABLE has lines "url|code|file"; a hit copies the file (code 200) or fails like --fail does
url=""; out=""
while [ $# -gt 0 ]; do case "$1" in -o) out=$2; shift 2 ;; -w|-H|--connect-timeout|--speed-limit|--speed-time|--proto|--proto-redir|--tlsv1.2) 
  case "$1" in --tlsv1.2) shift ;; *) shift 2 ;; esac ;; -*) shift ;; *) url=$1; shift ;; esac; done
echo "$url" >> "$FAKE_LOG"
line=$(grep -F "$url|" "$FAKE_TABLE" | head -n 1)
code=$(printf '%s' "$line" | cut -d'|' -f2); file=$(printf '%s' "$line" | cut -d'|' -f3)
[ -n "$code" ] || code=404
if [ "$code" = 200 ]; then cp "$file" "$out"; printf 200; exit 0; fi
echo "curl: (22) The requested URL returned error: $code" >&2; printf '%s' "$code"; exit 22
"""


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class FetchLibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="composer-lib-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        for tool in "sh awk sed grep cut head cat cp mv rm sleep date printf id uname tr mkdir env sha256sum".split():
            real = shutil.which(tool)
            if real:
                (bin_dir / tool).symlink_to(real)
        (bin_dir / "curl").write_text(FAKE_CURL)
        (bin_dir / "curl").chmod(0o755)
        self.good = self.tmp / "good.bin"
        self.good.write_bytes(b"the real file")
        self.bad = self.tmp / "bad.bin"
        self.bad.write_bytes(b"a tampered file")
        (self.tmp / "lib.sh").write_text(LIB)
        self.env = {"PATH": str(bin_dir), "FAKE_LOG": str(self.tmp / "log"), "FAKE_TABLE": str(self.tmp / "table"),
                    "COMPOSER_SETUP_RETRY_WAIT": "0", "LANG": "C"}

    def table(self, *rows):
        (self.tmp / "table").write_text("\n".join(rows) + "\n")

    def run_lib(self, body, **extra):
        script = f'set -eu\nSTALL_S=5; CONNECT_S=5\n. {self.tmp / "lib.sh"}\n{body}\n'
        return subprocess.run([shutil.which("sh"), "-c", script], capture_output=True, text=True, timeout=30,
                              env={**self.env, **extra}, cwd=self.tmp)

    def test_a_504_moves_to_the_next_source_with_one_line(self):
        self.table(f"https://a.test/f|504|", f"https://b.test/f|200|{self.good}")
        run = self.run_lib(f'fetch_pinned "the file" {self.tmp}/out {sha(b"the real file")} "first|https://a.test/f" "second|https://b.test/f"')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("! first did not work for the file (HTTP 504); trying the next source", run.stdout)
        self.assertEqual((self.tmp / "out").read_bytes(), b"the real file")

    def test_a_file_that_does_not_match_the_pin_is_thrown_away_and_the_next_source_is_used(self):
        self.table(f"https://a.test/f|200|{self.bad}", f"https://b.test/f|200|{self.good}")
        run = self.run_lib(f'fetch_pinned "the file" {self.tmp}/out {sha(b"the real file")} "first|https://a.test/f" "second|https://b.test/f"')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("first sent a file that does not match its pinned SHA-256, so it was thrown away", run.stdout)
        self.assertEqual((self.tmp / "out").read_bytes(), b"the real file")
        self.assertFalse((self.tmp / "out.part").exists())

    def test_only_a_bad_file_means_failure_and_nothing_is_kept(self):
        self.table(f"https://a.test/f|200|{self.bad}")
        run = self.run_lib(f'fetch_pinned "the file" {self.tmp}/out {sha(b"the real file")} "first|https://a.test/f"')
        self.assertNotEqual(run.returncode, 0)
        self.assertFalse((self.tmp / "out").exists())
        self.assertFalse((self.tmp / "out.part").exists())

    def test_a_source_that_failed_with_a_server_error_is_skipped_for_the_next_file(self):
        self.table("https://a.test/1|503|", f"https://b.test/1|200|{self.good}", f"https://b.test/2|200|{self.good}",
                   f"https://a.test/2|200|{self.good}")
        run = self.run_lib(f'''fetch_pinned one {self.tmp}/o1 {sha(b"the real file")} "first|https://a.test/1" "second|https://b.test/1"
fetch_pinned two {self.tmp}/o2 {sha(b"the real file")} "first|https://a.test/2" "second|https://b.test/2"''')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        log = (self.tmp / "log").read_text().split()
        self.assertNotIn("https://a.test/2", log)  # one outage, one note, no second wait

    def test_a_404_does_not_mark_the_source_dead(self):
        self.table(f"https://b.test/1|200|{self.good}", f"https://a.test/2|200|{self.good}")
        run = self.run_lib(f'''fetch_pinned one {self.tmp}/o1 {sha(b"the real file")} "first|https://a.test/1" "second|https://b.test/1"
fetch_pinned two {self.tmp}/o2 {sha(b"the real file")} "first|https://a.test/2" "second|https://b.test/2"''')
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
        self.assertIn("https://a.test/2", (self.tmp / "log").read_text().split())

    def test_skip_sources_is_honoured(self):
        self.table(f"https://a.test/f|200|{self.good}", f"https://b.test/f|200|{self.good}")
        run = self.run_lib(f'fetch_pinned f {self.tmp}/out {sha(b"the real file")} "first|https://a.test/f" "second|https://b.test/f"',
                           COMPOSER_SKIP_SOURCES="first")
        self.assertIn("(skipping first, as COMPOSER_SKIP_SOURCES asks)", run.stdout)
        self.assertEqual((self.tmp / "log").read_text().split(), ["https://b.test/f"])

    def test_your_own_file_is_used_only_when_it_matches(self):
        mine = self.tmp / "mine.bin"
        mine.write_bytes(b"the real file")
        dest = self.tmp / "dest0"
        dest.mkdir()
        run = self.run_lib(f'have_local MYFILE name.bin {sha(b"the real file")} "" {dest} && echo "GOT=$GOT"', MYFILE=str(mine))
        self.assertIn("GOT=", run.stdout)
        wrong = self.run_lib(f'have_local MYFILE name.bin {sha(b"something else")} "" {dest} || echo refused', MYFILE=str(mine))
        self.assertIn("does not match the pinned SHA-256, so it is not used", wrong.stdout)
        self.assertIn("refused", wrong.stdout)

    def test_your_own_file_is_copied_first_and_the_copy_is_what_is_used(self):
        mine = self.tmp / "mine.bin"
        mine.write_bytes(b"the real file")
        dest = self.tmp / "dest"
        dest.mkdir()
        run = self.run_lib(f'have_local MYFILE name.bin {sha(b"the real file")} "" {dest} && echo "GOT=$GOT"', MYFILE=str(mine))
        self.assertIn(f"GOT={dest}/name.bin.yours", run.stdout)
        mine.write_bytes(b"swapped after the check")  # the original changing now cannot change what is used
        self.assertEqual((dest / "name.bin.yours").read_bytes(), b"the real file")
        nodest = self.run_lib(f'have_local MYFILE name.bin {sha(b"the real file")} "" || echo refused', MYFILE=str(mine))
        self.assertIn("refused", nodest.stdout)  # no folder of ours to copy into: not used

    def test_an_empty_pin_is_never_a_match(self):
        self.table(f"https://a.test/f|200|{self.good}")
        run = self.run_lib(f'fetch_pinned f {self.tmp}/out "" "first|https://a.test/f" || echo refused')
        self.assertIn("refused", run.stdout)
        self.assertFalse((self.tmp / "out").exists())

    def test_a_failure_prints_what_failed_and_the_next_step_and_no_stack_trace(self):
        run = self.run_lib('fail "something broke" "do this next"')
        self.assertEqual(run.returncode, 2)
        self.assertIn("What failed: something broke", run.stderr)
        self.assertIn("Next:        do this next", run.stderr)
        self.assertNotIn("Traceback", run.stderr)

    def test_the_library_is_in_setup_sh_once_and_install_sh_gets_that_copy(self):
        self.assertEqual(SETUP.count("# BEGIN fetchlib"), 1)
        self.assertEqual(SETUP.count("# END fetchlib"), 1)


@unittest.skipUnless(os.name == "posix" and shutil.which("sh"), "POSIX shell")
class BuiltInstallScriptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="composer-built-"))
        facts = build_install.project_facts()
        rel = cls.tmp / "rel"
        rel.mkdir()
        v = facts["version"]
        for name in (f"lensmith_composer-{v}.tar.gz", f"lensmith_composer-{v}-py3-none-any.whl",
                     f"certifi-{facts['certifi']}-py3-none-any.whl", f"setuptools-{facts['setuptools']}-py3-none-any.whl",
                     "claim_seal-0.2.0-py3-none-any.whl",
                     f"claim-seal-{facts['cs_commit']}.tar.gz"):
            (rel / name).write_bytes(name.encode())
        cls.pins = build_install.build(rel, cls.tmp / "out", install_url="https://example.test/install.sh",
                                       mirror_url="https://mirror.test/m", release_base="https://rel.test/v", check_source=False)
        cls.script = cls.tmp / "out" / "install.sh"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def sh(self, *args, env=None):
        return subprocess.run([shutil.which("sh"), str(self.script), *args], capture_output=True, text=True, timeout=30,
                              env=env or {"PATH": os.environ["PATH"], "HOME": str(self.tmp)}, stdin=subprocess.DEVNULL)

    def test_it_is_valid_shell_and_carries_the_setup_sh_library_byte_for_byte(self):
        text = self.script.read_text(encoding="utf-8")
        self.assertIn(LIB, text)
        subprocess.run(["sh", "-n", str(self.script)], check=True)

    def test_every_pin_is_a_sha256_or_a_plain_value(self):
        text = self.script.read_text(encoding="utf-8")
        for key, val in self.pins.items():
            self.assertIn(f"PIN_{key}={val}\n", text)
            if key.endswith("_SHA") and val:
                self.assertRegex(val, r"^[0-9a-f]{64}$")
        self.assertRegex(self.pins["KIT_SHA"], r"^[0-9a-f]{64}$")

    def test_show_pins_prints_them_and_stops(self):
        run = self.sh("--show-pins")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn(self.pins["KIT_SHA"], run.stdout)
        self.assertIn(self.pins["COMPOSER_WHEEL_SHA"], run.stdout)

    def test_an_unknown_flag_is_a_clear_stop_not_a_trace(self):
        run = self.sh("--nonsense")
        self.assertEqual(run.returncode, 2)
        self.assertIn("What failed: unknown option --nonsense", run.stderr)
        self.assertIn("Next:", run.stderr)
        self.assertNotIn("Traceback", run.stderr)

    def test_help_prints_the_header(self):
        run = self.sh("--help")
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("Lensmith Composer: one command", run.stdout)
        self.assertIn("--no-open", run.stdout)

    def test_the_url_and_the_mirror_are_variables(self):
        text = self.script.read_text(encoding="utf-8")
        self.assertIn("https://example.test/install.sh", text)
        self.assertIn("COMPOSER_MIRROR_URL:-$PIN_MIRROR_URL", text)
        self.assertIn("COMPOSER_RELEASE_BASE:-$PIN_RELEASE_BASE", text)

    def test_nothing_in_it_runs_rm_on_a_glob_or_substitution(self):
        for n, line in enumerate((self.script).read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\brm\b.*(\*|\$\()", line) and not line.lstrip().startswith("#"):
                self.fail(f"line {n}: {line}")


if __name__ == "__main__":
    unittest.main()
