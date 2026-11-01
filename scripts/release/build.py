"""Build a release: the sdist and the wheel, a CycloneDX SBOM of what the wheel installs, and SHA256SUMS.

  python scripts/release/build.py --out dist [--tag v0.2.0]

Run it in an environment that has the hash-locked release tools (scripts/release/release-tools.txt):
  python -m pip install --require-hashes -r scripts/release/release-tools.txt

Steps, each one fatal if it fails:
  1. --tag, when given, must equal "v" + the version in pyproject.toml.
  2. The sdist and wheel are built with the pinned setuptools (no build isolation, so nothing unpinned is fetched).
  3. The wheel is installed into a new, empty virtual environment (pip fetches claim-seal at its pinned commit
     and checks its SHA-256) and run once: `composer --version` and `composer demo --fast`.
  4. The SBOM is made from THAT environment (cyclonedx-py), so it lists what was actually installed, not what a
     lock file says. The optional narration parts (scripts/release/optional-components.json) are added with
     scope "excluded": not in this artifact, listed so their licences are on record.
  5. SHA256SUMS covers every file in --out.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPTIONAL = Path(__file__).resolve().parent / "optional-components.json"


def project_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    if not m:
        raise SystemExit("build: no version in pyproject.toml")
    return m.group(1)


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    print("+ " + " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, **kw)


def venv_python(env_dir: Path) -> Path:
    return env_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def add_optional(sbom_path: Path) -> int:
    sbom = json.loads(sbom_path.read_text(encoding="utf-8"))
    extra = json.loads(OPTIONAL.read_text(encoding="utf-8"))["components"]
    components = sbom.setdefault("components", [])
    for c in extra:
        row = {k: v for k, v in c.items() if k != "delivery"}
        row["bom-ref"] = f"optional:{c['name']}@{c['version']}"
        row["scope"] = "excluded"
        row["properties"] = [{"name": "lensmith:delivery", "value": c["delivery"]}]
        components.append(row)
    sbom_path.write_text(json.dumps(sbom, indent=2) + "\n", encoding="utf-8")
    return len(extra)


def sha256sums(out: Path) -> Path:
    lines = []
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name != "SHA256SUMS":
            lines.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.name}")
    target = out / "SHA256SUMS"
    target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True, help="a new or empty folder for the release files")
    ap.add_argument("--tag", help="the git tag being released; must be v<version>")
    args = ap.parse_args(argv)

    version = project_version()
    if args.tag and args.tag != f"v{version}":
        raise SystemExit(f"build: tag {args.tag} does not match pyproject version {version} (expected v{version})")
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"build: refused, {out} is not empty")
    out.mkdir(parents=True, exist_ok=True)

    run([sys.executable, "-m", "build", "--no-isolation", "--sdist", "--wheel", "--outdir", str(out), str(ROOT)])
    wheels = sorted(out.glob("*.whl"))
    sdists = sorted(out.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(f"build: expected one wheel and one sdist, found {wheels + sdists}")

    with tempfile.TemporaryDirectory() as tmp:
        env_dir = Path(tmp) / "venv"
        venv.EnvBuilder(with_pip=True, clear=True).create(env_dir)
        py = venv_python(env_dir)
        run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "--no-cache-dir", str(wheels[0])])
        run([str(py), "-m", "composer", "--version"])
        run([str(py), "-m", "composer", "demo", "--fast"], stdout=subprocess.DEVNULL, cwd=tmp)
        # pip itself was only the installer; it is not part of what the wheel brings, so it leaves the SBOM.
        run([str(py), "-m", "pip", "uninstall", "--yes", "--quiet", "pip"])
        sbom = out / f"lensmith_composer-{version}.cdx.json"
        run([sys.executable, "-m", "cyclonedx_py", "environment", "--pyproject", str(ROOT / "pyproject.toml"),
             "--mc-type", "application", "--output-reproducible", "--of", "JSON", "--sv", "1.6",
             "-o", str(sbom), str(py)])
    added = add_optional(sbom)
    sums = sha256sums(out)
    print(f"build: {wheels[0].name}, {sdists[0].name}, {sbom.name} (+{added} optional narration parts, "
          f"scope excluded), {sums.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
