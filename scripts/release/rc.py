"""Build release candidates from chosen commits, the way the release workflow builds a release.

  python scripts/release/rc.py --version 0.2.0 --rc 1=<commit> --rc 2=<commit> --out rc-0.2.0

For a test before a release (for example, installing rc1 and then updating to rc2 on a laptop), so the test uses
real release files and not a working copy. For each --rc N=<commit>, in order:

  checkout  a fresh, shallow clone of that one commit (as actions/checkout makes for a tag), never the working tree
  version   the release would be tagged v<version>rc<N>; the commit's pyproject.toml must say <version>rc<N>.
            --stamp-version writes that version into pyproject.toml and composer/__init__.py of the clone instead
            (and says so), because the workflow itself would refuse a tag that does not match.
  test      the workflow's test job: `pip install .` into a new, empty environment, then
            scripts/release/test_results.py, recorded as test-results.json. A failure stops here, as it stops the
            release, unless --keep-going (the failures are then written into the manifest).
  build     the workflow's build job: the hash-locked release tools into a second new environment, then
            scripts/release/build.py --tag v<version>rc<N> (sdist, wheel, installed and run, SBOM, SHA256SUMS).
  sums      the publish job's SHA256SUMS over every release file (`sha256sum -- *` format).

Not made here, because they need what only the workflow has: the claim-sealed release note (the release
environment's model key), the container image and its attestations (the registry and GitHub's signing), and the
GitHub Release. The manifest says so.

The output folder gets every release file of every candidate side by side, one SHA256SUMS that covers all of them
(so `shasum -a 256 -c SHA256SUMS` checks both, and `composer update --from-file` finds the sum next to the file),
rc<N>/ with that candidate's own SHA256SUMS, test-results.json and build log, and rc-manifest.json.

Use the same Python as the workflow (3.13) for a faithful build; another version works and is recorded. It needs
git and the internet (pip fetches claim-seal at its pinned commit and the release tools by hash).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import venv
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOW_PYTHON = (3, 13)
VERSION_RE = re.compile(r"\d+\.\d+\.\d+")
NOT_BUILT = ["release note (claim-sealed; needs the release environment's model key)",
             "container image, its SBOM and attestations (need the registry and GitHub's signing)",
             "GitHub artifact attestations for the files (need GitHub's signing)"]


class RCError(RuntimeError):
    """A candidate could not be built; the message says which step and why."""


def parse_rc(text: str) -> tuple[int, str]:
    m = re.fullmatch(r"(\d{1,2})=([0-9A-Za-z._/-]+)", text or "")
    if not m or int(m.group(1)) < 1:
        raise argparse.ArgumentTypeError(f"--rc takes N=<commit>, such as 1=main or 2=a1b2c3d; got {text!r}")
    return int(m.group(1)), m.group(2)


def rc_version(version: str, n: int) -> str:
    return f"{version}rc{n}"


def sums_text(folder: Path, names: list[str] | None = None) -> str:
    """`sha256sum -- *` output for the given files (default: every file in the folder but SHA256SUMS)."""
    if names is None:
        names = sorted(p.name for p in folder.iterdir() if p.is_file() and p.name != "SHA256SUMS")
    lines = [f"{hashlib.sha256((folder / n).read_bytes()).hexdigest()}  {n}" for n in sorted(names)]
    return "\n".join(lines) + "\n"


def failing_tests(log: str) -> list[str]:
    """The ids of failed or errored tests, from unittest's own report in the log."""
    return sorted(set(m.group(2) + " (" + m.group(3) + ")"
                      for m in re.finditer(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", log, re.M)))


def stamp_version(src: Path, version: str) -> list[str]:
    """Write `version` into pyproject.toml and composer/__init__.py; returns the files changed."""
    changed = []
    for rel, pattern, repl in (("pyproject.toml", r'^version\s*=\s*"[^"]+"', f'version = "{version}"'),
                               ("composer/__init__.py", r'^__version__\s*=\s*"[^"]+"', f'__version__ = "{version}"')):
        path = src / rel
        text = path.read_text(encoding="utf-8")
        new, count = re.subn(pattern, repl, text, count=1, flags=re.M)
        if count != 1:
            raise RCError(f"version: no version line in {rel}")
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(rel)
    return changed


def read_version(src: Path) -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', (src / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    if not m:
        raise RCError("version: no version in pyproject.toml")
    return m.group(1)


class Runner:
    """Runs commands, echoing each one and keeping a log per candidate."""

    def __init__(self, log_path: Path):
        self.log = log_path.open("a", encoding="utf-8")

    def __call__(self, cmd: list[str], *, cwd: Path, env: dict | None = None, step: str) -> int:
        line = "+ " + " ".join(cmd)
        print(line, flush=True)
        self.log.write(f"\n## {step}\n{line}\n")
        self.log.flush()
        proc = subprocess.run(cmd, cwd=str(cwd), env=env, stdout=self.log, stderr=subprocess.STDOUT)
        self.log.write(f"(exit {proc.returncode})\n")
        self.log.flush()
        return proc.returncode

    def close(self):
        self.log.close()


def venv_python(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def new_venv(path: Path) -> Path:
    venv.EnvBuilder(with_pip=True, clear=True).create(path)
    return venv_python(path)


def checkout(commit: str, dest: Path, run: Runner) -> str:
    """A shallow clone of one commit, as actions/checkout makes for a tag. Returns the full commit id."""
    sha = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", f"{commit}^{{commit}}"],
                         capture_output=True, text=True)
    if sha.returncode != 0:
        raise RCError(f"checkout: {commit!r} is not a commit in {ROOT}")
    full = sha.stdout.strip()
    dest.mkdir(parents=True)
    for cmd in (["git", "init", "--quiet"], ["git", "fetch", "--quiet", "--depth", "1", str(ROOT), full],
                ["git", "checkout", "--quiet", "--detach", "FETCH_HEAD"]):
        if run(cmd, cwd=dest, step="checkout") != 0:
            raise RCError(f"checkout: `{' '.join(cmd)}` failed (see the build log)")
    return full


def build_one(n: int, commit: str, version: str, out: Path, work: Path, *, stamp: bool, keep_going: bool) -> dict:
    v = rc_version(version, n)
    tag = f"v{v}"
    rc_dir = out / f"rc{n}"
    rc_dir.mkdir()
    run = Runner(rc_dir / "build.log")
    rec = {"rc": n, "tag": tag, "version": v, "commit_asked": commit}
    def prepare(job: str) -> Path:
        """A fresh clone for one job (the workflow's jobs each check out on their own), stamped if asked."""
        src = work / f"rc{n}" / f"src-{job}"
        rec["commit"] = checkout(commit, src, run)
        found = read_version(src)
        rec["version_in_commit"] = found
        if found != v:
            if not stamp:
                raise RCError(f"version: the commit says {found}; the workflow refuses tag {tag} for it "
                              f"(build.py: tag must be v + pyproject version). Commit version {v}, or pass "
                              "--stamp-version for a test-only build.")
            rec["stamped"] = stamp_version(src, v)
            print(f"rc{n} ({job}): stamped version {v} into {', '.join(rec['stamped'])} (the commit says {found})")
        else:
            rec["stamped"] = []
        return src

    try:
        src = prepare("test")
        env = dict(os.environ, GITHUB_SHA=rec["commit"], GITHUB_REF_NAME=tag, PIP_DISABLE_PIP_VERSION_CHECK="1")

        # test job
        py_t = new_venv(work / f"rc{n}" / "test-venv")
        if run([str(py_t), "-m", "pip", "install", "--quiet", "."], cwd=src, env=env, step="test: install") != 0:
            raise RCError("test: `pip install .` failed (see the build log)")
        results = rc_dir / "test-results.json"
        code = run([str(py_t), "scripts/release/test_results.py", "--out", str(results)], cwd=src, env=env,
                   step="test: offline suite")
        tests = json.loads(results.read_text(encoding="utf-8")) if results.is_file() else {}
        rec["tests"] = {k: tests.get(k) for k in ("python", "ran", "passed", "failed", "errors", "skipped")}
        rec["tests"]["failing"] = failing_tests((rc_dir / "build.log").read_text(encoding="utf-8"))
        if code != 0:
            rec["tests"]["release_would_stop"] = True
            if not keep_going:
                raise RCError(f"test: the offline suite failed ({tests.get('failed')} failed, {tests.get('errors')} "
                              "errors); the release workflow stops here. See test-results.json, or pass --keep-going "
                              "to build the files anyway for a test that is not a release.")
            print(f"rc{n}: the offline suite failed; building anyway (--keep-going). Not releasable as it is.")

        # build job, from its own fresh clone
        src = prepare("build")
        py_b = new_venv(work / f"rc{n}" / "build-venv")
        if run([str(py_b), "-m", "pip", "install", "--quiet", "--require-hashes", "-r",
                "scripts/release/release-tools.txt"], cwd=src, env=env, step="build: release tools") != 0:
            raise RCError("build: the hash-locked release tools did not install (see the build log)")
        dist = work / f"rc{n}" / "dist"
        if run([str(py_b), "scripts/release/build.py", "--out", str(dist), "--tag", tag], cwd=src, env=env,
               step="build: build.py") != 0:
            raise RCError("build: scripts/release/build.py failed (see the build log)")
        check = (dist / "SHA256SUMS").read_text(encoding="utf-8")
        if check != sums_text(dist):
            raise RCError("build: build.py's SHA256SUMS does not match the files it made")

        # publish job's SHA256SUMS: every release file (here: the build job's files; no note, no image)
        files = sorted(p.name for p in dist.iterdir() if p.is_file() and p.name != "SHA256SUMS")
        for name in files:
            shutil.copy2(dist / name, out / name)
            shutil.copy2(dist / name, rc_dir / name)
        (rc_dir / "SHA256SUMS").write_text(sums_text(rc_dir, files), encoding="utf-8")
        rec["files"] = {name: hashlib.sha256((dist / name).read_bytes()).hexdigest() for name in files}
        rec["not_built"] = NOT_BUILT
        rec["status"] = "built" if not rec["tests"].get("release_would_stop") else "built, tests failed"
        return rec
    except RCError as exc:
        rec["status"] = "failed"
        rec["error"] = str(exc)
        raise
    finally:
        run.close()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", required=True, help="the release these are candidates for, such as 0.2.0")
    ap.add_argument("--rc", action="append", type=parse_rc, required=True, metavar="N=COMMIT",
                    help="candidate number and the commit to build it from; repeat for each candidate")
    ap.add_argument("--out", required=True, help="a new or empty folder for the candidates")
    ap.add_argument("--stamp-version", action="store_true",
                    help="write <version>rc<N> into the clone when the commit says another version (test builds)")
    ap.add_argument("--keep-going", action="store_true",
                    help="build the files even when the offline suite fails (recorded; not releasable)")
    args = ap.parse_args(argv)

    if not VERSION_RE.fullmatch(args.version):
        ap.error("--version is a release version such as 0.2.0, without rc")
    numbers = [n for n, _ in args.rc]
    if len(set(numbers)) != len(numbers):
        ap.error("each --rc number may appear once")
    if sys.version_info[:2] != WORKFLOW_PYTHON:
        print(f"note: this is Python {platform.python_version()}; the release workflow builds with "
              f"{'.'.join(map(str, WORKFLOW_PYTHON))}. The build is recorded as made with this one.", flush=True)
    if shutil.which("git") is None:
        raise SystemExit("rc: git is needed")
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"rc: refused, {out} is not empty")
    out.mkdir(parents=True, exist_ok=True)

    manifest = {"schema": "composer-rc/v1", "version": args.version,
                "made_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "python": platform.python_version(), "system": f"{platform.system()} {platform.machine()}",
                "workflow_python": ".".join(map(str, WORKFLOW_PYTHON)), "candidates": []}
    code = 0
    with tempfile.TemporaryDirectory(prefix="composer-rc-") as tmp:
        for n, commit in sorted(args.rc):
            print(f"== rc{n}: {rc_version(args.version, n)} from {commit}", flush=True)
            try:
                rec = build_one(n, commit, args.version, out, Path(tmp), stamp=args.stamp_version,
                                keep_going=args.keep_going)
            except RCError as exc:
                print(f"rc{n}: FAILED: {exc}", file=sys.stderr, flush=True)
                manifest["candidates"].append({"rc": n, "commit_asked": commit, "status": "failed",
                                               "error": str(exc)})
                code = 1
                break
            manifest["candidates"].append(rec)
            print(f"rc{n}: {rec['status']}: " + ", ".join(rec["files"]), flush=True)
    if code == 0:
        (out / "SHA256SUMS").write_text(sums_text(out), encoding="utf-8")
        manifest["sha256sums"] = (out / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    (out / "rc-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"rc: {'done' if code == 0 else 'stopped'}; see {out / 'rc-manifest.json'}")
    return code


if __name__ == "__main__":
    sys.exit(main())
