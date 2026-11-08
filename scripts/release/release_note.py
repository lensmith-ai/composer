"""Build the release note, with every factual line checked by claim-seal against the changelog and the test results.

  python scripts/release/release_note.py --version 0.2.0 --draft release-notes/0.2.0.json \\
      --tests test-results.json --out-dir dist [--changelog CHANGELOG.md] [--judge model | --judge replay:FILE]

The draft is a short brief in claim-seal's shape: each item is one line of the note ("insight", an optional
"why_it_matters" and "detail"), and cites its source by title:
  {"id": "changelog", "ref": "Changelog 0.2.0"}        this version's section of CHANGELOG.md
  {"id": "tests", "ref": "Test results 0.2.0"}         the test results the release workflow recorded
claim-seal finds each cited title (plain code), then a model reads each line next to its source and says whether
the source supports it. The note is written ONLY when every line is "supported" and the seal verifies; a partly
supported, unsupported, unchecked or unresolved line stops the release (exit 1) and is named.

--judge model (default) uses the same model settings as `composer compose` (ANTHROPIC_API_KEY, or
COMPOSER_PROVIDER=openai with OPENAI_API_KEY and COMPOSER_OPENAI_BASE_URL). --judge replay:FILE replays recorded
answers, for the offline tests; a note checked that way says so in its footer.

Writes <out-dir>/release-note.md and <out-dir>/release-note-check.json (claim-seal's full result, seal included).
Exit codes: 0 written, 1 a line is not supported (nothing written), 2 a usage or input problem.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REPO = "lensmith-ai/composer"


class NoteError(Exception):
    pass


def changelog_section(text: str, version: str) -> str:
    """The body of `## [version]` in a Keep a Changelog file, up to the next `## ` heading."""
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m or not m.group(1).strip():
        raise NoteError(f"CHANGELOG has no section for {version}")
    body = re.sub(r"^\[[^\]]+\]:\s*\S+\s*$", "", m.group(1), flags=re.M)   # link definitions
    body = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", body)                     # [text](url) -> text
    body = re.sub(r"[`*_]", "", body)
    lines = []
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("### "):
            lines.append(line[4:].strip() + ":")
        else:
            lines.append(line.lstrip("-").strip().rstrip(".") + ".")
    return " ".join(lines)


def tests_text(results: list[dict]) -> str:
    """Plain sentences from test-results JSON files: what a reader of the release note can check."""
    out = []
    for r in results:
        if r.get("schema") != "composer-test-results/v1":
            raise NoteError("a --tests file is not composer-test-results/v1")
        s = (f"On {r['system']} with Python {r['python']}, the offline test suite ran {r['ran']} tests: "
             f"{r['passed']} passed, {r['failed']} failed, {r['errors']} had errors and {r['skipped']} were skipped.")
        if r.get("skips"):
            reasons = sorted({x["reason"] for x in r["skips"]})
            s += " Skipped because: " + "; ".join(reasons) + "."
        if r.get("commit"):
            s += f" Commit {r['commit']}."
        out.append(s)
    return " ".join(out)


def sources_for(version: str, changelog: str, results: list[dict]) -> dict:
    tag = f"v{version}"
    return {
        "changelog": {"label": "CHANGELOG.md", "items": [{
            "id": f"changelog-{version}", "title": f"Changelog {version}",
            "text": changelog_section(changelog, version),
            "url": f"https://github.com/{REPO}/blob/{tag}/CHANGELOG.md"}]},
        "tests": {"label": "Test results", "items": [{
            "id": f"tests-{version}", "title": f"Test results {version}",
            "text": tests_text(results),
            "url": f"https://github.com/{REPO}/releases/tag/{tag}"}]},
    }


def problems_in(result: dict) -> list[str]:
    out = []
    for n, item in enumerate(result["brief"].get("items") or [], 1):
        v = item.get("verification") or {}
        if v.get("verdict") != "supported":
            out.append(f"line {n} is {v.get('verdict') or 'unchecked'}: {item.get('insight', '')[:120]}"
                       + (f" ({v.get('why')})" if v.get("why") else ""))
        for cit in v.get("citations") or []:
            if cit.get("resolution") == "unresolved":
                out.append(f"line {n} cites {cit.get('ref')!r}, which is not a source title")
    return out


def render(version: str, draft: dict, result: dict, judge_name: str, replay: bool) -> str:
    import claim_seal
    seal = ((result.get("claim_evidence") or {}).get("verification") or {}).get("seal") or {}
    titles = {"changelog": f"the changelog for {version}", "tests": "the recorded test results"}
    lines = [f"# Lensmith Composer {version}", ""]
    if draft.get("lede"):
        lines += [draft["lede"].strip(), ""]
    lines += ["Each line below names where it comes from: this release's changelog entry or the test results the "
              "release workflow recorded. Before this note was published, claim-seal checked every line against "
              "that source. The seal and how to check it again are at the end.", "", "## What's in it", ""]
    for item in result["brief"]["items"]:
        cites = sorted({titles.get(c.get("id"), c.get("id")) for c in item.get("sources") or []})
        text = item["insight"].strip()
        if item.get("why_it_matters"):
            text += " " + item["why_it_matters"].strip()
        lines.append(f"- {text} <sub>(from {' and '.join(cites)}; checked: supported)</sub>")
        for d in item.get("detail") or []:
            lines.append(f"  - {d}")
    n = len(result["brief"]["items"])
    lines += ["", "## How this note was checked", "",
              f"- claim-seal {claim_seal.__version__} read each of the {n} lines next to the source it cites; "
              f"all {n} are supported. Judge: {judge_name}."
              + (" The judge's answers were REPLAYED from a file (an offline test run), not freshly judged."
                 if replay else ""),
              f"- Seal: `{seal.get('value', 'none')}`. `release-note-check.json`, attached to this release, holds "
              "the full check; `claim-seal verify-seal release-note-check.json` recomputes the seal.",
              "- What the check does not do: it shows the changelog and the test results say what this note says. "
              "It does not prove them true, and the judge is a model that can be wrong.",
              "", "## Check the files yourself", "",
              "```sh",
              "sha256sum -c SHA256SUMS",
              f"gh attestation verify lensmith_composer-{version}-py3-none-any.whl --repo {REPO} \\",
              f"  --signer-workflow {REPO}/.github/workflows/release.yml",
              "```", "",
              "Composer sends no telemetry: no analytics, no crash reports, no update checks.", ""]
    return "\n".join(lines)


def make_judge(spec: str):
    if spec.startswith("replay:"):
        from claim_seal.adapters import ReplayJudge
        return ReplayJudge.from_file(spec[len("replay:"):]), "replayed answers (replay-judge/v1)", True
    if spec != "model":
        raise NoteError(f"unknown --judge {spec!r}: use model or replay:FILE")
    sys.path.insert(0, str(ROOT))
    from composer.providers import from_env
    model = from_env(None, None)
    model.ready()
    return model, str(getattr(model, "name", "model")), False


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--version", required=True)
    ap.add_argument("--draft", required=True)
    ap.add_argument("--tests", required=True, action="append", help="a test-results JSON file (repeatable)")
    ap.add_argument("--changelog", default=str(ROOT / "CHANGELOG.md"))
    ap.add_argument("--judge", default="model")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)
    try:
        import claim_seal
        draft = json.loads(Path(args.draft).read_text(encoding="utf-8"))
        if draft.get("version") != args.version:
            raise NoteError(f"the draft is for {draft.get('version')!r}, not {args.version}")
        results = [json.loads(Path(p).read_text(encoding="utf-8")) for p in args.tests]
        if not all(r.get("ok") for r in results):
            raise NoteError("a test-results file is not ok: no release note for a red run")
        sources = sources_for(args.version, Path(args.changelog).read_text(encoding="utf-8"), results)
        brief = {"items": draft["items"]}
        judge, judge_name, replay = make_judge(args.judge)
    except (NoteError, OSError, KeyError, ValueError) as exc:
        print(f"release-note: {exc}", file=sys.stderr)
        return 2
    result = claim_seal.judge(brief, sources, model=judge)
    problems = problems_in(result)
    ce = result.get("claim_evidence")
    if not ce or not claim_seal.verify_seal(ce):
        problems.append("the claim-evidence seal is missing or does not verify")
    if problems:
        print("release-note: NOT written. Fix or remove these lines:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "release-note-check.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    (out / "release-note.md").write_text(render(args.version, draft, result, judge_name, replay), encoding="utf-8")
    seal = ((ce.get("verification") or {}).get("seal") or {}).get("value")
    print(f"release-note: {len(brief['items'])} lines, all supported, seal {seal} -> {out}/release-note.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
