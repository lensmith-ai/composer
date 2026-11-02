#!/bin/bash
# The stranger's side of the test: runs INSIDE the clean container as root, one step per call, and acts as the
# person (user "tester") with `su`. Each result is one line "@@<id>|<pass|fail|skip>|<reason>" that run.sh records.
#   bash in_container.sh <step> [args...]
# Files: the release files are in the tester's downloads folder (as if downloaded), the test's own files in /stranger.
set -uo pipefail

T=/stranger
TH=$(getent passwd tester | cut -d: -f6)
TH=${TH:-/nonexistent}
H=$TH/.lensmith-composer
IH=$TH/composer-interactive
DL=$TH/downloads
FIXENV="SSL_CERT_FILE=$T/ca-bundle.pem COMPOSER_ALLOW_PRIVATE_FETCH=1"

rec() { local r=${3//$'\n'/ }; printf '@@%s|%s|%s\n' "$1" "$2" "${r:0:600}"; }
as_tester() { su tester -s /bin/bash -c "$1"; }
feature() { grep -qx "$1" "$T/features.txt" 2>/dev/null; }
tail_of() { tail -n "${2:-6}" "$1" 2>/dev/null | tr '\n' ' ' | tr -s ' ' | cut -c1-400; }

step=$1; shift
case "$step" in

prep)
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null \
    || { rec env.prereqs fail "apt could not install curl and ca-certificates"; exit 1; }
  # expect is the test's own robot for the interactive setup, not something Composer needs
  apt-get install -y -qq --no-install-recommends expect >/dev/null || { rec env.expect fail "could not install expect"; exit 1; }
  useradd -m -s /bin/bash tester
  TH=$(getent passwd tester | cut -d: -f6); DL=$TH/downloads
  mkdir -p "$DL" && chown tester:tester "$DL"
  py=$(command -v python3 || command -v python || true)
  if [ -z "$py" ]; then
    rec env.clean_machine pass "ubuntu:24.04 by digest, only curl + ca-certificates (+ expect for the test robot); no python3 on PATH"
  else
    rec env.clean_machine fail "the clean machine already has $py, so the no-Python path is not being tested"
  fi
  ;;

bundle)
  # the app trusts the fixture site's certificate through SSL_CERT_FILE: a bundle of the system CAs plus that one
  sys_ca=$(ls -1 /e*/ssl/certs/ca-certificates.crt | head -n 1)  # the system bundle (the ca-certificates package)
  cat "$sys_ca" "$T/fixture-cert.pem" > "$T/ca-bundle.pem" && chmod 644 "$T"/*
  ;;

snapshot)
  name=$1
  ex=( -path "$H" -o -path "$IH" -o -path "$DL" -o -path "$T" -o -path /proc -o -path /sys -o -path /dev -o -path /run -o -path /tmp \
       -o -path /var/tmp )
  # files the container runtime mounts in (name resolution files it rewrites when the network changes) are not
  # the machine's own files: they are taken from mountinfo, not named here
  while read -r mp; do [ -f "$mp" ] && ex+=( -o -path "$mp" ); done < <(awk '{print $5}' /proc/self/mountinfo)
  find / -xdev \( "${ex[@]}" \) -prune -o \( -type f -o -type l \) -print0 2>/dev/null | sort -z | \
    xargs -0 -r sha256sum 2>/dev/null > "/tmp/snap-$name.files" || true
  find / -xdev \( "${ex[@]}" \) -prune -o -type d -printf "%m %u %p\n" 2>/dev/null | sort > "/tmp/snap-$name.dirs"
  echo "snapshot $name: $(wc -l < "/tmp/snap-$name.files") files, $(wc -l < "/tmp/snap-$name.dirs") folders"
  ;;

compare)
  # measured even when an app folder is left behind (delete_data reports that); app folders are excluded here
  df=$(diff /tmp/snap-before.files /tmp/snap-after.files | grep '^[<>]' | head -n 12 | tr '\n' ' ')
  dd=$(diff /tmp/snap-before.dirs /tmp/snap-after.dirs | grep '^[<>]' | head -n 12 | tr '\n' ' ')
  left=$(ls -d "$H" "$IH" 2>/dev/null | tr '\n' ' ')
  if [ -n "$df$dd" ]; then
    rec lifecycle.outside_unchanged fail "changed outside the app folder: $df $dd"
  else
    rec lifecycle.outside_unchanged pass "file list and hashes outside the app folders identical before setup and after the last step: $(wc -l < /tmp/snap-before.files) files, $(wc -l < /tmp/snap-before.dirs) folders (excluded: the app folders, the downloads folder, the test's own folder, files the container runtime mounts, /tmp, /proc, /sys, /dev, /run)${left:+; app folder still present: $left}"
  fi
  ;;

verify)
  rel=$1
  out=$(as_tester "cd $DL && sha256sum -c SHA256SUMS 2>&1"); rc=$?
  n=$(printf '%s\n' "$out" | grep -c ': OK$')
  if [ "$rc" = 0 ] && printf '%s\n' "$out" | grep -qF "$rel: OK"; then
    rec artifact.checksum pass "sha256sum -c SHA256SUMS: $n files OK, including $rel"
  else
    rec artifact.checksum fail "sha256sum -c SHA256SUMS rc $rc: $(printf '%s' "$out" | tr '\n' ' ' | cut -c1-300)"
  fi
  # the check must bite: one changed byte in a copy fails it
  mkdir -p /tmp/tamper && cp "$DL/$rel" "$DL/SHA256SUMS" /tmp/tamper/ && printf 'x' >> "/tmp/tamper/$rel"
  if (cd /tmp/tamper && sha256sum -c SHA256SUMS >/dev/null 2>&1); then
    rec artifact.checksum_bites fail "a release file with one byte added still passed sha256sum -c"
  else
    rec artifact.checksum_bites pass "a copy with one byte added fails sha256sum -c"
  fi
  rm -rf /tmp/tamper
  ;;

extract)
  rel=$1
  as_tester "cd $DL && tar -xzf '$rel'" || { rec artifact.unpack fail "tar -xzf $rel failed"; exit 0; }
  dir=$(tar -tzf "$DL/$rel" | head -n 1 | cut -d/ -f1)
  if [ -x "$DL/$dir/setup.sh" ]; then
    rec artifact.has_setup pass "$rel unpacks to $dir/ with an executable setup.sh"
  elif [ -f "$DL/$dir/setup.sh" ]; then
    rec artifact.has_setup fail "$rel has setup.sh but it is not executable"
  else
    rec artifact.has_setup fail "$rel unpacks to $dir/ with no setup.sh: a stranger cannot follow the README's ./setup.sh"
  fi
  echo "DIR=$dir"
  ;;

setup_answers)
  # provider: the local fixture model (an OpenAI-compatible endpoint on this machine) with a made-up key from the
  # environment; sources: the bundled ones plus a local feed; narration and the daily brief off
  dir=$1
  key=$(cat "$T/fixture-key.txt")
  as_tester "cd $DL/$dir && $FIXENV OPENAI_API_KEY=$key ./setup.sh --answers $T/answers.toml" > /tmp/setup-answers.log 2>&1; rc=$?
  cp /tmp/setup-answers.log "$T/out/" 2>/dev/null
  if [ "$rc" = 0 ] && [ -x "$H/bin/composer" ]; then
    rec setup.answers pass "./setup.sh --answers (provider openai at the local fixture model, narration off) rc 0; $(tail_of /tmp/setup-answers.log 2)"
  else
    rec setup.answers fail "./setup.sh --answers rc $rc: $(tail_of /tmp/setup-answers.log 8)"; exit 0
  fi
  mode=$(stat -c %a "$H/data" 2>/dev/null)
  sec=$(find "$H/data" -name secrets.env | head -n 1)
  if grep -qF "$key" /tmp/setup-answers.log; then
    rec setup.data_private fail "setup printed the key"
  elif [ "$mode" = 700 ] && [ -n "$sec" ] && [ "$(stat -c %a "$sec")" = 600 ] && grep -qF "$key" "$sec"; then
    rec setup.data_private pass "data folder mode 700; the key (read once from OPENAI_API_KEY) is only in secrets.env, mode 600; setup never printed it"
  else
    rec setup.data_private fail "data folder mode $mode; secrets file: ${sec:-none} $( [ -n "$sec" ] && stat -c %a "$sec")"
  fi
  if grep -rqs "harbor/feed.xml" "$H/data" && grep -rqs "localhost:8443/blog/feed.xml" "$H/data"; then
    rec setup.add_feed pass "the answers file's [sources] add put both local feeds in: $(grep -m1 -i 'read [0-9]* items' /tmp/setup-answers.log | cut -c1-160)"
  else
    rec setup.add_feed fail "the feed in the answers file was not added: $(grep -i -m2 'not added\|feed' /tmp/setup-answers.log | tr '\n' ' ' | cut -c1-300)"
  fi
  ;;

doctor)
  home=$1; label=$2
  as_tester "$FIXENV $home/bin/composer doctor" > "/tmp/doctor-$label.log" 2>&1; rc=$?
  cp "/tmp/doctor-$label.log" "$T/out/" 2>/dev/null
  line=$(grep -E '^doctor: [0-9]+ passed' "/tmp/doctor-$label.log" | tail -n 1)
  fails=$(grep -E '^FAIL' "/tmp/doctor-$label.log" | head -n 5 | tr '\n' ' ')
  if [ "$rc" = 0 ] && [ -n "$line" ] && printf '%s' "$line" | grep -q ' 0 failed'; then
    rec "doctor.$label" pass "composer doctor rc 0: $line"
  else
    rec "doctor.$label" fail "composer doctor rc $rc: ${line:-no summary line} $fails"
  fi
  if feature article_parser; then
    if grep -qi "article parser" "/tmp/doctor-$label.log"; then
      rec "doctor.$label.article_parser" pass "$(grep -i 'article parser' "/tmp/doctor-$label.log" | head -n 1)"
    else
      rec "doctor.$label.article_parser" fail "this build has the optional article parser but doctor has no line for it"
    fi
  else
    rec "doctor.$label.article_parser" skip "this build has no optional article parser"
  fi
  if feature checker_model; then
    if grep -qiE '^(PASS|FAIL|SKIP) +checker' "/tmp/doctor-$label.log" || grep -qi " checker" "/tmp/doctor-$label.log"; then
      rec "doctor.$label.checker" pass "$(grep -i 'checker' "/tmp/doctor-$label.log" | head -n 1)"
    else
      rec "doctor.$label.checker" fail "this build has a separate checker model but doctor has no checker line"
    fi
  else
    rec "doctor.$label.checker" skip "this build has no separate checker model"
  fi
  ;;

feed_labels)
  # the labels setup gave the local feeds (setup names a feed after its host; a later build may use its title)
  find "$H/data" -name sources.json -print0 | xargs -0 -r cat | "$H/app/current/venv/bin/python" -I -c '
import json, sys
dec = json.JSONDecoder()
text, i = sys.stdin.read(), 0
while i < len(text):
    while i < len(text) and text[i].isspace():
        i += 1
    if i >= len(text):
        break
    doc, i = dec.raw_decode(text, i)
    for s in doc.get("sources", []):
        if ":8443/" in s.get("url", ""):
            print(s.get("label"))'
  ;;

provider)
  # provider none (what a stranger who skips the key gets) or back to the fixture model
  which=$1
  key=$(cat "$T/fixture-key.txt")
  as_tester "$FIXENV OPENAI_API_KEY=$key $H/bin/composer setup --reconfigure provider --answers $T/answers-provider-$which.toml" \
    > "/tmp/setup-provider-$which.log" 2>&1; rc=$?
  cp "/tmp/setup-provider-$which.log" "$T/out/" 2>/dev/null
  [ "$rc" = 0 ] || rec "setup.provider_$which" fail "setup --reconfigure provider ($which) rc $rc: $(tail_of "/tmp/setup-provider-$which.log" 6)"
  ;;

interactive)
  dir=$1
  key="fixture-typed-key-$(date +%s%N | sha256sum | cut -c1-16)"
  printf '%s\n' "$key" > /tmp/interactive-key
  as_tester "cd $DL/$dir && $FIXENV expect -f $T/setup.exp ./setup.sh $IH $key http://127.0.0.1:8790/v1 https://127.0.0.1:8443/blog/feed.xml" \
    > /tmp/setup-interactive.log 2>&1; rc=$?
  cp /tmp/setup-interactive.log "$T/out/" 2>/dev/null
  seen=$(grep -o 'EXPECT SAW [a-z_]*' /tmp/setup-interactive.log | awk '{print $3}' | sort -u | tr '\n' ' ')
  if [ "$rc" = 0 ] && [ -x "$IH/bin/composer" ]; then
    rec setup.interactive pass "interactive ./setup.sh driven by expect, rc 0; prompts answered: $seen"
  else
    rec setup.interactive fail "interactive ./setup.sh rc $rc; prompts answered: $seen; $(grep 'EXPECT FAIL' /tmp/setup-interactive.log | head -n 2 | tr '\n' ' ') $(tail_of /tmp/setup-interactive.log 4)"
  fi
  for want in provider key narration port; do
    if ! printf '%s' "$seen" | grep -qw "$want"; then
      rec setup.interactive.prompts fail "the interactive setup never asked about $want"; break
    fi
  done
  printf '%s' "$seen" | grep -qw port && printf '%s' "$seen" | grep -qw key && \
    rec setup.interactive.prompts pass "asked about: $seen"
  if grep -qF "$key" /tmp/setup-interactive.log; then
    rec setup.key_not_echoed fail "the typed key appears in the terminal output"
  elif grep -rqsF "$key" "$IH/data" --exclude=secrets.env; then
    rec setup.key_not_echoed fail "the typed key appears in a data file other than secrets.env"
  else
    sec=$(find "$IH/data" -name secrets.env | head -n 1)
    if [ -n "$sec" ] && [ "$(stat -c %a "$sec")" = 600 ] && grep -qF "$key" "$sec"; then
      rec setup.key_not_echoed pass "the typed key was not shown and is stored only in secrets.env (mode 600)"
    else
      rec setup.key_not_echoed fail "the typed key is not stored as promised (secrets.env: ${sec:-none})"
    fi
  fi
  if feature model_picklist; then
    tc=$(grep -m1 'test call' /tmp/setup-interactive.log | tr -d '\r' | sed 's/^ *//')
    if grep -q 'EXPECT SAW model_list' /tmp/setup-interactive.log; then lists="a model list was offered"
    else lists="no model list for an OpenAI-compatible endpoint (the Anthropic list is not exercised: it would call Anthropic)"; fi
    if printf '%s' "$tc" | grep -qiE 'work|answered|ok'; then
      rec setup.model_picklist pass "setup made one test call with the typed key: \"$tc\"; $lists"
    else
      rec setup.model_picklist fail "this build has the setup test call, but it did not succeed against the local model: \"${tc:-no test call shown}\"; $lists"
    fi
  else
    rec setup.model_picklist skip "this build has no model pick-list or test call at setup"
  fi
  ;;

interactive_cleanup)
  as_tester "$IH/bin/composer uninstall --delete-data --yes" > /tmp/uninstall-interactive.log 2>&1; rc=$?
  if [ "$rc" = 0 ] && [ ! -e "$IH" ]; then
    rec setup.interactive_removed pass "the interactive install removed itself completely (uninstall --delete-data --yes)"
  else
    rec setup.interactive_removed fail "uninstall --delete-data of the interactive install rc $rc; left: $(ls -A "$IH" 2>/dev/null | tr '\n' ' ')"
  fi
  ;;

no_internet)
  if curl -s -m 6 -o /dev/null https://pypi.org/simple/ 2>/dev/null; then
    rec env.no_internet fail "the container still reaches the internet; the use phase would not prove it works offline"
  else
    rec env.no_internet pass "no route out (https://pypi.org unreachable); the app's use phase runs with no internet"
  fi
  ;;

online)
  if curl -s -m 15 -o /dev/null https://pypi.org/simple/; then echo online; else echo offline; fi
  ;;

up_start)
  label=${1:-up}
  # its own session (setsid), so stopping its process group stops everything it started
  if curl -sf -o /dev/null http://127.0.0.1:8765/health; then
    rec "lifecycle.$label" fail "something already answers on 8765 before this start; the check would be meaningless"
    exit 0
  fi
  as_tester "cd $TH; $FIXENV setsid nohup $H/bin/composer up > /tmp/$label.log 2>&1 < /dev/null & echo \$! > /tmp/up.pid"
  ok=0
  for _ in $(seq 1 80); do curl -sf -o /dev/null http://127.0.0.1:8765/health && { ok=1; break; }; sleep 0.25; done
  sleep 1
  if [ "$ok" = 1 ] && ! kill -0 "$(cat /tmp/up.pid)" 2>/dev/null; then
    rec "lifecycle.$label" fail "something answered /health but the composer up just started has exited: $(tail_of /tmp/$label.log 4)"
  elif [ "$ok" = 1 ]; then
    rec "lifecycle.$label" pass "composer up: /health 200 $(curl -s http://127.0.0.1:8765/health | cut -c1-160)"
  else
    rec "lifecycle.$label" fail "composer up did not answer /health in 20 s: $(tail_of /tmp/$label.log 6)"
  fi
  ;;

up_stop)
  pid=$(cat /tmp/up.pid 2>/dev/null)
  if [ -n "$pid" ]; then
    kill -TERM -- "-$pid" 2>/dev/null
    for _ in $(seq 1 40); do kill -0 -- "-$pid" 2>/dev/null || break; sleep 0.25; done
    if kill -0 -- "-$pid" 2>/dev/null; then
      rec lifecycle.stop fail "composer up still running 10 s after TERM"
      kill -KILL -- "-$pid" 2>/dev/null
    fi
  fi
  for _ in $(seq 1 20); do curl -sf -o /dev/null http://127.0.0.1:8765/health || break; sleep 0.25; done
  if curl -sf -o /dev/null http://127.0.0.1:8765/health; then
    rec lifecycle.stop fail "the app still answers /health after it was stopped (pid file: ${pid:-none})"
  fi
  cp /tmp/up*.log /tmp/after_*.log /tmp/restart.log "$T/out/" 2>/dev/null
  ;;

saved)
  # the saved briefs on the shelf, one job id per line (GET /shelf is the index the page reads)
  curl -s http://127.0.0.1:8765/shelf | "$H/app/current/venv/bin/python" -I -c '
import json, sys
for row in json.load(sys.stdin).get("items", []):
    print(row.get("job"))'
  ;;

seed_saved)
  # one brief composed and saved through the engine's own routes (the same requests the page makes), so the lifecycle
  # checks have saved data even when the page's own Save is broken; prints the job id
  "$H/app/current/venv/bin/python" -I - "$@" <<'SEED'
import json, sys, time, urllib.request
base = "http://127.0.0.1:8765"
hdr = {"Content-Type": "application/json", "X-Composer-CSRF": "same-origin", "Origin": base}
def call(path, body=None):
    req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(), headers=hdr,
                                 method="GET" if body is None else "POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)
bundled = set(sys.argv[1:])
ids = [i for i in call("/data/options.json")["sources"] if i not in bundled]
job = call("/compose", {"sources": ids[:2], "lens": "what changed on the river this week", "insights": 3})["job"]
for _ in range(240):
    st = call(f"/status/{job}")
    if st.get("phase") in ("verified", "verification_failed") or st.get("state") == "failed":
        break
    time.sleep(0.5)
call(f"/save/{job}", {})
print(job)
SEED
  ;;

version)
  as_tester "$H/bin/composer --version" 2>&1
  ;;

update)
  wheel=$1
  as_tester "$H/bin/composer update --from-file $DL/b/$wheel" > /tmp/update.log 2>&1; rc=$?
  cp /tmp/update.log "$T/out/" 2>/dev/null
  if [ "$rc" = 0 ]; then
    rec lifecycle.update pass "composer update --from-file $wheel (SHA256SUMS next to it) rc 0: $(tail_of /tmp/update.log 2)"
  else
    rec lifecycle.update fail "composer update rc $rc: $(tail_of /tmp/update.log 6)"
  fi
  ;;

rollback)
  as_tester "$H/bin/composer rollback" > /tmp/rollback.log 2>&1; rc=$?
  cp /tmp/rollback.log "$T/out/" 2>/dev/null
  if [ "$rc" = 0 ]; then
    rec lifecycle.rollback pass "composer rollback rc 0: $(tail_of /tmp/rollback.log 2)"
  else
    rec lifecycle.rollback fail "composer rollback rc $rc: $(tail_of /tmp/rollback.log 6)"
  fi
  ;;

uninstall_while_running)
  if as_tester "$H/bin/composer uninstall" > /tmp/uninstall-running.log 2>&1; then
    rec lifecycle.uninstall_refused_while_running fail "uninstall ran while composer up was running"
  elif [ -x "$H/bin/composer" ]; then
    rec lifecycle.uninstall_refused_while_running pass "uninstall refused while the app runs: $(tail_of /tmp/uninstall-running.log 1)"
  else
    rec lifecycle.uninstall_refused_while_running fail "uninstall failed but still removed the launcher"
  fi
  ;;

uninstall_keep)
  before=$(find "$H/data" -type f | sort | xargs -r sha256sum | sha256sum | cut -c1-16)
  as_tester "$H/bin/composer uninstall" > /tmp/uninstall.log 2>&1; rc=$?
  cp /tmp/uninstall.log "$T/out/" 2>/dev/null
  left=$(ls -A "$H" 2>/dev/null | tr '\n' ' ')
  after=$(find "$H/data" -type f 2>/dev/null | sort | xargs -r sha256sum | sha256sum | cut -c1-16)
  if [ "$rc" = 0 ] && [ ! -e "$H/bin" ] && [ ! -e "$H/app" ] && [ "$before" = "$after" ]; then
    rec lifecycle.uninstall_keeps_data pass "uninstall rc 0: app removed, data byte-identical (left: $left)"
  else
    rec lifecycle.uninstall_keeps_data fail "uninstall rc $rc; left: $left; data hash before $before after $after"
  fi
  ;;

reinstall)
  dir=$1
  as_tester "cd $DL/$dir && $FIXENV OPENAI_API_KEY=$(cat "$T/fixture-key.txt") ./setup.sh --answers $T/answers.toml" > /tmp/reinstall.log 2>&1; rc=$?
  cp /tmp/reinstall.log "$T/out/" 2>/dev/null
  if [ "$rc" = 0 ] && [ -x "$H/bin/composer" ]; then
    rec lifecycle.reinstall pass "setup again on the kept data rc 0: $(tail_of /tmp/reinstall.log 2)"
  else
    rec lifecycle.reinstall fail "setup on the kept data rc $rc: $(tail_of /tmp/reinstall.log 6)"
  fi
  ;;

delete_data)
  as_tester "$H/bin/composer uninstall --delete-data --yes" > /tmp/delete.log 2>&1; rc=$?
  cp /tmp/delete.log "$T/out/" 2>/dev/null
  if [ "$rc" = 0 ] && [ ! -e "$H" ]; then
    rec lifecycle.delete_data pass "uninstall --delete-data --yes rc 0; the app folder is gone"
  else
    rec lifecycle.delete_data fail "uninstall --delete-data rc $rc; left: $(ls -A "$H" 2>/dev/null | tr '\n' ' ')"
  fi
  ;;

*)
  echo "unknown step $step" >&2; exit 2 ;;
esac
exit 0
