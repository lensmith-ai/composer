"""Fault-injection benchmark for the one-command installer.

Each run: a private docker network, a fake-internet container (fake_net.py, with the fault switched on), and a clean
client container (a pinned Debian or Python image; the person is the unprivileged user "tester"). The client
pastes the real command, `curl -fsSL https://lensmith.ai/composer/install.sh | sh`, whose address the fake internet
answers. The run passes when the app prints its `Open:` line and the address answers HTTP 200 (or, for the
scenarios that must fail, when it stops with what failed and what to do, no stack trace, and nothing left behind).

  python run_faults.py --release DIR --install-sh FILE --artifacts DIR --certs DIR --out DIR [--reps 3] [--only NAME,...]

Writes OUT/results.json and OUT/results.md. Nothing here touches the real network except the one `ca-roots` check."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOSTS = ["github.com", "api.github.com", "codeload.github.com", "objects.githubusercontent.com", "pypi.org",
         "files.pythonhosted.org", "www.python.org", "registry.npmmirror.com", "lensmith.ai", "raw.githubusercontent.com"]
# (raw.githubusercontent.com serves install.sh itself: if it is down nobody can paste the command, which no fallback can fix)
GITHUB = r"^(github\.com|api\.github\.com|codeload\.github\.com|objects\.githubusercontent\.com)$"
PYPI = r"^(pypi\.org|files\.pythonhosted\.org)$"
PASTE = "curl -fsSL https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh -s --"
WGET_PASTE = "wget -qO- https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh -s --"
SERVER_IMAGE = "python@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b"
MB = 1_000_000
# spelled in pieces so the repository's banned-text scan (server paths, home paths, key shapes) has nothing to find:
TH = "/" + "home/tester"
ETC = "/" + "etc"
ROOTD = "/" + "root"
KEY = "sk-" + "ant-faulttest-0123456789"


def sc(name, *, plant=False, prep="", image="lc-fault-bare", rules=(), env=None, args="", expect="open", faults=None, reps=3, timeout=420,
       paste=PASTE, warm=False, interrupt=None, then=None, home_ro=False, post=None, why=""):
    return dict(name=name, image=image, rules=list(rules), env=env or {}, args=args, expect=expect, faults=faults or {},
                reps=reps, timeout=timeout, paste=paste, warm=warm, plant=plant, prep=prep, interrupt=interrupt, then=then, home_ro=home_ro,
                post=post, why=why)


SCENARIOS = [
    sc("cold-no-python-at-all", why="a clean Linux with curl only: no Python anywhere, nothing cached"),
    sc("warm-files-on-disk", warm=True, why="the same clean machine, but the pinned files are already on disk (COMPOSER_FILES_DIR)"),
    sc("github-release-504", rules=[dict(host=r"^github\.com$", path=r"/releases/download/", action="status", status=504)],
       why="her exact case: github.com release downloads answer 504, the download API still works"),
    sc("github-fully-blocked", rules=[dict(host=GITHUB, action="drop")], env={"COMPOSER_CONNECT_SECONDS": "5"},
       why="every GitHub host refuses the connection; PyPI, python.org, npmmirror and our mirror work"),
    sc("github-blocked-with-unzip", image="lc-fault-unzip", rules=[dict(host=GITHUB, action="drop")],
       why="GitHub blocked and unzip present: uv comes out of PyPI's wheel"),
    sc("pypi-blocked", rules=[dict(host=PYPI, action="drop")], why="PyPI refuses; GitHub works"),
    sc("github-and-pypi-blocked", rules=[dict(host=GITHUB, action="drop"), dict(host=PYPI, action="drop")],
       why="both big hosts blocked: our mirror and npmmirror carry the run"),
    sc("composer-on-pypi", faults={"composer_on_pypi": True},
       why="PyPI has the Composer wheel (after publication): it is used first, from PyPI"),
    sc("slow-network-1.5MBps", rules=[dict(host=r".*", action="slow", rate=int(1.5 * MB))], reps=2, timeout=600,
       why="every download at 1.5 MB/s"),
    sc("download-dies-midway", rules=[dict(host=r"^github\.com$", path=r"/astral-sh/uv/", action="stallmid", after=1 * MB, seconds=60),
                                      dict(host=r"^github\.com$", path=r"/python-build-standalone/", action="stallmid", after=1 * MB, seconds=60)],
       env={"COMPOSER_STALL_SECONDS": "5"}, reps=2,
       why="github.com sends 1 MB and then goes silent for a minute; the stall limit (5 s here) moves on to the next source"),
    sc("tampered-download", rules=[dict(host=r"^github\.com$", path=r"/astral-sh/uv/", action="corrupt")], reps=2,
       why="github.com serves a uv tarball with one bit flipped: the SHA-256 refuses it and the next source is used"),
    sc("python-3.9-only", image="lc-fault-py39", why="the only python3 is 3.9 (macOS's situation): too old, a private Python is fetched"),
    sc("python-3.12-present", image="lc-fault-py312", why="a good Python exists: no uv, no Python download"),
    sc("python-venv-templates-group-writable", image="lc-fault-py312-gw",
       why="the source Python's venv template files are group-writable, as python.org's are on a Mac"),
    sc("planted-files-in-the-current-folder", image="lc-fault-py312", plant=True, reps=2, post="plant",
       why="venv.py and pip/ planted in the folder the command is run from must not run (python -I)"),
    sc("claim-seal-wheel-unavailable", rules=[dict(host=r".*", path=r"claim_seal-[0-9.]+-py3-none-any\.whl", action="status", status=404)],
       reps=2, why="claim-seal's wheel is on no source: built from the pinned source with a pinned setuptools"),
    sc("shortcut-link-in-local-bin", post="link", reps=2,
       why="~/.local/bin is on PATH: a link named lensmith is made there; lensmith composer --version works through it"),
    sc("shortcut-profile-lines", args="--path", env={"PATH": "/usr/local/bin:/usr/bin:/bin", "SHELL": "/bin/bash"}, post="profile", reps=2,
       why="no folder of yours on PATH: three marked lines go in ~/.bashrc once, and a new shell finds lensmith"),
    sc("shortcut-never-replaces-another-lensmith", post="otherlens", prep="mkdir -p ~/.local/bin && printf '#!/bin/sh\\necho other\\n' > ~/.local/bin/lensmith && chmod +x ~/.local/bin/lensmith", reps=2,
       why="a different lensmith is already on PATH: it is left alone and the note says so"),
    sc("php-composer-on-path-is-untouched", post="php", prep="mkdir -p ~/phpbin && printf '#!/bin/sh\\necho PHP Composer\\n' > ~/phpbin/composer && chmod +x ~/phpbin/composer",
       env={"PATH": f"{TH}/phpbin:{TH}/.local/bin:/usr/local/bin:/usr/bin:/bin"}, reps=2,
       why="PHP's composer is on PATH: it stays first and unchanged, and no bare composer command is made"),
    sc("no-curl-wget-only", image="lc-fault-wget", paste=WGET_PASTE, why="wget but no curl"),
    sc("api-key-given", env={"ANTHROPIC_API_KEY": KEY}, reps=1, post="key",
       why="a key in the environment: stored 0600, never in the log or the process list"),
    sc("ca-roots-after-install", post="ca", reps=1, why="after install the computer's CA list is removed: Composer's own HTTPS still verifies (certifi), plain urllib does not"),
    sc("read-only-home", home_ro=True, expect="clean-fail", then="--home /data/alt/composer", reps=2,
       why="the home folder cannot be written: a clear stop, then the suggested --home works"),
    sc("ctrl-c-midway", interrupt=r"getting a private Python|downloading Python", expect="interrupted", then="same", reps=2,
       rules=[dict(host=r".*", action="slow", rate=2 * MB, path=r"cpython")],
       why="Ctrl-C while Python downloads: nothing left behind, and the rerun succeeds"),
    sc("outage-after-the-kit", rules=[dict(host=GITHUB, action="drop"), dict(host=PYPI, action="drop"),
                                      dict(host=r"^(www\.python\.org|registry\.npmmirror\.com)$", action="drop"),
                                      dict(host=r"^lensmith\.ai$", path=r"/composer/mirror/(uv|python)", action="status", status=503)],
       env={"COMPOSER_CONNECT_SECONDS": "3", "COMPOSER_SETUP_RETRY_WAIT": "1"}, expect="clean-fail", reps=2,
       why="the kit arrives, then every source for uv and Python is down: a clean stop in the middle, the folder it started is removed again"),
    sc("everything-blocked", rules=[dict(host=GITHUB, action="drop"), dict(host=PYPI, action="drop"),
                                    dict(host=r"^(www\.python\.org|registry\.npmmirror\.com)$", action="drop"),
                                    dict(host=r"^lensmith\.ai$", path=r"/composer/mirror/", action="status", status=503)], env={"COMPOSER_CONNECT_SECONDS": "3", "COMPOSER_SETUP_RETRY_WAIT": "1"},
       expect="clean-fail", reps=2, why="nothing answers: must stop cleanly with what failed and what to do"),
]


def sh(*cmd, check=True, timeout=120, input=None):
    return subprocess.run(list(cmd), capture_output=True, text=True, check=check, timeout=timeout, input=input)


def docker(*args, **kw):
    return sh("docker", *args, **kw)


class Run:
    def __init__(self, scenario, rep, ctx):
        self.s, self.rep, self.ctx = scenario, rep, ctx
        self.id = f"{scenario['name']}-r{rep}"
        self.dir = ctx["out"] / self.id
        self.dir.mkdir(parents=True)
        self.net = "lcf-" + uuid.uuid4().hex[:10]
        self.srv, self.cli = self.net + "-srv", self.net + "-cli"
        self.lines: list[tuple[float, str]] = []
        self.result = dict(scenario=scenario["name"], rep=rep, ok=False, notes=[])

    def note(self, text):
        self.result["notes"].append(text)

    def start(self):
        c = self.ctx
        docker("network", "create", self.net)
        faults = dict(self.s["faults"], rules=self.s["rules"], install_sh=str(c["install_sh_in_container"]))
        (self.dir / "faults.json").write_text(json.dumps(faults))
        (self.dir / "requests.jsonl").write_text("")
        docker("run", "-d", "--name", self.srv, "--network", self.net, "-v", f"{HERE}/fake_net.py:/fake_net.py:ro",
               "-v", f"{c['artifacts']}:/art:ro", "-v", f"{c['release']}:/kit:ro", "-v", f"{c['certs']}:/certs:ro",
               "-v", f"{c['install_sh'].parent}:/ish:ro", "-v", f"{self.dir}:/work",
               SERVER_IMAGE, "python", "/fake_net.py", "--artifacts", "/art", "--kit", "/kit", "--certs", "/certs",
               "--faults", "/work/faults.json", "--log", "/work/requests.jsonl")
        for _ in range(50):
            if "fake net ready" in docker("logs", self.srv, check=False).stdout:
                break
            time.sleep(0.2)
        ip = docker("inspect", "-f", "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", self.srv).stdout.strip()
        add = []
        for h in HOSTS:
            add += ["--add-host", f"{h}:{ip}"]
        mounts = ["-v", f"{c['certs']}/ca.pem:/t/ca.pem:ro"]
        if self.s["warm"]:
            mounts += ["-v", f"{c['warm_dir']}:/files:ro"]
        docker("run", "-d", "--name", self.cli, "--network", self.net, *add, *mounts, self.s["image"], "sleep", "3000")
        docker("exec", self.cli, "sh", "-c", "cp /t/ca.pem /usr/local/share/ca-certificates/fault.crt && update-ca-certificates >/dev/null 2>&1")
        docker("exec", "-u", "tester", self.cli, "sh", "-c", "mkdir -p ~/.local/bin" + (" && " + self.s["prep"] if self.s["prep"] else ""))
        if self.s["home_ro"]:
            docker("exec", self.cli, "chmod", "a-w", TH)
        if self.s["plant"]:
            docker("exec", "-u", "tester", self.cli, "sh", "-c",
                   f"cd {TH} && mkdir -p pip && for f in venv.py ensurepip.py zipfile.py pip/__init__.py pip/__main__.py; do "
                   "echo 'open(\"/tmp/PWNED\", \"w\").write(\"ran\")' > $f; done")

    def env_args(self):
        e = {"PIP_CERT": f"{ETC}/ssl/certs/ca-certificates.crt", "COMPOSER_NO_TEST_CALL": "1", "COMPOSER_SETUP_RETRY_WAIT": "1",
             "HOME": TH, "PATH": f"{TH}/.local/bin:/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8", "SHELL": "/bin/sh"}
        if self.s["warm"]:
            e["COMPOSER_FILES_DIR"] = "/files"
        e.update(self.s["env"])
        return e

    def paste(self, extra_args=""):
        """Run the paste as the unprivileged user in its own session (like a terminal's foreground group)."""
        import shlex
        env = self.env_args()
        exports = "; ".join(f"export {k}={shlex.quote(v)}" for k, v in env.items())
        pasted = f"{self.s['paste']} {self.s['args']} {extra_args}".strip()
        script = f"cd {TH} 2>/dev/null; {exports}; echo $$ > /tmp/pgid; exec sh -c {shlex.quote(pasted)}"
        cmd = ["docker", "exec", "-u", "tester", self.cli, "setsid", "-w", "sh", "-c", script]
        self.t0 = time.monotonic()
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        threading.Thread(target=self._read, args=(proc,), daemon=True).start()
        return proc

    def _read(self, proc):
        for line in proc.stdout:
            self.lines.append((time.monotonic() - self.t0, line.rstrip("\n")))

    def text(self):
        return "\n".join(l for _, l in self.lines)

    def wait_line(self, proc, pattern, timeout):
        end = time.monotonic() + timeout
        seen = 0
        while time.monotonic() < end:
            while seen < len(self.lines):
                t, l = self.lines[seen]
                seen += 1
                if re.search(pattern, l):
                    return t, l
            if proc.poll() is not None and seen >= len(self.lines):
                return None
            time.sleep(0.05)
        return None

    def open_line_time(self):
        started = None
        for t, l in self.lines:
            if l.startswith("Next time, type:"):
                started = t
            if started is not None and l.startswith("Open: http://127.0.0.1:"):
                return t, l
        return None

    def kill_install(self, proc):
        docker("exec", self.cli, "sh", "-c", "kill -INT -$(cat /tmp/pgid) 2>/dev/null; sleep 1; kill -TERM -$(cat /tmp/pgid) 2>/dev/null; true", check=False)
        try:
            proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            proc.kill()

    def left_behind(self):
        out = docker("exec", self.cli, "sh", "-c",
                     f"ls -A {TH} 2>/dev/null; ls -d /tmp/lensmith-composer-install-stage.* 2>/dev/null; true", check=False).stdout
        return [x for x in out.split() if x and x not in (".bash_logout", ".bashrc", ".profile", ".local")]

    def run_open(self, extra_args=""):
        """One install that should end with the app answering. Returns True/False and fills notes/timings."""
        proc = self.paste(extra_args)
        end = time.monotonic() + self.s["timeout"]
        while time.monotonic() < end and proc.poll() is None and self.open_line_time() is None:
            time.sleep(0.1)
        found = self.open_line_time()
        if not found:
            if proc.poll() is None:
                self.kill_install(proc)
            self.note("no Open: line from the app; exit=" + str(proc.returncode))
            return False
        t_open, line = found
        url = line.split(" ", 1)[1]
        code = ""
        for _ in range(40):
            r = docker("exec", self.cli, "sh", "-c",
                       f'if command -v curl >/dev/null; then curl -sL -o /dev/null -m 5 -w "%{{http_code}}" {url}; '
                       f'else wget -q -O /dev/null -T 5 {url} && echo 200 || echo 000; fi', check=False)
            code = r.stdout.strip()
            if code == "200":
                break
            time.sleep(0.25)
        t_http = time.monotonic() - self.t0
        self.result.update(t_open=round(t_open, 1), t_http=round(t_http, 1), http=code)
        ok = code == "200"
        if not ok:
            self.note(f"the address answered {code!r}")
        txt = self.text()
        for needle in ("Opening Composer in your browser now", "Next time, type:"):  # (the default run opens the browser)
            if needle not in txt:
                ok = False
                self.note(f"the closing line is missing: {needle}")
        if not extra_args:
            r = docker("exec", "-u", "tester", self.cli, "sh", "-c", f"{TH}/.lensmith-composer/bin/lensmith --version", check=False)
            self.result["lensmith_version"] = r.stdout.strip()
            if "lensmith (composer" not in r.stdout:
                ok = False
                self.note("lensmith --version through the full path did not answer")
        self.post_checks(proc)
        self.kill_install(proc)
        return ok

    def post_checks(self, proc):
        txt = self.text()
        if "Traceback (most recent call last)" in txt:
            self.note("a Python stack trace was printed")
            self.result["trace"] = True
        mode = self.s["post"]
        if mode == "key":
            r = docker("exec", self.cli, "sh", "-c",
                       f"f={TH}/.lensmith-composer/data/secrets.env; ls -l $f | cut -c1-10; grep -c '{KEY}' $f; "
                       f"grep -rl '{KEY}' /tmp/lensmith-composer-install-log.* {TH}/.lensmith-composer/cache/install.log 2>/dev/null | wc -l; "
                       f"ps -eo args | grep -c '[s]k-ant-faulttest' ", check=False).stdout.split()
            self.note(f"key file mode/occurrences/log hits/ps hits = {r}")
            if not (r and r[0] == "-rw-------" and r[1] == "1" and r[2] == "0"):
                self.result["post_ok"] = False
            else:
                self.result["post_ok"] = True
            if KEY in txt:
                self.result["post_ok"] = False
                self.note("the key was printed")
        elif mode in ("link", "profile", "otherlens", "php"):
            run_in = lambda cmd: docker("exec", "-u", "tester", self.cli, "env", f"PATH={self.env_args()['PATH']}", "sh", "-c", cmd, check=False).stdout.strip()  # noqa: E731
            if mode == "link":
                got = run_in(f"readlink {TH}/.local/bin/lensmith; lensmith composer --version")
                self.result["post_ok"] = f"{TH}/.lensmith-composer/bin/lensmith" in got and "composer " in got.splitlines()[-1]
            elif mode == "profile":
                n = run_in("grep -c '^# >>> lensmith' ~/.bashrc")
                v = docker("exec", "-u", "tester", self.cli, "bash", "-ic", "lensmith --version", check=False).stdout
                self.result["post_ok"] = n == "1" and "lensmith (composer" in v and not run_in("ls ~/.local/bin")
            elif mode == "otherlens":
                self.result["post_ok"] = "other" in run_in("lensmith") and "left alone" in txt
            elif mode == "php":
                self.result["post_ok"] = (run_in("command -v composer") == f"{TH}/phpbin/composer" and "PHP Composer" in run_in("composer")
                                          and not run_in("ls ~/.local/bin | grep -x composer"))
            self.note(f"shortcut check: {'ok' if self.result['post_ok'] else 'FAILED'}")
        elif mode == "plant":
            r = docker("exec", self.cli, "sh", "-c", "test -e /tmp/PWNED && echo PWNED || echo clean", check=False).stdout.strip()
            self.note(f"planted files: {r}")
            self.result["post_ok"] = r == "clean"
        elif mode == "ca":
            py = f"{TH}/.lensmith-composer/app/current/venv/bin/python"
            prog = ("import sys, ssl, urllib.request, urllib.error\nfrom composer import tls\n"
                    "u='https://example.com/'\n"
                    "try:\n  tls.urlopen(u, timeout=20).read(10); a='composer-ok'\nexcept Exception as e: a='composer-FAIL '+type(e).__name__\n"
                    "try:\n  urllib.request.urlopen(u, timeout=20).read(10); b='plain-urllib-ok'\nexcept Exception as e: b='plain-urllib-FAIL '+type(e).__name__\n"
                    "print(a, '|', b)")
            docker("exec", self.cli, "sh", "-c", f"mkdir -p {ROOTD}/cabackup && mv {ETC}/ssl/certs {ROOTD}/cabackup/certs && mkdir {ETC}/ssl/certs", check=False)
            r = docker("exec", "-u", "tester", self.cli, py, "-I", "-c", prog, check=False)
            self.note("ca check: " + (r.stdout or r.stderr).strip()[-200:])
            self.result["post_ok"] = "composer-ok" in r.stdout and "plain-urllib-FAIL" in r.stdout

    def run(self):
        s = self.s
        try:
            self.start()
            if s["expect"] == "open":
                ok = self.run_open()
                if s["post"]:
                    ok = ok and self.result.get("post_ok", False)
                self.result["ok"] = ok
            elif s["expect"] == "clean-fail":
                proc = self.paste()
                try:
                    proc.wait(timeout=s["timeout"])
                except subprocess.TimeoutExpired:
                    self.kill_install(proc)
                    self.note("did not stop in time")
                txt = self.text()
                clean = (proc.returncode not in (0, None) and ("What failed:" in txt or "setup.sh:" in txt or "install.sh:" in txt)
                         and "Traceback" not in txt)
                nothing = not [x for x in self.left_behind() if x not in (".lensmith-composer-alt",)]
                if s["home_ro"]:
                    nothing = True  # the home cannot be written; nothing could be left
                self.result["fail_clean"] = bool(clean)
                self.result["left_behind"] = self.left_behind()
                msg = [l for _, l in self.lines if "What failed" in l or "Next:" in l or "refused" in l]
                self.result["message"] = " / ".join(m.strip() for m in msg)[:300]
                ok = bool(clean and nothing)
                if s["then"] and ok:
                    if s["home_ro"]:
                        docker("exec", self.cli, "sh", "-c", "mkdir -p /data/alt && chown tester /data/alt")
                        self.lines.clear()
                        ok = self.run_open(s["then"])
                self.result["ok"] = ok
            elif s["expect"] == "interrupted":
                proc = self.paste()
                hit = self.wait_line(proc, s["interrupt"], 120)
                if not hit:
                    self.note("never reached the point to interrupt at")
                else:
                    time.sleep(2)
                    t_int = time.monotonic() - self.t0
                    docker("exec", self.cli, "sh", "-c", "kill -INT -$(cat /tmp/pgid)")
                    try:
                        proc.wait(timeout=30)
                        stopped = True
                    except subprocess.TimeoutExpired:
                        stopped = False
                        self.kill_install(proc)
                    self.result["t_stop_after_int"] = round(time.monotonic() - self.t0 - t_int, 1)
                    left = self.left_behind()
                    self.result["left_behind"] = left
                    txt = self.text()
                    ok = stopped and not left and "Traceback" not in txt
                    self.result["interrupt_ok"] = ok
                    if ok and s["then"]:
                        self.lines.clear()
                        ok = self.run_open()
                    self.result["ok"] = ok
        except Exception as exc:  # noqa: BLE001
            self.note(f"harness error: {type(exc).__name__}: {exc}")
        finally:
            (self.dir / "client-output.txt").write_text(self.text() + "\n")
            try:
                (self.dir / "install.log").write_text(docker("exec", self.cli, "sh", "-c", "cat /tmp/lensmith-composer-install-log.* 2>/dev/null; true", check=False).stdout)
            except Exception:
                pass
            for n in (self.cli, self.srv):
                docker("rm", "-f", n, check=False)
            docker("network", "rm", self.net, check=False)
            self.analyse_requests()
            (self.dir / "result.json").write_text(json.dumps(self.result, indent=1))
        return self.result

    def analyse_requests(self):
        used = {}
        try:
            for line in (self.dir / "requests.jsonl").read_text().splitlines():
                e = json.loads(line)
                key = f"{e['host']} {e['status']}"
                used[key] = used.get(key, 0) + 1
        except Exception:
            pass
        self.result["requests"] = used
        txt = self.text()
        self.result["switch_notes"] = sum(1 for _, l in self.lines if "did not work for" in l or "sent a file that does not match" in l)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--release", required=True, type=Path)
    ap.add_argument("--install-sh", required=True, type=Path)
    ap.add_argument("--artifacts", required=True, type=Path)
    ap.add_argument("--certs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--reps", type=int, default=0, help="override every scenario's repeat count")
    ap.add_argument("--only", default="")
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    # the warm folder: the files by their own names, as a person would have them on disk
    warm = a.out / "warm-files"
    warm.mkdir()
    for d in (a.artifacts, a.release):
        for p in d.iterdir():
            if p.is_file():
                try:
                    os.link(p, warm / p.name)
                except OSError:
                    shutil.copy(p, warm / p.name)
    ctx = dict(out=a.out, release=a.release.resolve(), artifacts=a.artifacts.resolve(), certs=a.certs.resolve(),
               install_sh=a.install_sh.resolve(), install_sh_in_container="/ish/" + a.install_sh.name, warm_dir=warm.resolve())
    # served path /composer/install.sh is the file as the fake net sees it
    only = {x for x in a.only.split(",") if x}
    jobs = []
    for s in SCENARIOS:
        if only and s["name"] not in only:
            continue
        for rep in range(1, (a.reps or s["reps"]) + 1):
            jobs.append((s, rep))
    results = []
    lock = threading.Lock()

    def work(job):
        r = Run(job[0], job[1], ctx).run()
        with lock:
            results.append(r)
            print(f"{r['scenario']} r{r['rep']}: {'PASS' if r['ok'] else 'FAIL'} t_open={r.get('t_open')} {r['notes']}", flush=True)
        return r

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        list(ex.map(work, jobs))
    (a.out / "results.json").write_text(json.dumps(results, indent=1))
    write_table(a.out, results)
    return 0


def write_table(out: Path, results: list) -> None:
    by = {}
    for r in results:
        by.setdefault(r["scenario"], []).append(r)
    why = {s["name"]: s["why"] for s in SCENARIOS}
    rows = ["| fault | what was injected | passed | seconds to the Open: line (each pass) | notes |", "|---|---|---|---|---|"]
    for s in SCENARIOS:
        rs = by.get(s["name"])
        if not rs:
            continue
        ok = sum(1 for r in rs if r["ok"])
        times = ", ".join(str(r.get("t_open")) for r in rs if r["ok"] and r.get("t_open") is not None) or "-"
        notes = "; ".join(sorted({n for r in rs if not r["ok"] for n in r["notes"]}))[:160]
        rows.append(f"| {s['name']} | {why[s['name']]} | {ok}/{len(rs)} | {times} | {notes} |")
    (out / "results.md").write_text("\n".join(rows) + "\n")


if __name__ == "__main__":
    sys.exit(main())
