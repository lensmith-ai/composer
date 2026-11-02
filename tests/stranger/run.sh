#!/bin/bash
# The stranger test: can someone who has never seen this project install a release and use the real page?
#
#   tests/stranger/run.sh <commit> [--second <commit>] [--strict] [--only-browser <engine-width,...>]
#
# From <commit> it:
#   1. builds the release the way the release workflow does (scripts/release/build.py in a pinned python:3.13, with
#      the hash-locked tools): sdist, wheel, SBOM, SHA256SUMS; and a second build for the update test (from
#      --second, or the same tree with the version raised to <version>.post1);
#   2. scans the built files for text that must not be published (scan_banned.py);
#   3. copies ONLY the release files into a fresh, pinned ubuntu:24.04 with curl and CA certificates (plus expect, the
#      test's robot for the interactive setup), checks SHA256SUMS, unpacks, runs ./setup.sh with an answers file and
#      once interactively through expect, `composer doctor`, `composer up`. The model is a local fixture with the
#      OpenAI chat-completions shape (fixtures.py, with a local HTTPS feed site): setup is given provider "openai",
#      its address on 127.0.0.1, a model id and a made-up key, so the real provider path runs with no real key;
#   4. cuts the container off the internet and drives the real page with Playwright in Chromium and WebKit at
#      390x844 and 1280x900 (browser_flow.mjs); then, with NO model configured, presses Compose and records what a
#      stranger sees (an error today is recorded as "expected to change", never as a pass);
#   5. lifecycle: restart, update to the second build and roll back (data kept), uninstall keeps data, setup again
#      picks it up, delete-data, and a file list of everything outside the app folder before and after.
# Prints "STRANGER: N passed, M failed, K skipped[, J expected to change] (reasons)" and each failure; exit 0 only when
# nothing failed. --strict turns every skip and every expected-to-change into a failure (for the final build).
#
# Needs: docker, git, python3, openssl, node with Playwright (PLAYWRIGHT_MODULE=<.../playwright/index.mjs> if it is
# not in node_modules; Chromium and WebKit installed), and root for nsenter: the browser runs on this machine inside
# the container's network namespace, because the app listens on 127.0.0.1 there, as it does on a laptop.
# Output: STRANGER_OUT (default a new folder under $TMPDIR): results.jsonl, summary.txt, run.log, shots/, logs.
set -uo pipefail

UBUNTU=ubuntu@sha256:fe81560990fae86dc4743202b2cb4d3df98d0bcf949173cecef15ce1127ef852
PYBUILD=python@sha256:6a9220edda062e9223ea0784740a535987299420b96fbfd520b89bbd3e772485

usage() { sed -n '4p' "$0" | sed 's/^# *//' >&2; exit 2; }
[ $# -ge 1 ] || usage
COMMIT=$1; shift
SECOND=""; STRICT=""; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --second) SECOND=$2; shift 2 ;;
    --strict) STRICT=--strict; shift ;;
    --only-browser) ONLY=$2; shift 2 ;;
    *) usage ;;
  esac
done

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(git -C "$HERE" rev-parse --show-toplevel)
OUT=${STRANGER_OUT:-$(mktemp -d "${TMPDIR:-/tmp}/stranger.XXXXX")}
mkdir -p "$OUT/shots" "$OUT/stage" "$OUT/logs"
RES=$OUT/results.jsonl
: > "$RES"
LOG=$OUT/run.log
exec > >(tee -a "$LOG") 2>&1
T0=$(date +%s)
NAME=stranger-$$-$RANDOM
NET=$NAME-offline
say() { printf '[%s] %s\n' "$(date -u +%H:%M:%S)" "$*"; }
rec() { python3 "$HERE/results.py" add "$RES" "$@"; printf '%s %s: %s\n' "$(echo "$2" | tr a-z A-Z)" "$1" "$3"; }
FIXPID=""
cleanup() {
  [ -n "$FIXPID" ] && kill "$FIXPID" 2>/dev/null
  docker rm -f "$NAME" >/dev/null 2>&1
  docker network rm "$NET" >/dev/null 2>&1
}
trap cleanup EXIT
finish() {
  cleanup
  say "done in $(( $(date +%s) - T0 )) s; results in $OUT"
  python3 "$HERE/results.py" summary "$RES" $STRICT | tee "$OUT/summary.txt"
  exit "${PIPESTATUS[0]}"
}
# one step inside the container; its "@@" lines become rows
CXN=0
cx() {
  CXN=$((CXN + 1))
  local logf; logf=$OUT/logs/cx-$(printf '%02d' "$CXN")-$1.log
  docker exec "$NAME" bash /stranger/in_container.sh "$@" > "$logf" 2>&1
  python3 "$HERE/results.py" ingest "$RES" "$logf" >/dev/null
  cat "$logf"
}
cxq() { docker exec "$NAME" bash /stranger/in_container.sh "$@" 2>/dev/null; }

for tool in docker git python3 openssl node nsenter; do
  command -v "$tool" >/dev/null || { say "missing $tool"; rec env.tools fail "the test needs $tool on this machine"; finish; }
done
FULL=$(git -C "$REPO" rev-parse --verify "$COMMIT^{commit}") || { say "no commit $COMMIT"; exit 2; }
say "stranger test of $FULL; output $OUT"

# ------------------------------------------------------------------------------------------- 1. build the release
build() {  # build SRC DIST LABEL
  mkdir -p "$2"
  if docker run --rm -v "$1:/src:ro" -v "$2:/out" "$PYBUILD" bash -c '
      set -e; cp -a /src /w; cd /w
      python -m pip install -q --disable-pip-version-check --root-user-action=ignore --require-hashes -r scripts/release/release-tools.txt
      python scripts/release/build.py --out /out
      cd /out && sha256sum -c SHA256SUMS' > "$OUT/logs/build-$3.log" 2>&1; then
    return 0
  fi
  return 1
}
mkdir -p "$OUT/src-a"
git -C "$REPO" archive "$FULL" | tar -x -C "$OUT/src-a"
VA=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$OUT/src-a/pyproject.toml" | head -n 1)
mkdir -p "$OUT/src-b"
if [ -n "$SECOND" ]; then
  git -C "$REPO" archive "$(git -C "$REPO" rev-parse --verify "$SECOND^{commit}")" | tar -x -C "$OUT/src-b"
else
  cp -a "$OUT/src-a/." "$OUT/src-b/"
  sed -i "s/^version = \"$VA\"$/version = \"$VA.post1\"/" "$OUT/src-b/pyproject.toml"
  sed -i "s/^__version__ = \"$VA\"$/__version__ = \"$VA.post1\"/" "$OUT/src-b/composer/__init__.py"
fi
VB=$(sed -n 's/^version = "\(.*\)"$/\1/p' "$OUT/src-b/pyproject.toml" | head -n 1)
say "building $VA (and $VB for the update test) as the release workflow does"
if build "$OUT/src-a" "$OUT/dist-a" a && build "$OUT/src-b" "$OUT/dist-b" b; then
  rec artifact.build pass "build.py in pinned python:3.13: $(cd "$OUT/dist-a" && ls | tr '\n' ' ')and $VB for the update; SHA256SUMS verify"
else
  rec artifact.build fail "the release build failed: $(tail -n 5 "$OUT"/logs/build-*.log | tr '\n' ' ' | cut -c1-400)"
  finish
fi

# which file does a stranger download? the release's tarball with setup.sh in it
REL=""; RELDIR="$OUT/dist-a"
for f in "$OUT"/dist-a/*.tar.gz; do
  # grep reads the whole list (no -q): with pipefail, grep -q stopping early made tar fail on SIGPIPE
  if tar -tzf "$f" | grep -E '^[^/]+/setup\.sh$' > /dev/null; then REL=$(basename "$f"); break; fi
done
if [ -n "$REL" ]; then
  rec artifact.setup_tarball pass "the release has $REL with setup.sh in it"
else
  rec artifact.setup_tarball fail "the release build makes no tarball with setup.sh in it ($(cd "$OUT/dist-a" && ls | tr '\n' ' ')); the README's ./setup.sh path cannot start from a release file. The rest of this run uses a stand-in: git archive of the same commit"
  RELDIR="$OUT/standin-a"; mkdir -p "$RELDIR"
  REL="lensmith-composer-$VA.tar.gz"
  git -C "$REPO" archive --format=tar.gz --prefix="lensmith-composer-$VA/" "$FULL" > "$RELDIR/$REL"
  (cd "$RELDIR" && sha256sum "$REL" > SHA256SUMS)
fi
WHEEL_B=$(cd "$OUT/dist-b" && ls *.whl | head -n 1)

# ------------------------------------------------------------------------------------------- 2. banned text
scan=( "$OUT"/dist-a/* )
[ "$RELDIR" != "$OUT/dist-a" ] && scan+=( "$RELDIR/$REL" )
python3 "$HERE/scan_banned.py" "$RES" "$OUT/banned-report.json" "${scan[@]}" --words-from "$OUT/src-a/tests/test_banned.py"

# ------------------------------------------------------------------------------------------- 3. what this build has
python3 - "$OUT/src-a" "$OUT/stage/features.txt" <<'PY'
import pathlib, sys
src, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
def text(p):
    f = src / p
    return f.read_text(encoding="utf-8", errors="replace") if f.is_file() else ""
code = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in (src / "composer").rglob("*.py"))
features = {
    "add_source": "/source/probe" in text("composer/server.py"),
    "make_lens": "/lens/save" in text("composer/server.py"),
    "reading_level": "reading_level" in text("composer/server.py"),
    "source_packages": (src / "composer/packages.json").is_file(),
    "article_parser": '"parser"' in text("composer/answers.py"),
    "checker_model": '"checker"' in text("composer/answers.py"),
    "model_picklist": "test call" in text("composer/installer.py"),
    "seals_daily": "seals_daily" in text("composer/scheduler.py"),
}
out.write_text("".join(k + "\n" for k, v in features.items() if v), encoding="utf-8")
print("features of this build: " + ", ".join(f"{k}={'yes' if v else 'no'}" for k, v in features.items()))
PY
feature() { grep -qx "$1" "$OUT/stage/features.txt"; }

# ------------------------------------------------------------------------------------------- the test's own files
cp "$HERE/in_container.sh" "$HERE/setup.exp" "$OUT/stage/"
openssl req -x509 -newkey rsa:2048 -nodes -days 2 -subj /CN=127.0.0.1 -addext subjectAltName=IP:127.0.0.1,DNS:localhost \
  -addext basicConstraints=critical,CA:TRUE -keyout "$OUT/fixture-key.pem" -out "$OUT/stage/fixture-cert.pem" \
  >/dev/null 2>&1
# a made-up key for the local fixture model: it is never a real key and is only ever sent to 127.0.0.1
printf 'fixture-%s\n' "$(head -c 12 /dev/urandom | od -An -tx1 | tr -d ' \n')" > "$OUT/stage/fixture-key.txt"
FIXMODEL='[provider]\nkind = "openai"\nbase_url = "http://127.0.0.1:8790/v1"\nmodel = "fixture-model"\nkey_from_env = "OPENAI_API_KEY"\n'
{
  printf '[install]\npython_download = true\n'
  printf "$FIXMODEL"
  # two local feeds (the page keeps at least two sources ticked); two host names, because setup names a feed
  # after its host
  printf '[sources]\nhacker_news = false\nadd = ["https://127.0.0.1:8443/harbor/feed.xml", "https://localhost:8443/blog/feed.xml"]\n'
  printf '[narration]\nenabled = false\n[schedule]\nenabled = false\n[server]\nport = 8765\n'
  feature article_parser && printf '[parser]\ntrafilatura = true\n'
} > "$OUT/stage/answers.toml"
printf "$FIXMODEL" > "$OUT/stage/answers-provider-fixture.toml"
printf '[provider]\nkind = "none"\n' > "$OUT/stage/answers-provider-none.toml"

# ------------------------------------------------------------------------------------------- 4. the clean machine
say "starting a clean $UBUNTU"
docker run -d --init --name "$NAME" --hostname stranger "$UBUNTU" sleep infinity >/dev/null || {
  rec env.clean_machine fail "could not start the pinned ubuntu container"; finish; }
PID=$(docker inspect -f '{{.State.Pid}}' "$NAME")
# the fixture services run on this machine but inside the container's network namespace: the app reaches them at
# 127.0.0.1, and nothing of them is on the container's disk
nsenter --net="/proc/$PID/ns/net" -- python3 -I -B "$HERE/fixtures.py" "$OUT/stage/fixture-cert.pem" \
  "$OUT/fixture-key.pem" "$OUT/logs/fixtures-requests.jsonl" > "$OUT/logs/fixtures.out" 2>&1 &
FIXPID=$!
for _ in $(seq 1 40); do grep -q '"model"' "$OUT/logs/fixtures.out" 2>/dev/null && break; sleep 0.25; done
if grep -q '"model"' "$OUT/logs/fixtures.out"; then
  rec fixtures.start pass "local HTTPS feed site and fixture model (OpenAI chat-completions shape) on the container's 127.0.0.1"
else
  rec fixtures.start fail "the fixture services did not start: $(tail -n 3 "$OUT/logs/fixtures.out" | tr '\n' ' ')"
fi
docker exec "$NAME" mkdir -p /stranger/out
docker cp "$OUT/stage/." "$NAME:/stranger/"
cx prep
cx bundle
TH=$(docker exec "$NAME" getent passwd tester | cut -d: -f6)
# a person downloads the release's files and its SHA256SUMS, which covers all of them (docs/releasing.md)
for f in "$RELDIR"/*; do docker cp "$f" "$NAME:$TH/downloads/"; done
docker exec "$NAME" chown -R tester:tester "$TH/downloads"
cx snapshot before
cx verify "$REL"
DIR=$(cx extract "$REL" | sed -n 's/^DIR=//p' | tail -n 1)
say "setup with an answers file (the local fixture model, a made-up key from the environment)"
cx setup_answers "$DIR"
cx doctor "$TH/.lensmith-composer" main
FEED_LABELS=$(cxq feed_labels | sort -u | paste -sd '|')
say "the local feeds are labelled \"${FEED_LABELS:-?}\" in this build"
say "setup on the terminal, through expect"
cx interactive "$DIR"
cx doctor "$TH/composer-interactive" interactive
cx interactive_cleanup

# ------------------------------------------------------------------------------------------- 5. offline, the page
docker network create --internal "$NET" >/dev/null && docker network connect "$NET" "$NAME" && \
  docker network disconnect bridge "$NAME"
cx no_internet
cx up_start up
cx uninstall_while_running
browser_cfg() {  # browser_cfg MODE FILE
  python3 - "$OUT" "$OUT/src-a" "$OUT/stage/features.txt" "${STRANGER_EXPECT_SOURCES:-6}" "$ONLY" \
    "${FEED_LABELS:-127.0.0.1|localhost}" "$1" "$2" <<'PY'
import json, pathlib, sys
out, src, feats, expect, only, label, mode, dest = (pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3],
                                                     int(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7], sys.argv[8])
bundled = json.loads((src / "composer/sources.json").read_text(encoding="utf-8"))["sources"]
rec = json.loads((src / "composer/data/recorded-run.json").read_text(encoding="utf-8"))
texts = [c.get("insight", "") for c in rec.get("cards", []) if c.get("insight")]
cfg = {"base": "http://127.0.0.1:8765", "results": str(out / "results.jsonl"), "shots": str(out / "shots"),
       "mode": mode, "features": {k: True for k in pathlib.Path(feats).read_text().split()},
       "bundled_labels": [s["label"] for s in bundled], "expect_bundled": expect,
       "recorded_texts": [t[:60] for t in texts],
       "blogs": [f"https://127.0.0.1:8443/blog{'' if n == 1 else f'-{n}'}" for n in range(1, 5)],
       "local_feed_labels": label.split("|"), "only": [x for x in only.split(",") if x]}
pathlib.Path(dest).write_text(json.dumps(cfg, indent=1), encoding="utf-8")
PY
}
browser() {  # browser CONFIG LOG
  timeout 3600 nsenter --net="/proc/$PID/ns/net" -- node "$HERE/browser_flow.mjs" "$1" > "$2" 2>&1
  say "browser exit $?"; grep -E '^(PASS|FAIL|SKIP|KNOWN) ' "$2" | cut -c1-260
}
browser_cfg flow "$OUT/browser.json"
say "the page, in Chromium and WebKit at 390x844 and 1280x900 (inside the container's network, no internet)"
browser "$OUT/browser.json" "$OUT/logs/browser.log"
SAVED0=$(cxq saved | sort | tr '\n' ' ')
if [ -z "$SAVED0" ]; then
  say "nothing is saved after the browser part; saving one brief through the engine's own routes so the lifecycle checks have data"
  BUNDLED=$(python3 -c 'import json, sys; print(" ".join(s["id"] for s in json.load(open(sys.argv[1]))["sources"]))' \
    "$OUT/src-a/composer/sources.json")
  cxq seed_saved $BUNDLED | tail -n 3
  SAVED0=$(cxq saved | sort | tr '\n' ' ')
fi
say "saved briefs on the shelf: ${SAVED0:-none}"

# the seal: doctor --seals re-checks every saved brief; the daily re-check is scheduled where the build has it
if feature seals_daily; then
  sched=$(docker exec "$NAME" curl -s http://127.0.0.1:8765/schedule)
  if printf '%s' "$sched" | grep -q '"seals_daily": *true'; then
    rec seals.daily pass "the scheduler reports the daily seal re-check on: $(printf '%s' "$sched" | cut -c1-200)"
  else
    rec seals.daily fail "this build has the daily seal re-check but /schedule says: $(printf '%s' "$sched" | cut -c1-200)"
  fi
else
  rec seals.daily skip "this build has no daily seal re-check in its scheduler"
fi
cx up_stop
seal_out=$(docker exec "$NAME" su tester -s /bin/bash -c "SSL_CERT_FILE=/stranger/ca-bundle.pem COMPOSER_ALLOW_PRIVATE_FETCH=1 $TH/.lensmith-composer/bin/composer doctor --seals" 2>&1); seal_rc=$?
printf '%s\n' "$seal_out" > "$OUT/logs/doctor-seals.log"
seal_line=$(printf '%s\n' "$seal_out" | grep -iE 'seal' | head -n 3 | tr '\n' ' ')
if [ "$seal_rc" = 0 ] && [ -n "$SAVED0" ] && [ -n "$seal_line" ]; then
  rec seals.doctor pass "composer doctor --seals rc 0 with saved briefs ($SAVED0): $seal_line"
elif [ -z "$SAVED0" ]; then
  rec seals.doctor fail "blocked: no saved brief to re-check; doctor --seals rc $seal_rc"
else
  rec seals.doctor fail "composer doctor --seals rc $seal_rc: $seal_line $(printf '%s' "$seal_out" | grep '^FAIL' | head -n 3 | tr '\n' ' ')"
fi

# what a stranger sees with NO model: provider none, Compose pressed (recorded as expected to change, not a pass)
cx provider none
cx up_start no_model_up
browser_cfg no_model "$OUT/browser-no-model.json"
browser "$OUT/browser-no-model.json" "$OUT/logs/browser-no-model.log"
cx up_stop
cx provider fixture

# ------------------------------------------------------------------------------------------- 6. lifecycle
keeps() {  # keeps ID WHAT: the saved briefs are the same as after the browser part
  local now; now=$(cxq saved | sort | tr '\n' ' ')
  if [ -z "$SAVED0" ]; then
    rec "$1" fail "blocked: nothing was saved in the browser part, so keeping data cannot be shown"
  elif [ "$now" = "$SAVED0" ]; then
    rec "$1" pass "$2: the same $(echo "$SAVED0" | wc -w) saved brief(s) on the shelf"
  else
    rec "$1" fail "$2: the shelf changed from [$SAVED0] to [$now]"
  fi
}
cx up_start restart
keeps lifecycle.restart_keeps_data "after a restart"
cx up_stop
docker network connect bridge "$NAME" && docker network disconnect "$NET" "$NAME"
say "online again for the update (pip fetches the pinned dependency): $(cxq online)"
docker exec "$NAME" mkdir -p "$TH/downloads/b"
docker cp "$OUT/dist-b/$WHEEL_B" "$NAME:$TH/downloads/b/"
docker cp "$OUT/dist-b/SHA256SUMS" "$NAME:$TH/downloads/b/"
docker exec "$NAME" chown -R tester:tester "$TH/downloads/b"
cx update "$WHEEL_B"
v=$(cxq version)
if printf '%s' "$v" | grep -qF "$VB"; then rec lifecycle.update_version pass "composer --version: $v"
else rec lifecycle.update_version fail "after the update composer --version says $v, expected $VB"; fi
cx up_start after_update
keeps lifecycle.update_keeps_data "after updating to $VB"
cx up_stop
cx rollback
v=$(cxq version)
if printf '%s' "$v" | grep -qE "(^| )$VA\$"; then rec lifecycle.rollback_version pass "composer --version: $v"
else rec lifecycle.rollback_version fail "after the rollback composer --version says $v, expected $VA"; fi
cx up_start after_rollback
keeps lifecycle.rollback_keeps_data "after rolling back to $VA"
cx up_stop
cx uninstall_keep
cx reinstall "$DIR"
cx up_start after_reinstall
keeps lifecycle.reinstall_keeps_data "after uninstall and setup again"
cx up_stop
cx delete_data
cx snapshot after
cx compare
docker cp "$NAME:/stranger/out/." "$OUT/logs/" >/dev/null 2>&1
finish
