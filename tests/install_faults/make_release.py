"""Assemble a release kit directory for the installer tests: Composer's sdist and wheel built from this checkout, plus
the dependency files (certifi's wheel, claim-seal's wheel and its pinned source archive) copied from --extras.

  python make_release.py --out NEWDIR --extras DIR --builder-python PATH/TO/python-with-build-and-setuptools

--out must not exist yet (nothing is ever cleared). Then: python scripts/install/build_install.py --release NEWDIR --out ...
No network is used."""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--extras", required=True, type=Path)
    ap.add_argument("--builder-python", required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    subprocess.run([a.builder_python, "-m", "build", "--sdist", "--wheel", "--no-isolation", "-o", str(a.out), str(ROOT)], check=True,
                   env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
    for p in a.extras.iterdir():
        if p.is_file():
            shutil.copy2(p, a.out / p.name)
    print("release kit:", sorted(x.name for x in a.out.iterdir()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
