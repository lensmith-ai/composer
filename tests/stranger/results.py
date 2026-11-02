"""The stranger test's record: one JSON line per check, and the summary line.

  python3 results.py add RESULTS ID STATUS REASON       append one row (STATUS: pass, fail, skip or known)
  python3 results.py ingest RESULTS LOG                  append every "@@id|status|reason" line printed in LOG
  python3 results.py summary RESULTS [--strict]          print "STRANGER: N passed, M failed, K skipped (reasons)"

The summary also fails every check the test is meant to make but never recorded (a phase that crashed or was cut
short), so a missing row can never read as a pass. With --strict a skip counts as a failure too: use it on the
build that is meant to have every flow. "known" marks a behaviour recorded as expected to change (never a pass);
it is listed and counted on its own, and --strict fails it. Exit code 0 only when nothing failed.
"""
from __future__ import annotations

import json
import sys
import time
from collections import Counter, defaultdict

BROWSER_STEPS = ["open_root", "replay_plays", "narration_off", "source_picker", "source_packages", "add_source", "make_lens", "compose",
                 "reading_level", "compose_with_lens", "brief_opens", "brief_link", "insight_cards",
                 "transcript", "save", "shelf", "trash", "page_health"]
COMBOS = [("chromium", "390x844"), ("chromium", "1280x900"), ("webkit", "390x844"), ("webkit", "1280x900")]
EXPECTED = [
    "artifact.build", "artifact.setup_tarball", "artifact.banned_text", "artifact.checksum", "artifact.checksum_bites",
    "artifact.has_setup", "env.clean_machine", "fixtures.start", "setup.answers", "setup.data_private",
    "setup.add_feed", "doctor.main", "doctor.main.article_parser", "doctor.main.checker",
    "setup.interactive", "setup.interactive.prompts", "setup.key_not_echoed", "setup.model_picklist",
    "doctor.interactive", "setup.interactive_removed", "env.no_internet", "lifecycle.up",
    "lifecycle.uninstall_refused_while_running", "seals.doctor", "seals.daily", "lifecycle.restart_keeps_data",
    "lifecycle.update", "lifecycle.update_version", "lifecycle.update_keeps_data", "lifecycle.rollback",
    "lifecycle.rollback_version", "lifecycle.rollback_keeps_data", "lifecycle.uninstall_keeps_data",
    "lifecycle.reinstall", "lifecycle.reinstall_keeps_data", "lifecycle.delete_data", "lifecycle.outside_unchanged",
] + [f"browser.{s}@{e}-{z}" for e, z in COMBOS for s in BROWSER_STEPS] + [
    "browser.no_model@chromium-390x844", "browser.no_model@webkit-390x844"]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def add(path: str, rid: str, status: str, reason: str) -> None:
    if status not in ("pass", "fail", "skip", "known"):
        raise SystemExit(f"results: bad status {status!r}")
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"t": now(), "id": rid, "status": status, "reason": reason[:1200]}) + "\n")


def ingest(path: str, log: str) -> int:
    n = 0
    with open(log, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if line.startswith("@@") and line.count("|") >= 2:
                rid, status, reason = line[2:].rstrip("\n").split("|", 2)
                add(path, rid, status, reason)
                n += 1
    return n


def key(row: dict) -> str:
    if row.get("engine") and row.get("size"):
        return f"{row['id']}@{row['engine']}-{row['size']}"
    return row["id"]


def summary(path: str, strict: bool) -> int:
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
    except FileNotFoundError:
        pass
    latest: dict[str, dict] = {}
    for row in rows:
        latest[key(row)] = row  # a re-run of one check replaces its earlier row
    for rid in EXPECTED:
        if rid not in latest:
            latest[rid] = {"id": rid, "status": "fail", "reason": "no result recorded: the step never ran"}
    counts = Counter()
    skips: dict[str, list] = defaultdict(list)
    fails = []
    for rid, row in latest.items():
        status = row["status"]
        if status == "skip" and strict:
            status = "fail"
            row = dict(row, reason="skipped under --strict: " + row["reason"])
        if status == "known" and strict:
            status = "fail"
            row = dict(row, reason="known problem under --strict: " + row["reason"])
        counts[status] += 1
        if status == "known":
            fails.append((rid, "(expected to change, not a pass) " + row["reason"]))
        elif status == "skip":
            skips[row["reason"]].append(rid)
        elif status == "fail":
            fails.append((rid, row["reason"]))
    reasons = "; ".join(f"{len(ids)}x {reason}" for reason, ids in sorted(skips.items(), key=lambda kv: -len(kv[1])))
    known = f", {counts['known']} expected to change" if counts["known"] else ""
    print(f"STRANGER: {counts['pass']} passed, {counts['fail']} failed, {counts['skip']} skipped{known}"
          + (f" ({reasons})" if reasons else ""))
    for rid, reason in sorted(fails):
        print(f"  {'KNOWN' if reason.startswith('(expected') else 'FAIL'} {rid}: {reason}")
    return 1 if counts["fail"] else 0


def main(argv: list[str]) -> int:
    if len(argv) >= 5 and argv[0] == "add":
        add(argv[1], argv[2], argv[3], " ".join(argv[4:]))
        return 0
    if len(argv) == 3 and argv[0] == "ingest":
        print(f"recorded {ingest(argv[1], argv[2])} results from {argv[2]}")
        return 0
    if len(argv) >= 2 and argv[0] == "summary":
        return summary(argv[1], "--strict" in argv[2:])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
