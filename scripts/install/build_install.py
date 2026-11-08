"""Make install.sh for one release: the template with this release's pinned SHA-256 values and the fetch library
taken from setup.sh (so there is one copy of it).

  python scripts/install/build_install.py --release DIR --out DIR \\
      [--install-url URL] [--mirror-url URL] [--release-base URL] [--kit-pypi-url URL] [--claim-seal-pypi FILE]

DIR (--release) holds the release's files, by their usual names:
  lensmith_composer-X.tar.gz            the source release; the "kit" install.sh downloads (it holds setup.sh)
  lensmith_composer-X-py3-none-any.whl  Composer's wheel
  certifi-V-py3-none-any.whl            the CA list wheel (the version pyproject.toml pins)
  setuptools-S-py3-none-any.whl         the build tool pyproject.toml pins (only used to build claim-seal from source)
  claim_seal-V-py3-none-any.whl         claim-seal's wheel, built from the commit pyproject.toml pins
  claim-seal-<commit>.tar.gz            that commit's archive, the same bytes GitHub serves (pinned by pyproject.toml)
Writes install.sh, install.sh.sha256 and install-pins.json to --out. Nothing is uploaded or published.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PLAIN = re.compile(r"^[A-Za-z0-9._:/+%@-]*$")  # what a pins value may hold (setup.sh reads only these)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def fetchlib(setup_text: str) -> str:
    m = re.search(r"^# BEGIN fetchlib.*?^# END fetchlib\n", setup_text, re.S | re.M)
    if not m:
        raise SystemExit("build_install: setup.sh has no fetchlib region")
    return m.group(0)


def project_facts() -> dict:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    version = re.search(r'^version = "([^"]+)"', text, re.M).group(1)
    certifi = re.search(r'"certifi==([^"]+)"', text).group(1)
    cs = re.search(r'"claim-seal @ https://github\.com/lensmith-ai/claim-seal/archive/([0-9a-f]{40})\.tar\.gz#sha256=([0-9a-f]{64})"', text)
    st = re.search(r'requires = \["setuptools==([^"]+)"\]', text).group(1)
    return {"version": version, "certifi": certifi, "setuptools": st, "cs_commit": cs.group(1), "cs_src_sha": cs.group(2)}


def one(release: Path, pattern: str) -> Path:
    found = sorted(release.glob(pattern))
    if len(found) != 1:
        raise SystemExit(f"build_install: expected one file matching {pattern} in {release}, found {[p.name for p in found]}")
    return found[0]


def build(release: Path, out: Path, *, install_url: str, mirror_url: str, release_base: str, kit_pypi_url: str = "",
          claim_seal_pypi: Path | None = None, check_source: bool = True) -> dict:
    facts = project_facts()
    v = facts["version"]
    kit = one(release, f"lensmith_composer-{v}.tar.gz")
    wheel = one(release, f"lensmith_composer-{v}-py3-none-any.whl")
    certifi = one(release, f"certifi-{facts['certifi']}-py3-none-any.whl")
    setuptools = one(release, f"setuptools-{facts['setuptools']}-py3-none-any.whl")
    cs_wheel = one(release, "claim_seal-*-py3-none-any.whl")
    cs_ver = cs_wheel.name.split("-")[1]
    cs_src = one(release, f"claim-seal-{facts['cs_commit']}.tar.gz")
    if check_source and sha256(cs_src) != facts["cs_src_sha"]:
        raise SystemExit("build_install: the claim-seal archive does not match the SHA-256 pyproject.toml pins")
    pins = {
        "VERSION": v, "MIRROR_URL": mirror_url.rstrip("/"), "RELEASE_BASE": release_base.rstrip("/"),
        "KIT": kit.name, "KIT_SHA": sha256(kit), "KIT_PYPI_URL": kit_pypi_url,
        "COMPOSER_WHEEL": wheel.name, "COMPOSER_WHEEL_SHA": sha256(wheel),
        "CERTIFI_VERSION": facts["certifi"], "CERTIFI_WHEEL": certifi.name, "CERTIFI_WHEEL_SHA": sha256(certifi),
        "CLAIMSEAL_VERSION": cs_ver, "CLAIMSEAL_WHEEL": cs_wheel.name, "CLAIMSEAL_WHEEL_SHA": sha256(cs_wheel),
        "CLAIMSEAL_PYPI_WHEEL": claim_seal_pypi.name if claim_seal_pypi else "",
        "CLAIMSEAL_PYPI_SHA": sha256(claim_seal_pypi) if claim_seal_pypi else "",
        "SETUPTOOLS_VERSION": facts["setuptools"], "SETUPTOOLS_WHEEL": setuptools.name, "SETUPTOOLS_WHEEL_SHA": sha256(setuptools),
        "CLAIMSEAL_SRC": cs_src.name, "CLAIMSEAL_SRC_SHA": facts["cs_src_sha"], "CLAIMSEAL_COMMIT": facts["cs_commit"],
    }
    for k, val in pins.items():
        if not PLAIN.match(val):
            raise SystemExit(f"build_install: {k} holds characters a pins file may not carry: {val!r}")
    block = "\n".join(f"PIN_{k}={val}" for k, val in pins.items())
    template = (HERE / "install.sh.in").read_text(encoding="utf-8")
    text = (template.replace("@@PINS@@", block).replace("@@FETCHLIB@@", fetchlib((ROOT / "setup.sh").read_text(encoding="utf-8")))
            .replace("@@INSTALL_URL@@", install_url))
    out.mkdir(parents=True, exist_ok=True)
    script = out / "install.sh"
    script.write_text(text, encoding="utf-8")
    script.chmod(0o755)
    subprocess.run(["sh", "-n", str(script)], check=True)
    (out / "install.sh.sha256").write_text(f"{sha256(script)}  install.sh\n", encoding="utf-8")
    (out / "install-pins.json").write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return pins


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--release", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--install-url", default="https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh")
    ap.add_argument("--mirror-url", default="https://lensmith.ai/composer/mirror")
    ap.add_argument("--release-base", default="")
    ap.add_argument("--kit-pypi-url", default="")
    ap.add_argument("--claim-seal-pypi", type=Path)
    a = ap.parse_args(argv)
    facts = project_facts()
    base = a.release_base or f"https://github.com/lensmith-ai/composer/releases/download/v{facts['version']}"
    pins = build(a.release, a.out, install_url=a.install_url, mirror_url=a.mirror_url, release_base=base,
                 kit_pypi_url=a.kit_pypi_url, claim_seal_pypi=a.claim_seal_pypi)
    print(f"wrote {a.out / 'install.sh'} for Composer {pins['VERSION']}; sha256 {sha256(a.out / 'install.sh')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
