"""Run the offline test suite and write what happened as JSON: the release note's second source.

  python scripts/release/test_results.py --out test-results.json

The file records the Python version, the system, how many tests ran, passed, failed, errored and were skipped
(each skip with its reason), and the commit. Exit 0 only when nothing failed or errored.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def commit() -> str | None:
    # The checked-out commit first: on a manual workflow run GITHUB_SHA is main's head, not the released commit.
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return os.environ.get("GITHUB_SHA") or None


def version() -> str:
    m = re.search(r'^version\s*=\s*"([^"]+)"', (ROOT / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    return m.group(1) if m else "unknown"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)
    tests_dir = ROOT / "tests"
    sys.path.insert(0, str(tests_dir))
    suite = unittest.defaultTestLoader.discover(str(tests_dir), top_level_dir=str(tests_dir))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    doc = {
        "schema": "composer-test-results/v1",
        "version": version(),
        "commit": commit(),
        "python": platform.python_version(),
        "system": platform.system(),
        "ran": result.testsRun,
        "passed": result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped),
        "failed": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "skips": [{"test": t.id(), "reason": str(reason)} for t, reason in result.skipped],
        "ok": result.wasSuccessful(),
    }
    Path(args.out).write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"test-results: {doc['ran']} ran, {doc['passed']} passed, {doc['failed']} failed, {doc['errors']} errors, "
          f"{doc['skipped']} skipped -> {args.out}")
    return 0 if doc["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
