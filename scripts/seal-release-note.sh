#!/bin/sh
# Seal the release note for one version, on the maintainer's own computer, before the tag.
#
#   sh scripts/seal-release-note.sh 0.2.0                      the judge is your own `claude` login (no API key)
#   ANTHROPIC_API_KEY=... sh scripts/seal-release-note.sh 0.2.0   the judge is the Anthropic model in that key
#
# claim-seal reads each line of release-notes/<version>.json next to the changelog entry it cites and a model says whether
# the entry supports it (a few model calls in all). Only if every line is supported, the sealed result is
# written to release-notes/<version>.sealed.json: commit it with the release. The release workflow then re-verifies that file
# offline (no model, no key, no secret) and stops the release if the note, the changelog entry or the seal changed after
# this ran. So run it LAST: after the final edit to CHANGELOG.md's entry for this version and to the draft.
#
# It needs a Python 3.10+ with Composer installed (pip install .), which brings claim-seal. Set PYTHON to pick another one.
set -eu
version=${1:?usage: sh scripts/seal-release-note.sh VERSION (for example 0.2.0)}
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then judge=model; else judge=claude-cli; fi
here=$(cd "$(dirname "$0")/.." && pwd)
py=${PYTHON:-python3}
cd "$here"
"$py" scripts/release/release_note.py seal --version "$version" --draft "release-notes/$version.json" \
  --judge "$judge" --out "release-notes/$version.sealed.json"
# the same check the release workflow makes, now: the saved seal must verify against the files as they are
out=$(mktemp -d "${TMPDIR:-/tmp}/release-note-check.XXXXXX")  # vnf-allow: mktemp template, not a stub
env -u ANTHROPIC_API_KEY "$py" scripts/release/release_note.py verify --version "$version" \
  --draft "release-notes/$version.json" --sealed "release-notes/$version.sealed.json" --out-dir "$out"
echo "sealed: release-notes/$version.sealed.json (commit it). The note as it will be published: $out/release-note.md"
