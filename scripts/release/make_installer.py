"""Make install.sh for a release, and the dependency files it may fetch from the release, from the build job's files.

  python scripts/release/make_installer.py --dist DIR --out NEWDIR [--extras-dir DIR]

DIR (--dist) holds the build job's files: lensmith_composer-X.tar.gz and lensmith_composer-X-py3-none-any.whl.
Run it in the environment that has the hash-locked release tools (scripts/release/release-tools.txt).

Each dependency file is checked against a hash written in the repository before it is used:
  certifi's wheel and setuptools' wheel   the SHA-256 in scripts/install/pinned-extras.json (downloaded from PyPI with
                                          pip, or taken from --extras-dir when you already have them)
  claim-seal's source archive             the SHA-256 pyproject.toml pins with the commit (downloaded from GitHub, or
                                          taken from --extras-dir)
  claim-seal's wheel                      built here from that archive with the hash-locked setuptools
Then scripts/install/build_install.py writes install.sh, install.sh.sha256 and install-pins.json from all six files.
--out receives every file the release should carry for the installer; nothing is uploaded or published here.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "install"))
import build_install as bi  # noqa: E402

PINNED = ROOT / "scripts" / "install" / "pinned-extras.json"


class InstallerError(SystemExit):
    pass


def need_sha(path: Path, expected: str, what: str) -> None:
    got = bi.sha256(path)
    if got != expected:
        raise InstallerError(f"make_installer: {what} {path.name} has SHA-256 {got}, expected {expected}")


def check_listed_sums(dist: Path, names) -> None:
    """The build job's own SHA256SUMS must agree with the files as they arrived (a corrupted transfer stops here)."""
    sums = dist / "SHA256SUMS"
    if not sums.is_file():
        raise InstallerError("make_installer: dist has no SHA256SUMS")
    listed = {}
    for line in sums.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            listed[parts[1].lstrip("*")] = parts[0]
    for name in names:
        if listed.get(name) != bi.sha256(dist / name):
            raise InstallerError(f"make_installer: {name} does not match the build job's SHA256SUMS")


def pip_download(spec: str, dest: Path) -> None:
    subprocess.run([sys.executable, "-m", "pip", "download", "--disable-pip-version-check", "--no-deps",
                    "--only-binary=:all:", "--dest", str(dest), spec], check=True)


def fetch(url: str, dest: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as r, dest.open("wb") as f:  # nosec: https only, hash checked after
        shutil.copyfileobj(r, f)


def build_claim_seal_wheel(archive: Path, work: Path) -> Path:
    src = work / "claim-seal-src"
    src.mkdir()
    with tarfile.open(archive) as tar:
        tar.extractall(src, filter="data")
    tops = [p for p in src.iterdir() if p.is_dir()]
    if len(tops) != 1:
        raise InstallerError("make_installer: the claim-seal archive does not hold one top folder")
    out = work / "cs-wheel"
    out.mkdir()
    subprocess.run([sys.executable, "-m", "build", "--no-isolation", "--wheel", "--outdir", str(out), str(tops[0])], check=True)
    wheels = sorted(out.glob("claim_seal-*-py3-none-any.whl"))
    if len(wheels) != 1:
        raise InstallerError(f"make_installer: expected one claim-seal wheel, found {[w.name for w in wheels]}")
    return wheels[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dist", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--extras-dir", type=Path, help="use these dependency files instead of downloading them (each still hash-checked)")
    a = ap.parse_args(argv)
    if a.out.exists() and any(a.out.iterdir()):
        raise InstallerError(f"make_installer: refused, {a.out} is not empty")
    facts = bi.project_facts()
    pinned = json.loads(PINNED.read_text(encoding="utf-8"))
    version = facts["version"]
    dist_names = (f"lensmith_composer-{version}.tar.gz", f"lensmith_composer-{version}-py3-none-any.whl")
    for name in dist_names:
        if not (a.dist / name).is_file():
            raise InstallerError(f"make_installer: {a.dist / name} is missing")
    check_listed_sums(a.dist, dist_names)
    certifi = pinned["certifi"]
    setuptools = pinned["setuptools"]
    if certifi["version"] != facts["certifi"] or setuptools["version"] != facts["setuptools"]:
        raise InstallerError("make_installer: pinned-extras.json names other versions than pyproject.toml pins")
    cs_name = f"claim-seal-{facts['cs_commit']}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        stage = work / "stage"
        stage.mkdir()
        for p in a.dist.iterdir():
            if p.name.startswith("lensmith_composer-") and (p.suffix == ".whl" or p.name.endswith(".tar.gz")):
                shutil.copy2(p, stage / p.name)
        if a.extras_dir:
            for name in (certifi["file"], setuptools["file"], cs_name):
                shutil.copy2(a.extras_dir / name, stage / name)
        else:
            dl = work / "dl"
            dl.mkdir()
            pip_download(f"certifi=={certifi['version']}", dl)
            pip_download(f"setuptools=={setuptools['version']}", dl)
            fetch(f"https://github.com/lensmith-ai/claim-seal/archive/{facts['cs_commit']}.tar.gz", dl / cs_name)
            for name in (certifi["file"], setuptools["file"], cs_name):
                shutil.copy2(dl / name, stage / name)
        need_sha(stage / certifi["file"], certifi["sha256"], "certifi's wheel")
        need_sha(stage / setuptools["file"], setuptools["sha256"], "setuptools' wheel")
        need_sha(stage / cs_name, facts["cs_src_sha"], "claim-seal's source archive")
        cs_wheel = build_claim_seal_wheel(stage / cs_name, work)
        shutil.copy2(cs_wheel, stage / cs_wheel.name)
        built = work / "built"
        bi.build(stage, built, install_url="https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh",
                 mirror_url="https://lensmith.ai/composer/mirror",
                 release_base=f"https://github.com/lensmith-ai/composer/releases/download/v{version}")
        a.out.mkdir(parents=True, exist_ok=True)
        for p in sorted(built.iterdir()):
            shutil.copy2(p, a.out / p.name)
        for name in (certifi["file"], setuptools["file"], cs_name, cs_wheel.name):
            shutil.copy2(stage / name, a.out / name)
    print("make_installer: " + ", ".join(sorted(p.name for p in a.out.iterdir())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
