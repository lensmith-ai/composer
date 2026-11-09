"""The release note, claim-checked ONCE on the maintainer's server before the tag, then only re-verified (offline) by the
release workflow. No model key and no secret are needed on GitHub.

  python scripts/release/release_note.py seal   --version 0.2.0 --draft release-notes/0.2.0.json \\
      --out release-notes/0.2.0.sealed.json [--changelog CHANGELOG.md] [--judge model | --judge replay:FILE]
  python scripts/release/release_note.py verify --version 0.2.0 --draft release-notes/0.2.0.json \\
      --sealed release-notes/0.2.0.sealed.json --out-dir note [--changelog CHANGELOG.md]

The draft is a short brief in claim-seal's shape: each item is one line of the note ("insight", an optional
"why_it_matters" and "detail"), and cites its source by title:
  {"id": "changelog", "ref": "Changelog 0.2.0"}        this version's section of CHANGELOG.md
claim-seal finds each cited title (plain code), then a model reads each line next to its source and says whether the
source supports it.

seal (run by the maintainer, with the maintainer's own model key, once, after the last edit to the changelog and the
draft): writes the sealed file ONLY when every line is "supported" and the seal verifies; a partly supported, unsupported,
unchecked or unresolved line stops it (exit 1) and is named. The file is committed with the release. It holds claim-seal's
full result and the SHA-256 of the draft file and of the changelog section it checked.

verify (run by the release workflow; no model, no key, no network): refuses, naming what changed, unless
  - the sealed file is for this version and its judge was a model (not a replay),
  - the draft file is byte for byte the one that was sealed, and its lines are the lines that were checked,
  - the changelog section is the text that was checked (its SHA-256 equals the one the seal binds),
  - every line is supported and claim-seal's seal recomputes.
It then writes <out-dir>/release-note.md and <out-dir>/release-note-check.json (claim-seal's result, seal included).
Exit codes: 0 done, 1 not sealed or changed since sealing (nothing written), 2 a usage or input problem.

The seal is an unkeyed digest chain: tamper-evident alongside version history (the sealed file is committed), not a
signature. It shows the changelog says what the note says; it does not prove the changelog true, and the judge is a
model that can be wrong.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
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


SCHEMA = "composer-release-note-seal/v1"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _clean(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"[`*_]", "", text)
    return text.strip().rstrip(".") + "."


def changelog_entries(text: str, version: str) -> list[tuple[str, str]]:
    """One (title, text) per bullet of `## [version]`: "Changelog 0.2.0, Added 9" is the ninth bullet under ### Added.
    A model judges a line next to the single entry it cites, not next to a whole long section."""
    m = re.search(rf"^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not m or not m.group(1).strip():
        raise NoteError(f"CHANGELOG has no section for {version}")
    entries: list[list] = []
    heading, counts = "", {}
    for line in m.group(1).splitlines():
        if line.startswith("### "):
            heading = line[4:].strip()
            counts[heading] = 0
        elif line.startswith("- ") and heading:
            counts[heading] += 1
            entries.append([f"Changelog {version}, {heading} {counts[heading]}", line[2:].strip()])
        elif line.strip() and entries and line.startswith(" "):
            entries[-1][1] += " " + line.strip()
    if not entries:
        raise NoteError(f"CHANGELOG has no entries under {version}")
    return [(title, _clean(body)) for title, body in entries]


def sources_for(version: str, changelog: str) -> dict:
    tag = f"v{version}"
    return {
        "changelog": {"label": "CHANGELOG.md", "items": [{
            "id": f"changelog-{version}-{n}", "title": title, "text": body,
            "url": f"https://github.com/{REPO}/blob/{tag}/CHANGELOG.md"}
            for n, (title, body) in enumerate(changelog_entries(changelog, version), 1)]},
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


def render(version: str, draft: dict, sealed: dict) -> str:
    import claim_seal
    result = sealed["result"]
    seal = ((result.get("claim_evidence") or {}).get("verification") or {}).get("seal") or {}
    lines = [f"# Lensmith Composer {version}", ""]
    if draft.get("lede"):
        lines += [draft["lede"].strip(), ""]
    lines += ["Each line below names where it comes from: this release's changelog entry. Before the tag was made, "
              "claim-seal checked every line against that entry on the maintainer's own computer, and sealed the result "
              "in the repository. The release workflow then re-verified the saved seal offline: it needs no model and "
              "no key, and it stops the release if the note or the changelog entry changed after sealing. "
              "The seal and how to check it again are at the end.", "", "## What's in it", ""]
    for item in result["brief"]["items"]:
        text = item["insight"].strip()
        if item.get("why_it_matters"):
            text += " " + item["why_it_matters"].strip()
        lines.append(f"- {text} <sub>(from the changelog for {version}; checked: supported)</sub>")
        for d in item.get("detail") or []:
            lines.append(f"  - {d}")
    n = len(result["brief"]["items"])
    lines += ["", "## How this note was checked", "",
              f"- claim-seal {claim_seal.__version__} read each of the {n} lines next to the source it cites; "
              f"all {n} are supported. Judge: {sealed.get('judge', 'a model')}, on {sealed.get('sealed_on', 'an earlier day')}.",
              f"- Seal: `{seal.get('value', 'none')}`. `release-note-check.json`, attached to this release, holds "
              "the full check; `claim-seal verify-seal release-note-check.json` recomputes the seal. "
              f"The sealed file is `release-notes/{version}.sealed.json` in the repository.",
              "- What the check does not do: it shows the changelog says what this note says. "
              "It does not prove the changelog true, and the judge is a model that can be wrong.",
              "", "## Check the files yourself", "",
              "```sh",
              "sha256sum -c SHA256SUMS",
              f"gh attestation verify lensmith_composer-{version}-py3-none-any.whl --repo {REPO} \\",
              f"  --signer-workflow {REPO}/.github/workflows/release.yml",
              "```", "",
              "Composer sends no telemetry: no analytics, no crash reports, no update checks.", ""]
    return "\n".join(lines)


class ClaudeCLIJudge:
    """A judge that asks the `claude` command (the maintainer's own login) instead of an API key."""

    def __init__(self, model_id: str):
        import shutil
        self.exe = shutil.which("claude")
        if not self.exe:
            raise NoteError("--judge claude-cli needs the `claude` command on PATH")
        self.name = f"claude-cli:{model_id}"
        self.model_id = model_id

    def ready(self) -> None:
        return None

    def __call__(self, prompt: str, timeout: float | None = None):
        import os
        import subprocess
        import tempfile
        from claim_seal.support import ModelText
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with tempfile.TemporaryDirectory(prefix="release-note-judge-") as cwd:
            run = subprocess.run([self.exe, "-p", "--model", self.model_id, "--output-format", "text",
                                  "--no-session-persistence"], input=prompt, capture_output=True, text=True,
                                 timeout=timeout or 300, cwd=cwd, env=env)
        if run.returncode != 0:
            raise NoteError(f"claude exited {run.returncode}: {(run.stderr or run.stdout)[-300:]}")
        return ModelText(run.stdout, model=self.name)


def make_judge(spec: str):
    if spec.startswith("replay:"):
        from claim_seal.adapters import ReplayJudge
        return ReplayJudge.from_file(spec[len("replay:"):]), "replayed answers (replay-judge/v1)", True
    if spec.startswith("claude-cli"):
        # The maintainer's own `claude` login (no API key): one `claude -p` call per prompt, in an empty folder so no project
        # instructions are read. Optional model after a colon: claude-cli:sonnet
        model_id = spec.partition(":")[2] or "sonnet"
        return ClaudeCLIJudge(model_id), f"claude-cli:{model_id}", False
    if spec != "model":
        raise NoteError(f"unknown --judge {spec!r}: use model, claude-cli[:MODEL] or replay:FILE")
    sys.path.insert(0, str(ROOT))
    from composer.providers import from_env
    model = from_env(None, None)
    model.ready()
    return model, str(getattr(model, "name", "model")), False


def _line_key(item: dict) -> tuple:
    return (item.get("insight"), item.get("why_it_matters"), tuple(item.get("detail") or ()),
            tuple((s.get("id"), s.get("ref")) for s in item.get("sources") or ()))


def load_draft(path: str, version: str) -> tuple[dict, str]:
    raw = Path(path).read_bytes()
    draft = json.loads(raw.decode("utf-8"))
    if draft.get("version") != version:
        raise NoteError(f"the draft is for {draft.get('version')!r}, not {version}")
    return draft, hashlib.sha256(raw).hexdigest()


def cmd_seal(args) -> int:
    import claim_seal
    try:
        draft, draft_sha = load_draft(args.draft, args.version)
        changelog = Path(args.changelog).read_text(encoding="utf-8")
        sources = sources_for(args.version, changelog)
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
        print("release-note: NOT sealed. Fix or remove these lines:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1
    sealed = {"schema": SCHEMA, "version": args.version, "sealed_on": datetime.now(timezone.utc).date().isoformat(),
              "judge": judge_name, "replayed": replay, "draft_sha256": draft_sha,
              "changelog_section_sha256": sha256_text(changelog_section(changelog, args.version)), "result": result}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sealed, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    seal = ((ce.get("verification") or {}).get("seal") or {}).get("value")
    print(f"release-note: {len(brief['items'])} lines, all supported, seal {seal} -> {out}")
    return 0


def check_sealed(version: str, draft_path: str, changelog_text: str, sealed: dict, *, allow_replay: bool) -> tuple[dict, list[str]]:
    """(draft, why not): empty list when the sealed file still matches the draft and the changelog and its seal holds."""
    import claim_seal
    why: list[str] = []
    if sealed.get("schema") != SCHEMA:
        return {}, [f"the sealed file is not {SCHEMA}"]
    if sealed.get("version") != version:
        why.append(f"the sealed file is for {sealed.get('version')!r}, not {version}")
    if (sealed.get("replayed") or (sealed.get("result") or {}).get("verification", {}).get("model") == "replay-judge/v1") \
            and not allow_replay:
        why.append("the sealed file was made from replayed answers, not by a model judge")
    draft, draft_sha = load_draft(draft_path, version)
    if draft_sha != sealed.get("draft_sha256"):
        why.append("the draft file (release-notes/%s.json) changed after it was sealed" % version)
    result = sealed.get("result") or {}
    sealed_items = [_line_key(i) for i in (result.get("brief") or {}).get("items") or []]
    if sealed_items != [_line_key(i) for i in draft.get("items") or []]:
        why.append("the note's lines are not the lines that were checked")
    if sha256_text(changelog_section(changelog_text, version)) != sealed.get("changelog_section_sha256"):
        why.append(f"the changelog entry for {version} changed after the note was sealed")
    current = {sha256_text(body) for _, body in changelog_entries(changelog_text, version)}
    bound = [s.get("raw_sha256") for s in (result.get("lineage") or {}).get("sources") or [] if s.get("source") == "changelog"]
    if not bound or not set(bound) <= current:
        why.append("the seal's source binding is not the current changelog entries")
    why += problems_in(result) if result.get("brief") else ["the sealed file holds no checked lines"]
    ce = result.get("claim_evidence")
    if not ce or not claim_seal.verify_seal(ce):
        why.append("the claim-evidence seal is missing or does not recompute")
    return draft, why


def cmd_verify(args) -> int:
    try:
        sealed = json.loads(Path(args.sealed).read_text(encoding="utf-8"))
        changelog = Path(args.changelog).read_text(encoding="utf-8")
        draft, why = check_sealed(args.version, args.draft, changelog, sealed, allow_replay=args.allow_replay)
    except (NoteError, OSError, KeyError, ValueError) as exc:
        print(f"release-note: {exc}", file=sys.stderr)
        return 2
    if why:
        print("release-note: NOT verified. The sealed note no longer matches:", file=sys.stderr)
        for w in why:
            print(f"  - {w}", file=sys.stderr)
        print("  Seal it again (scripts/seal-release-note.sh), commit the new sealed file, and move the tag.", file=sys.stderr)
        return 1
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "release-note-check.json").write_text(json.dumps(sealed["result"], indent=1, ensure_ascii=False) + "\n",
                                                 encoding="utf-8")
    (out / "release-note.md").write_text(render(args.version, draft, sealed), encoding="utf-8")
    seal = ((sealed["result"]["claim_evidence"].get("verification") or {}).get("seal") or {}).get("value")
    print(f"release-note: verified, {len(sealed['result']['brief']['items'])} lines, all supported, seal {seal} -> {out}/release-note.md")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seal", help="check every line with a model judge and write the sealed file")
    v = sub.add_parser("verify", help="re-verify a sealed file offline and write the note")
    for sp in (s, v):
        sp.add_argument("--version", required=True)
        sp.add_argument("--draft", required=True)
        sp.add_argument("--changelog", default=str(ROOT / "CHANGELOG.md"))
    s.add_argument("--judge", default="model")
    s.add_argument("--out", required=True)
    v.add_argument("--sealed", required=True)
    v.add_argument("--out-dir", required=True)
    v.add_argument("--allow-replay", action="store_true", help="tests only: accept a sealed file made from replayed answers")
    args = ap.parse_args(argv)
    return cmd_seal(args) if args.cmd == "seal" else cmd_verify(args)


if __name__ == "__main__":
    sys.exit(main())
