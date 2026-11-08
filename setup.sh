#!/bin/sh
# Lensmith Composer setup.
#
#   ./setup.sh                          ask the questions (provider and key, sources, narration, schedule, port)
#   ./setup.sh --answers answers.toml   no questions (see docs/setup.md)
#   ./setup.sh --yes                    no questions, every default
#   ./setup.sh --home DIR               another app folder (default ~/.lensmith-composer, or COMPOSER_HOME)
#   ./setup.sh --python-download        allow downloading a private Python if this computer has no 3.10+
#   ./setup.sh --no-test-call           skip the one tiny model call that checks each key and model id
#   ./setup.sh --reconfigure PART       ask one part again (provider, checker, sources, parser, narration, ...)
#
# What it does: checks everything first and writes nothing until every check passes. Then it makes ONE folder,
# finds Python 3.10+ (or, only if you say yes, downloads a pinned, checksum-verified uv into that folder, which
# installs its own Python there too), makes a private environment in it, installs Composer from this folder into
# that environment, and hands over to `composer setup` for the questions.
#
# What it never does: edit your shell profile or PATH, use sudo, apt, brew or pip --user, or write outside the
# app folder (every cache and temporary file is pointed inside it). It needs curl or wget, and CA certificates,
# only when it has to download Python.
set -eu
# Private from the first program it runs (Python's version checks write bytecode next to an existing install's code):
# nothing setup or what it starts makes may be writable by other accounts (the trust contract refuses that).
umask 077

UV_VERSION=0.5.29
PY_VERSION=3.12.9
NEED_KB=307200

# BEGIN fetchlib (the one copy: scripts/install/build_install.py puts it into install.sh too; keep it self-contained)
PROG=${COMPOSER_PROG:-setup.sh}
T0=${COMPOSER_T0:-$(date +%s)}
LOG=${COMPOSER_INSTALL_LOG:-}
FAILED=0
GOT=""
LAST_WHY=""
DEAD="|"
say() { printf '%s\n' "$*"; if [ -n "$LOG" ]; then printf '%s\n' "$*" >> "$LOG" 2>/dev/null || true; fi; }
elapsed() { e=$(( $(date +%s) - T0 )); printf '%d:%02d' $((e / 60)) $((e % 60)); }
# fail WHAT NEXT: the end of a run that cannot go on. Never a stack trace: what failed, the one next thing, the log.
fail() {
  FAILED=1
  { printf '\n%s: stopped.\n' "$PROG"
    printf '  What failed: %s\n' "$1"
    printf '  Next:        %s\n' "$2"
    [ -z "$LOG" ] || printf '  Log:         %s  (paste it if you ask for help; it holds no key)\n' "$LOG"
  } >&2
  if [ -n "$LOG" ]; then printf 'FAILED: %s | NEXT: %s\n' "$1" "$2" >> "$LOG" 2>/dev/null || true; fi
  exit 2
}
# need_tools: a download program (curl, else wget) and a SHA-256 program; sets FETCH and SHACMD.
need_tools() {
  [ -z "$FETCH" ] || [ -z "$SHACMD" ] || return 0
  if command -v curl >/dev/null 2>&1; then FETCH=curl
  elif command -v wget >/dev/null 2>&1; then FETCH=wget
  else fail "this computer has neither curl nor wget, so nothing can be downloaded" \
    "install Python 3.10 or newer yourself (python.org, or your package manager) and run Composer's ./setup.sh from a downloaded release, or install curl"; fi
  if command -v sha256sum >/dev/null 2>&1; then SHACMD="sha256sum"
  elif command -v shasum >/dev/null 2>&1; then SHACMD="shasum -a 256"
  elif command -v openssl >/dev/null 2>&1; then SHACMD="openssl dgst -sha256 -r"
  else fail "this computer has no sha256sum, shasum or openssl, so a download cannot be checked" \
    "install one of them (it ships with macOS and every Linux), then run this again"; fi
}
FETCH=""
SHACMD=""
sha_of() { $SHACMD "$1" | awk '{print $1}'; }
# fetch_one URL DEST [ACCEPT]: one try, a progress bar when this is a terminal. Sets LAST_WHY. Its own error text
# (curl's or wget's) is shown, never hidden.
fetch_one() {
  fo_url=$1; fo_dest=$2; fo_acc=${3:-}; fo_rc=0
  if [ "$FETCH" = curl ]; then
    if [ -t 2 ]; then fo_prog=--progress-bar; else fo_prog=--silent; fi
    if [ -n "$fo_acc" ]; then
      if fo_code=$(curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 $fo_prog --show-error \
          --connect-timeout "$CONNECT_S" --speed-limit 1000 --speed-time "$STALL_S" -H "Accept: $fo_acc" \
          -w '%{http_code}' -o "$fo_dest" "$fo_url"); then return 0; else fo_rc=$?; fi
    else
      if fo_code=$(curl --fail --location --proto '=https' --proto-redir '=https' --tlsv1.2 $fo_prog --show-error \
          --connect-timeout "$CONNECT_S" --speed-limit 1000 --speed-time "$STALL_S" \
          -w '%{http_code}' -o "$fo_dest" "$fo_url"); then return 0; else fo_rc=$?; fi
    fi
    case "$fo_code" in
      000|"") LAST_WHY="no answer, or it stalled" ;;
      2*) if [ "$fo_rc" = 28 ]; then LAST_WHY="no answer, it stalled for $STALL_S seconds"; else LAST_WHY="no answer, the download stopped part way"; fi ;;
      *) LAST_WHY="HTTP $fo_code" ;;
    esac
  else
    if [ -t 2 ]; then fo_prog=""; else fo_prog=-nv; fi
    wget --https-only --tries=1 --timeout="$STALL_S" $fo_prog ${fo_acc:+--header="Accept: $fo_acc"} -O "$fo_dest" "$fo_url" && return 0
    LAST_WHY="no answer, or the download failed"
  fi
  return 1
}
# A source that answered with a server error or nothing is skipped for the rest of the run (one outage, one note);
# a 404 only says this one file is not there.
mark_dead() { case "$LAST_WHY" in "HTTP 5"*|"no answer"*) DEAD="$DEAD$1|" ;; esac; }
is_dead() { case "$DEAD" in *"|$1|"*) return 0 ;; esac; return 1; }
# have_local ENVVAR NAME SHA SIZE_NOTE DESTDIR: a file the person gave us (the env var's path, or NAME in
# COMPOSER_FILES_DIR), used only if its SHA-256 is the pinned one. Sets GOT.
have_local() {
  [ -n "$3" ] && [ -d "${5:-}" ] || return 1   # a pin to check against, and a folder of ours to copy into
  hl_path=""
  if [ -n "$1" ]; then eval "hl_path=\${$1:-}"; fi
  if [ -z "$hl_path" ] && [ -n "${COMPOSER_FILES_DIR:-}" ] && [ -f "${COMPOSER_FILES_DIR%/}/$2" ]; then hl_path=${COMPOSER_FILES_DIR%/}/$2; fi
  [ -n "$hl_path" ] || return 1
  if [ ! -f "$hl_path" ]; then say "  $hl_path is not a file; ignoring it"; return 1; fi
  need_tools
  # The file is copied into a folder of ours and the COPY is checked and used: the original can change after it is
  # read (a shared folder, a slow disk) without the checked bytes changing.
  hl_copy=${5%/}/$2.yours
  rm -f -- "$hl_copy.part" "$hl_copy"
  if cp -- "$hl_path" "$hl_copy.part" 2>/dev/null && [ "$(sha_of "$hl_copy.part")" = "$3" ]; then
    mv -f -- "$hl_copy.part" "$hl_copy"; GOT=$hl_copy; say "  using your file $hl_path (its SHA-256 matches the pin)"; return 0
  fi
  rm -f -- "$hl_copy.part"
  say "  your file $hl_path does not match the pinned SHA-256, so it is not used"
  return 1
}
# fetch_pinned LABEL DEST SHA SOURCE...: SOURCE is "name|url" or "name|url|accept-header". Tries each in order; each
# download is checked against SHA before it is kept; a one-line note says every time it switches to the next one.
# Two rounds (a short wait between), so one blip does not cost the run. Returns 1 when none worked.
fetch_pinned() {
  fp_label=$1; fp_dest=$2; fp_sha=$3; shift 3
  [ -n "$fp_sha" ] || return 1
  need_tools
  fp_round=1; fp_max=${FP_ROUNDS:-2}
  while [ "$fp_round" -le "$fp_max" ]; do
    for fp_src in "$@"; do
      fp_name=${fp_src%%|*}; fp_rest=${fp_src#*|}; fp_url=${fp_rest%%|*}
      case "$fp_rest" in *'|'*) fp_acc=${fp_rest#*|} ;; *) fp_acc="" ;; esac
      [ -n "$fp_url" ] || continue
      case ",${COMPOSER_SKIP_SOURCES:-}," in *",$fp_name,"*) say "  (skipping $fp_name, as COMPOSER_SKIP_SOURCES asks)"; continue ;; esac
      if is_dead "$fp_name" && [ "$fp_round" = 1 ] && [ -z "${FP_FORCE:-}" ]; then continue; fi
      say "  downloading $fp_label from $fp_name"
      rm -f -- "$fp_dest.part"
      if fetch_one "$fp_url" "$fp_dest.part" "$fp_acc"; then
        if [ "$(sha_of "$fp_dest.part")" = "$fp_sha" ]; then mv -f -- "$fp_dest.part" "$fp_dest"; GOT=$fp_dest; return 0; fi
        rm -f -- "$fp_dest.part"
        say "  ! $fp_name sent a file that does not match its pinned SHA-256, so it was thrown away; trying the next source"
      else
        rm -f -- "$fp_dest.part"
        say "  ! $fp_name did not work for $fp_label ($LAST_WHY); trying the next source"
        mark_dead "$fp_name"
      fi
    done
    [ "$fp_round" -lt "$fp_max" ] || break
    say "  none of the sources worked; trying them all once more in ${COMPOSER_SETUP_RETRY_WAIT:-5} seconds"
    sleep "${COMPOSER_SETUP_RETRY_WAIT:-5}"
    fp_round=$((fp_round + 1))
  done
  return 1
}
# END fetchlib
# Numbered, visible steps: a person watching a slow connection can see where setup is and how many are left.
# Run by install.sh, the numbers continue after its step 1 and each line says how long the run has taken.
STEPS=${COMPOSER_STEPS:-7}
STEP_BASE=${COMPOSER_STEP_BASE:-0}
STEP_NOW=0
STEP_WHAT=""
step() {
  STEP_NOW=$(($1 + STEP_BASE)); STEP_WHAT=$2
  if [ -n "${COMPOSER_INSTALLER:-}" ]; then say ""; say "Step $STEP_NOW of $STEPS ($(elapsed) elapsed): $2"
  else say ""; say "Step $STEP_NOW of $STEPS: $2"; fi
}
# try3 WHAT COMMAND...: runs the command up to 3 times. Its own output (download progress, and the real error when
# it fails) is never hidden or captured. Returns 1 after the third failure.
try3() {
  t3_what=$1; shift; t3_n=1
  while :; do
    if "$@"; then return 0; fi
    [ "$t3_n" -lt 3 ] || return 1
    say "  $t3_what did not work (attempt $t3_n of 3); trying again in ${COMPOSER_SETUP_RETRY_WAIT:-5} seconds"
    sleep "${COMPOSER_SETUP_RETRY_WAIT:-5}"
    t3_n=$((t3_n + 1))
  done
}
die() { FAILED=1; printf 'setup.sh: %s\n' "$*" >&2; if [ -n "$LOG" ]; then printf 'FAILED: %s\n' "$*" >> "$LOG" 2>/dev/null || true; fi; exit 2; }
has_tty() { (: < /dev/tty) 2>/dev/null; }
# The folders setup and Composer make in the app folder must be real folders: a symbolic link planted there could
# send a write or a removal outside it. The only link allowed is app/current, naming a real version folder beside it.
# Prints why not and returns 1; prints nothing and returns 0 when every one is a real folder (or not there yet).
owned_ok() {
  for n in bin app python bootstrap narration models cache tmp narration/venv models/kokoro; do
    if [ -L "$H/$n" ]; then say "$H/$n is a symbolic link"; return 1; fi
    if [ -e "$H/$n" ] && [ ! -d "$H/$n" ]; then say "$H/$n is not a folder"; return 1; fi
  done
  [ -d "$H/app" ] || return 0
  for p in "$H/app"/* "$H/app"/.[!.]*; do
    [ -e "$p" ] || [ -L "$p" ] || continue
    case "${p##*/}" in
      current|.current.tmp)
        t=$(readlink "$p" 2>/dev/null || true)
        case "$t" in ""|.*|*/*) say "$p must be a link to a version folder beside it"; return 1 ;; esac
        if [ ! -d "$H/app/$t" ] || [ -L "$H/app/$t" ]; then say "$p must be a link to a version folder beside it"; return 1; fi ;;
      *)
        if [ -L "$p" ]; then say "$p is a symbolic link"; return 1; fi
        if [ -L "$p/venv" ]; then say "$p/venv is a symbolic link"; return 1; fi ;;
    esac
  done
  tree_ok
}
# The trust contract all the way down: every folder, file and link in the app folder must belong to you or root, and
# no folder or file in it may be writable by group or others. An existing install is checked, never adopted as it is.
tree_ok() {
  [ -d "$H" ] || return 0
  nl='
'
  bad=$(find "$H" ! -user "$(id -u)" ! -user 0 -print) || { say "$H cannot be checked all the way down"; return 1; }
  if [ -n "$bad" ]; then say "${bad%%"$nl"*} belongs to another account; fix: chown -R $(id -un) $H"; return 1; fi
  bad=$(find "$H" ! -type l \( -perm -020 -o -perm -002 \) -print) || { say "$H cannot be checked all the way down"; return 1; }
  if [ -n "$bad" ]; then say "${bad%%"$nl"*} can be written by other accounts; fix: chmod -R go-w $H"; return 1; fi
  return 0
}
check_owned() {
  why=$(owned_ok) || die "refused: $why. Setup works only in its own real folders that no other account can change, so nothing was written or removed. Fix that (or remove the link) and run it again."
}
# The trust contract (SECURITY.md): the app folder and every folder above it, up to /, on the path as given and on
# its real path, must belong to you or root and be writable by no one else, and the path as given may not go through
# a symbolic link. Checks the nearest existing folder.
trust_one() {  # trust_one FOLDER: prints why not, returns 1
  set -- "$1" "$(ls -ldn -- "$1" 2>/dev/null)"
  [ -n "$2" ] || { say "$1 cannot be checked"; return 1; }
  mode=$(printf '%s' "$2" | awk '{print substr($1, 1, 10)}'); owner=$(printf '%s' "$2" | awk '{print $3}')
  if [ "$owner" != "$(id -u)" ] && [ "$owner" != 0 ]; then say "$1 belongs to another account (uid $owner); fix: chown $(id -un) $1"; return 1; fi
  case "$mode" in
    *[tT]) case "$mode" in ?????w*|????????w*) say "$1 is a folder shared by every account ($mode); put the app folder in a folder of your own instead: ./setup.sh --home DIR"; return 1 ;; esac ;;
    ?????w*|????????w*)
      fs=$(stat -f -c %T -- "$1" 2>/dev/null || true)  # GNU stat; elsewhere this prints nothing
      case "$fs" in
        msdos|vfat|fat|exfat|fuseblk|ntfs|ntfs3|cifs|smb2|smb3|*0x2011bab0*)
          say "$1 can be written by other accounts ($mode): it is on a $fs filesystem, which has no permission bits of its own, so chmod has no effect there; put the app folder on a POSIX filesystem (./setup.sh --home DIR), or mount that disk with uid=$(id -u),dmask=077,fmask=177"; return 1 ;;
      esac
      say "$1 can be written by other accounts ($mode); fix: chmod go-w $1"; return 1 ;;
  esac
  return 0
}
trust_ok() {
  d=$H
  while [ ! -e "$d" ] && [ ! -L "$d" ] && [ "$d" != / ]; do d=$(dirname "$d"); done
  # no symbolic link on the way: the folders a link leads through are on neither path, so they would go unchecked
  p=$d
  while :; do
    if [ -L "$p" ]; then say "$p is a symbolic link; give the real path instead: ./setup.sh --home $(cd "$d" 2>/dev/null && pwd -P)${H#"$d"}"; return 1; fi
    [ "$p" = / ] && break
    p=$(dirname "$p")
  done
  for start in "$d" "$(cd "$d" 2>/dev/null && pwd -P)"; do
    [ -n "$start" ] || continue
    p=$start
    while :; do
      trust_one "$p" || return 1
      [ "$p" = / ] && break
      p=$(dirname "$p")
    done
  done
  return 0
}
check_trust() {
  why=$(trust_ok) || die "refused: $why. Composer's folder and every folder above it must be writable only by you (or root), so no other account can change what it runs; or put the app folder in a folder of your own: ./setup.sh --home DIR. Nothing was written."
}

H=${COMPOSER_HOME:-${HOME:-}/.lensmith-composer}
ANSWERS=""
YES=0
PYDL=0
PKGOK=0
NOTEST=""
RECONF=""
while [ $# -gt 0 ]; do
  case "$1" in
    --home) [ $# -ge 2 ] || die "--home needs a folder"; H=$2; shift 2 ;;
    --answers) [ $# -ge 2 ] || die "--answers needs a file"; ANSWERS=$2; shift 2 ;;
    --yes) YES=1; shift ;;
    --python-download) PYDL=1; shift ;;
    --install-python-pkg) PKGOK=1; shift ;;
    --no-test-call) NOTEST=--no-test-call; shift ;;
    --reconfigure) [ $# -ge 2 ] || die "--reconfigure needs a part, such as provider"
      case "$2" in *[!a-z]*|"") die "--reconfigure takes a part name such as provider" ;; esac
      RECONF="$RECONF $2"; shift 2 ;;
    -h|--help) sed -n '2,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "unknown option $1 (see ./setup.sh --help)" ;;
  esac
done

# Model keys and the server pass phrase are for Composer's own setup step only (its check and its run, below): no
# other program setup.sh starts (Python discovery, uv, venv, pip and the build backends pip runs, version checks)
# gets them. They are taken out of the environment here and handed back only to `composer setup`.
HELD=""
for k in ANTHROPIC_API_KEY OPENAI_API_KEY COMPOSER_CHECKER_API_KEY COMPOSER_SERVER_PASS; do
  # a variable of the holding name handed in by the caller would stay exported (and so reach every program run
  # below) once it holds the key: it is removed first, so the holding variable is this script's alone
  unset "held_$k"
  if eval "[ -n \"\${$k+x}\" ]"; then eval "held_$k=\$$k"; HELD="$HELD $k"; unset "$k"; fi
done
with_keys() { ( for k in $HELD; do eval "export $k=\"\$held_$k\""; done; exec "$@" ) }

# Where downloads may come from, in the order they are tried, and how long a stalled one may sit. Every source is
# only a place to fetch a file from: each file is checked against a SHA-256 pinned in this release before it is used.
STALL_S=${COMPOSER_STALL_SECONDS:-30}      # a download moving slower than 1 KB/s for this long is dropped, next source
CONNECT_S=${COMPOSER_CONNECT_SECONDS:-15}
MIRROR=${COMPOSER_MIRROR_URL:-https://lensmith.ai/composer/mirror}
MIRROR=${MIRROR%/}
PYPI_INDEX=${COMPOSER_PYPI_INDEX:-https://pypi.org/simple/}

# The release's own files (set by install.sh in a pins file; absent when you run ./setup.sh from a checkout, which
# installs from that folder as before). The file is read, never run: only lines NAME=value with plain characters.
PINS=${COMPOSER_PINS:-}
pin() {  # pin NAME: its value, or nothing
  [ -n "$PINS" ] && [ -f "$PINS" ] || return 0
  sed -n "s/^$1=\([A-Za-z0-9._:\/+%@-]*\)\$/\1/p" "$PINS" | head -n 1
}

SRC=$(cd "$(dirname "$0")" && pwd)
[ -f "$SRC/pyproject.toml" ] && [ -d "$SRC/composer" ] || die "run this from a Composer folder (it installs that folder)"
VERSION=$(sed -n 's/^version = "\([0-9][0-9A-Za-z.+_-]*\)"$/\1/p' "$SRC/pyproject.toml" | head -n 1)
[ -n "$VERSION" ] || die "cannot read the version from pyproject.toml"
KIT=0
if [ -n "$PINS" ]; then
  [ -f "$PINS" ] || die "the release's pins file $PINS is missing; run the install command again"
  [ "$(pin PIN_VERSION)" = "$VERSION" ] || die "the release's pins are for Composer $(pin PIN_VERSION), but this folder is $VERSION; run the install command again"
  KIT=1
fi

# ---------------------------------------------------------------------------------------- checks (read only)
say "Lensmith Composer $VERSION setup"
step 1 "checking this computer and the app folder (nothing is written yet)"
case "$H" in /*) ;; *) die "the app folder must be an absolute path, not $H" ;; esac
while [ "${H%/}" != "$H" ] && [ "$H" != "/" ]; do H=${H%/}; done
case "$H" in */../*|*/..|*/./*|*/.) die "give the app folder without . or .. parts: $H" ;; esac
[ "$H" != "/" ] || die "refused: / is not an app folder"
if [ -n "${HOME:-}" ]; then
  [ "$H" != "${HOME%/}" ] || die "refused: $H is your home folder; pick a folder of its own"
  case "${HOME%/}/" in "$H"/*) die "refused: $H contains your home folder" ;; esac
fi
[ ! -L "$H" ] || die "refused: $H is a symbolic link; give the real folder"
check_trust
if [ -e "$H" ]; then
  [ -d "$H" ] || die "refused: $H exists and is not a folder"
  [ -r "$H" ] || die "refused: you cannot read $H"
  LISTING=$(ls -A "$H") || die "refused: cannot list $H"
  if [ -n "$LISTING" ]; then
    if [ -f "$H/.composer-home" ] && [ ! -L "$H/.composer-home" ] && \
       [ "$(cat "$H/.composer-home")" = "lensmith-composer home v1" ]; then
      if [ -f "$H/install-manifest.json" ] && \
         ! grep -Fq "\"home\": \"$H\"" "$H/install-manifest.json"; then
        die "refused: $H holds a Composer install made for another folder (moved or copied). Nothing was written."
      fi
      # A run of this script that stopped in the middle of making its version folder leaves a marker beside it
      # (app/.making-VERSION, a file this script wrote). The half-made folder named by that marker, and only that
      # one, is removed here, so a rerun starts clean instead of dying on what the last run left.
      for n in bin app python bootstrap narration models cache tmp; do
        [ ! -L "$H/$n" ] || die "refused: $H/$n is a symbolic link. Setup works only in its own real folders, so nothing was written or removed. Remove the link and run it again."
      done
      mk=$H/app/.making-$VERSION
      if [ -f "$mk" ] && [ ! -L "$mk" ]; then
        left=$H/app/$VERSION
        if [ -d "$left" ] && [ ! -L "$left" ] && [ "$(readlink "$H/app/current" 2>/dev/null)" != "$VERSION" ]; then
          other=$(find "$left" ! -user "$(id -u)" -print 2>/dev/null | head -n 1)
          [ -z "$other" ] || die "refused: $other belongs to another account, so the half-made $left was not removed; fix: chown -R $(id -un) $left"
          say "  an earlier setup stopped in the middle of making $left; removing that half-made folder first"
          chmod -R u+w -- "$left"
          rm -rf -- "$left"
        fi
        rm -f -- "$mk"
      fi
      check_owned
      STATE=ours
    else
      die "refused: $H already holds files that are not a Composer install. Nothing was written. Pick an empty or new folder with --home."
    fi
  else
    STATE=empty
  fi
  [ -w "$H" ] || die "refused: you cannot write to $H"
  PARENT=$H
else
  PARENT=$(dirname "$H")
  [ -d "$PARENT" ] || die "refused: the folder above it, $PARENT, does not exist"
  [ -w "$PARENT" ] || die "refused: you cannot create folders in $PARENT. Nothing was written. Give a folder you can write to: ./setup.sh --home DIR (with the installer: sh -s -- --home DIR)"
  STATE=new
fi
if [ -n "$ANSWERS" ]; then
  [ -f "$ANSWERS" ] && [ -r "$ANSWERS" ] || die "cannot read the answers file $ANSWERS"
  case "$ANSWERS" in /*) ;; *) ANSWERS=$(pwd)/$ANSWERS ;; esac
  if grep -Eq '^[[:space:]]*python_download[[:space:]]*=[[:space:]]*true' "$ANSWERS"; then PYDL=1; fi
fi
[ "$YES" = 1 ] && PYDL=1

PY=""
PYVER=""
WHYNOT=""
# consider PROGRAM: is this a usable Python (3.10 or newer, with venv and ensurepip)? Sets PY and PYVER if so;
# otherwise records why not (only the first two, so a long PATH stays readable).
consider() {
  p=$(command -v "$1" 2>/dev/null || true)
  [ -n "$p" ] || return 1
  # macOS without the Command Line Tools has a /usr/bin/python3 that opens an install dialog when run: not run
  case "$p" in /usr/bin/python3|/usr/bin/python3.*)
    if [ "$(uname -s)" = Darwin ] && ! xcode-select -p >/dev/null 2>&1; then return 1; fi ;; esac
  v=$("$p" -I -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || true)
  if "$p" -I -c 'import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    PY=$p; PYVER=$v; return 0
  fi
  if [ -z "$v" ]; then
    reason="Found $1 at $p, but it does not run."
  elif "$p" -I -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    reason="Found $1 $v at $p, but it has no venv module (on Debian or Ubuntu: apt install python3-venv)."
  else
    reason="Found $1 $v at $p; Composer needs 3.10 or newer."
  fi
  [ "$(printf '%s' "$WHYNOT" | grep -c .)" -ge 2 ] || WHYNOT="${WHYNOT:+$WHYNOT
}$reason"
  return 1
}
find_python() {
  for cand in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
    consider "$cand" && return 0
  done
  # where Homebrew and python.org put theirs, when they are not on PATH (COMPOSER_PYTHON_PATH_ONLY=1 skips this, so the
  # tests' fake PATH is the whole search even where a real Python lives in /usr/local/bin)
  [ -z "${COMPOSER_PYTHON_PATH_ONLY:-}" ] || return 1
  for minor in 14 13 12 11 10; do
    for cand in "/""opt""/homebrew/bin/python3.$minor" /usr/local/bin/python3.$minor \
                /Library/Frameworks/Python.framework/Versions/3.$minor/bin/python3; do
      [ -x "$cand" ] || continue
      consider "$cand" && return 0
    done
  done
  return 1
}
find_python || true
step 2 "looking for Python 3.10 or newer (Composer runs on it)"
[ -z "$PY" ] || say "  found Python $PYVER at $PY"

# What this computer can download (the sources and pins for each kind of computer; every file is checked).
UV_GH_ID=""; UV_WHEEL_URL=""; UV_WHEEL_SHA=""; PY_ASSET=""; PY_SHA=""; PY_GH_ID=""
PBS_TAG=20250205
PKG_URL=""; PKG_SHA=""
if [ -z "$PY" ]; then
  if [ -n "$WHYNOT" ]; then say "$WHYNOT"; else say "No python3 was found on this computer."; fi
  say "So there is no usable Python 3.10 or newer here, and Composer needs one."
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) UV_ASSET=uv-x86_64-unknown-linux-gnu; UV_SHA=46d3fcf04d64be42bded914d648657cd62d968172604e3aaf8386142c09d2317 ;;
    Linux-aarch64|Linux-arm64) UV_ASSET=uv-aarch64-unknown-linux-gnu; UV_SHA=d1f716e8362d7da654a154b8331054a987c1fc16562bd719190a42458e945785 ;;
    Darwin-arm64) UV_ASSET=uv-aarch64-apple-darwin; UV_SHA=c89e96bde40402cc4db2f59bcb886882ab69e557235279283a2db9dea61135c3 ;;
    Darwin-x86_64) UV_ASSET=uv-x86_64-apple-darwin; UV_SHA=2f13ef5a82b91ba137fd6441f478c406a0a8b0df41e9573d1e61551a1de5a3a2 ;;
    *) die "install Python 3.10 or newer yourself (python.org, or your package manager), then run this again" ;;
  esac
  # the other places the same files live: GitHub download API (works when its release-download address is down),
  # PyPI's uv wheel (carries the same program), and python-build-standalone's Python for uv to install
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64)
      UV_GH_ID=226708878; UV_WHEEL_SHA=02ceda14892816f7db3d7d1a4a69b299817b54749036af1125ec73d8f570b52a
      UV_WHEEL_URL=https://files.pythonhosted.org/packages/9f/e6/8f3889348a753ec986eafbadd45e4587a119ebdf35f659e5e8478a46e0dd/uv-0.5.29-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
      PY_ASSET=cpython-3.12.9+20250205-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz; PY_GH_ID=226610613
      PY_SHA=31c8314b3e0fd51f0f72cad5c1c8bd107bce381b03288fe77513ed8958b199c1 ;;
    Linux-aarch64|Linux-arm64)
      UV_GH_ID=226708838; UV_WHEEL_SHA=345f14af3944b67f1622b080fc037fa1276f921b1a8ffbe19d4c5b5e9a19a3b0
      UV_WHEEL_URL=https://files.pythonhosted.org/packages/6b/9e/0f095eb42a647b88604675e26ff15adb95ec2de8e0023cc44ce75408b91e/uv-0.5.29-py3-none-manylinux_2_17_aarch64.manylinux2014_aarch64.musllinux_1_1_aarch64.whl
      PY_ASSET=cpython-3.12.9+20250205-aarch64-unknown-linux-gnu-install_only_stripped.tar.gz; PY_GH_ID=226609975
      PY_SHA=cf30149c1d090214b6070813f9b298533c5c37a255ed0d4a38ed34736da907c4 ;;
    Darwin-arm64)
      UV_GH_ID=226708833; UV_WHEEL_SHA=25f12457e0898313aed2705effb53118af542bd9825a4de2214a324ddd9bf8d7
      UV_WHEEL_URL=https://files.pythonhosted.org/packages/0b/9e/fcdd09fff5372322ee8d1d17a1bc4ea63808d1b026b4508b9ecbbdc9cc95/uv-0.5.29-py3-none-macosx_11_0_arm64.whl
      PY_ASSET=cpython-3.12.9+20250205-aarch64-apple-darwin-install_only_stripped.tar.gz; PY_GH_ID=226609966
      PY_SHA=aa379cd48e23ca84af06567048dca016665d8b43e850a823be26570bd7cfabe1 ;;
    Darwin-x86_64)
      UV_GH_ID=226708873; UV_WHEEL_SHA=b307438a5e2df313a9ea5446d6e5af99a9b57a363fc5e68a434ef2d89cde083b
      UV_WHEEL_URL=https://files.pythonhosted.org/packages/e7/f7/a2d80425b22b424de0d363b0dabc137446d46297a1f7e549d7683739bc38/uv-0.5.29-py3-none-macosx_10_12_x86_64.whl
      PY_ASSET=cpython-3.12.9+20250205-x86_64-apple-darwin-install_only_stripped.tar.gz; PY_GH_ID=226610558
      PY_SHA=22d4c03830045fe6f9ed94d9fa69d5ec7c2796b38814e92dd1d83bb9a7222530 ;;
  esac
  # python.org's installer for macOS (the same Python 3.12.9 for every Mac); its SHA-256 was taken from python.org's
  # file on 2026-11-08. A Mac also checks the signature: pkgutil --check-signature must name the Python Software Foundation.
  case "$(uname -s)" in Darwin) PKG_URL=https://www.python.org/ftp/python/3.12.9/python-3.12.9-macos11.pkg
                               PKG_SHA=cca03f4d7ed77e93074d64936435d56d1f329870240cdb1ef0fd8e37cdaae8a0 ;; esac
  need_tools
  if [ "$PYDL" != 1 ]; then
    say "Setup can download uv $UV_VERSION (about 16 MB, checked against a pinned SHA-256) into $H/bootstrap,"
    say "and Python $PY_VERSION through it into $H/python (about 40 MB). Nothing goes anywhere else."
    reply=""
    if has_tty; then printf 'Download them? [y/N]: '; read -r reply < /dev/tty || reply=""; fi
    case "$reply" in y|Y|yes) PYDL=1 ;; esac
  fi
  [ "$PYDL" = 1 ] || die "no Python downloaded. Install Python 3.10+ (python.org, brew install python, or apt install python3 python3-venv), then run ./setup.sh again"
  NEED_KB=$((NEED_KB + 204800))
fi
if [ "$STATE" = ours ]; then
  # An existing install: setup.sh never changes its version (that is `composer update`, which is journaled and
  # undoable) and never replaces a broken environment by itself.
  CUR=$(readlink "$H/app/current" 2>/dev/null || true)
  if [ -n "$CUR" ] && [ "$CUR" != "$VERSION" ]; then
    die "$H runs Composer $CUR; this folder is $VERSION. Change versions with: $H/bin/composer update --from-file <release> (nothing was written)"
  fi
  if [ -e "$H/app/$VERSION" ] && ! "$H/app/$VERSION/venv/bin/composer" --version >/dev/null 2>&1; then
    die "the environment in $H/app/$VERSION does not start; run $H/bin/composer uninstall (your data stays), then ./setup.sh again (nothing was written)"
  fi
fi
if [ -n "$PY" ]; then
  # Preflight with this folder's own code: the answers, the key variable, the port and the folder are all checked
  # before anything is written (no bytecode is written either).
  set -- setup --home "$H" --check-only
  [ -n "$ANSWERS" ] && set -- "$@" --answers "$ANSWERS"
  [ "$YES" = 1 ] && set -- "$@" --yes
  (cd "$SRC" && export PYTHONDONTWRITEBYTECODE=1 PYTHONNOUSERSITE=1 && with_keys "$PY" -m composer "$@") || \
    die "the checks above failed; nothing was written"
fi
FREE_KB=$(df -Pk "$PARENT" | awk 'NR==2 {print $4}')
[ "${FREE_KB:-0}" -ge "$NEED_KB" ] || die "refused: $((FREE_KB / 1024)) MB free next to $H; setup needs $((NEED_KB / 1024)) MB"

# ---------------------------------------------------------------------------------------- writes
# Every write is inside $H. If anything below fails on a fresh folder, the paths made here are removed again.
cleanup() {
  status=$?
  if [ "$status" != 0 ]; then
    case "$status" in
      130|143|129) say "" >&2; say "setup.sh: stopped by you (Ctrl-C or a closed window) during step $STEP_NOW" >&2 ;;
      *) if [ "$FAILED" != 1 ]; then
           say "" >&2
           say "setup.sh: stopped unexpectedly during step $STEP_NOW (${STEP_WHAT:-starting}); the message above, if any, is the program's own." >&2
           say "  Next: run the same command again; if it stops here again, send the log${LOG:+ ($LOG)} or this screen." >&2
         fi ;;
    esac
    # what this run made in the version folder may have come out group-writable (python.org's venv templates are)
    if [ "$MADE_VERSION" = 1 ]; then chmod -R go-w -- "$H/app/$VERSION" 2>/dev/null || true; fi
    if ! why=$(owned_ok); then
      say "setup.sh: stopped; nothing it made was removed, because $why" >&2
      return
    fi
    if [ "$MADE_VERSION" = 1 ] && [ "$(readlink "$H/app/current" 2>/dev/null)" != "$VERSION" ]; then
      rm -rf -- "$H/app/$VERSION"
      rm -f -- "$H/app/.making-$VERSION"
    fi
    if [ "$STATE" != ours ] && [ ! -e "$H/data" ]; then
      rm -rf -- "$H/bootstrap" "$H/python" "$H/app" "$H/cache" "$H/tmp" "$H/bin"
      rm -f -- "$H/.composer-home" "$H/install-manifest.json"
      if [ "$STATE" = new ]; then rmdir -- "$H" 2>/dev/null || true; fi
      say "setup.sh: stopped; what it had made in $H was removed again" >&2
    fi
  fi
}
MADE_VERSION=0
trap cleanup EXIT
# Ctrl+C (or a closed window) during a long download must clean up too: some shells skip the EXIT trap on a signal
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

umask 077
check_trust
mkdir -p -- "$H"
check_owned  # again at the writes: the checks above may have taken a while
[ -e "$H/.composer-home" ] || printf 'lensmith-composer home v1\n' > "$H/.composer-home"
mkdir -p -- "$H/cache" "$H/tmp" "$H/app"
check_owned
export TMPDIR="$H/tmp" PIP_CACHE_DIR="$H/cache/pip" UV_CACHE_DIR="$H/cache/uv" UV_PYTHON_INSTALL_DIR="$H/python" \
  XDG_CACHE_HOME="$H/cache/xdg" XDG_CONFIG_HOME="$H/cache/xdg-config" XDG_DATA_HOME="$H/cache/xdg-data" \
  HF_HOME="$H/cache/hf" PYTHONPYCACHEPREFIX="$H/cache/pycache" PIP_REQUIRE_VIRTUALENV=1 PIP_CONFIG_FILE=/dev/null \
  PYTHONNOUSERSITE=1 PIP_DISABLE_PIP_VERSION_CHECK=1 UV_NO_CONFIG=1 UV_PYTHON_PREFERENCE=only-managed \
  COMPOSER_HOME="$H"
# A slow connection (the Python download alone is about 40 MB) must not fail on uv's 30 second default or pip's 15:
# generous timeouts unless you set your own (UV_HTTP_TIMEOUT=600 sh setup.sh).
: "${UV_HTTP_TIMEOUT:=300}" "${PIP_DEFAULT_TIMEOUT:=120}" "${PIP_RETRIES:=5}"
export UV_HTTP_TIMEOUT PIP_DEFAULT_TIMEOUT PIP_RETRIES

# ---- uv: the small program that installs a private Python. Sources, in order: your own file, GitHub's release
# address, GitHub download API (answers when the release address is down), PyPI's uv wheel (carries the same
# program), our mirror. Each file is checked against the pinned SHA-256 before anything in it runs.
uv_check() {  # the unpacked uv must run and be the pinned version
  chmod -R go-w -- "$H/bootstrap"
  [ -x "$H/bootstrap/uv" ] && [ "$("$H/bootstrap/uv" --version 2>/dev/null | awk '{print $2}')" = "$UV_VERSION" ]
}
uv_unpack_tar() {
  rm -f -- "$H/bootstrap/uv" "$H/bootstrap/uvx"
  tar -xzf "$1" --no-same-owner -C "$H/bootstrap" --strip-components=1 || return 1
  uv_check
}
can_unpack_wheel() {
  command -v unzip >/dev/null 2>&1 && return 0
  tar --version 2>/dev/null | grep -qi bsdtar && return 0
  [ -n "$(command -v python3 || command -v python || true)" ]
}
uv_unpack_wheel() {  # a wheel is a zip file; the program is uv-VERSION.data/scripts/uv inside it
  d=$H/cache/dl/uvwheel
  mkdir -p -- "$d"
  if command -v unzip >/dev/null 2>&1; then unzip -q -o -j "$1" 'uv-*.data/scripts/uv' -d "$d" || return 1
  elif tar --version 2>/dev/null | grep -qi bsdtar; then tar -xf "$1" -C "$d" --strip-components=2 'uv-*.data/scripts/uv' || return 1
  else
    zp=$(command -v python3 || command -v python || true)
    [ -n "$zp" ] || return 1
    "$zp" -I -c 'import sys, zipfile, shutil
z = zipfile.ZipFile(sys.argv[1])
n = [m for m in z.namelist() if m.endswith(".data/scripts/uv")]
shutil.copyfileobj(z.open(n[0]), open(sys.argv[2], "wb"))' "$1" "$d/uv" || return 1
  fi
  [ -f "$d/uv" ] || return 1
  rm -f -- "$H/bootstrap/uv"
  cp -- "$d/uv" "$H/bootstrap/uv" && chmod 755 "$H/bootstrap/uv" && uv_check
}
get_uv() {
  mkdir -p -- "$H/bootstrap" "$H/cache/dl"
  dl=$H/cache/dl
  if have_local COMPOSER_UV_TARBALL "$UV_ASSET.tar.gz" "$UV_SHA" "" "$H/cache/dl"; then
    if uv_unpack_tar "$GOT"; then return 0; fi
    say "  ! that file did not unpack to a working uv; trying the other sources"
  fi
  g=1; FP_ROUNDS=1
  while [ "$g" -le 2 ]; do
    [ "$g" = 1 ] || FP_FORCE=1
    if fetch_pinned "uv $UV_VERSION" "$dl/uv.tar.gz" "$UV_SHA" \
        "github.com|https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$UV_ASSET.tar.gz" \
        "GitHub download API|https://api.github.com/repos/astral-sh/uv/releases/assets/$UV_GH_ID|application/octet-stream" \
        && uv_unpack_tar "$dl/uv.tar.gz"; then unset FP_ROUNDS FP_FORCE; return 0; fi
    if ! can_unpack_wheel; then
      [ "$g" != 1 ] || say "  (PyPI's uv wheel is skipped: nothing here can unpack a zip file: no unzip, bsdtar or python)"
    elif fetch_pinned "uv $UV_VERSION (as PyPI's wheel, which carries the same program)" "$dl/uv.whl" "$UV_WHEEL_SHA" \
        "PyPI|$UV_WHEEL_URL"; then
      if uv_unpack_wheel "$dl/uv.whl"; then unset FP_ROUNDS FP_FORCE; return 0; fi
      say "  ! PyPI's wheel checked out but did not unpack to a working uv; trying the next source"
    fi
    if fetch_pinned "uv $UV_VERSION" "$dl/uv.tar.gz" "$UV_SHA" \
        "our mirror|$MIRROR/uv/$UV_ASSET.tar.gz" && uv_unpack_tar "$dl/uv.tar.gz"; then unset FP_ROUNDS FP_FORCE; return 0; fi
    [ "$g" -lt 2 ] || break
    say "  no source gave uv; one more round in ${COMPOSER_SETUP_RETRY_WAIT:-5} seconds"
    sleep "${COMPOSER_SETUP_RETRY_WAIT:-5}"
    g=$((g + 1))
  done
  unset FP_ROUNDS FP_FORCE
  return 1
}

# ---- Python itself (python-build-standalone, which uv installs). We fetch the pinned file first, with the same
# kind of source list, and hand it to uv as a folder on this computer; uv then installs from it without the network.
PBS_FROM=""
get_pbs() {
  PBS_FROM=""
  case "$H" in *[!A-Za-z0-9/._-]*) return 1 ;; esac  # a folder name uv could not be given as an address
  pdir=$H/cache/pbs/$PBS_TAG
  mkdir -p -- "$pdir"
  enc=$(printf '%s' "$PY_ASSET" | sed 's/+/%2B/g')
  if have_local COMPOSER_PYTHON_TARBALL "$PY_ASSET" "$PY_SHA" "" "$pdir"; then
    mv -f -- "$GOT" "$pdir/$PY_ASSET" && PBS_FROM=$H/cache/pbs && return 0
  fi
  if fetch_pinned "Python $PY_VERSION" "$pdir/$PY_ASSET" "$PY_SHA" \
      "github.com|https://github.com/astral-sh/python-build-standalone/releases/download/$PBS_TAG/$enc" \
      "GitHub download API|https://api.github.com/repos/astral-sh/python-build-standalone/releases/assets/$PY_GH_ID|application/octet-stream" \
      "npmmirror.com|https://registry.npmmirror.com/-/binary/python-build-standalone/$PBS_TAG/$enc" \
      "our mirror|$MIRROR/python-build-standalone/$PBS_TAG/$enc"; then
    PBS_FROM=$H/cache/pbs
    return 0
  fi
  return 1
}
# macOS, no source worked: python.org's installer. By default this prints the exact next step; with
# --install-python-pkg (your explicit yes) it downloads the installer, checks it, and runs it with sudo.
mac_python_pkg() {
  [ -n "$PKG_URL" ] || return 1
  if [ "$PKGOK" != 1 ]; then
    say ""
    say "A way that needs no GitHub: python.org's signed installer for macOS. Paste this one line (it asks for your Mac password), then run the install command again:"
    say "  curl -fL -o \"\$HOME/Downloads/python-$PY_VERSION.pkg\" $PKG_URL && echo '$PKG_SHA  '\"\$HOME/Downloads/python-$PY_VERSION.pkg\" | shasum -a 256 -c - && sudo installer -pkg \"\$HOME/Downloads/python-$PY_VERSION.pkg\" -target /"
    say "(Or add --install-python-pkg to the install command and it does the same for you.)"
    return 1
  fi
  mkdir -p -- "$H/cache/dl"
  fetch_pinned "python.org's Python $PY_VERSION installer" "$H/cache/dl/python.pkg" "$PKG_SHA" \
    "python.org|$PKG_URL" "our mirror|$MIRROR/python/python-$PY_VERSION-macos11.pkg" || return 1
  if command -v pkgutil >/dev/null 2>&1 && ! pkgutil --check-signature "$H/cache/dl/python.pkg" 2>&1 | grep -q "Python Software Foundation"; then
    say "  ! the installer is not signed by the Python Software Foundation; not running it"
    return 1
  fi
  say "  running python.org's installer with sudo (your Mac password is asked by sudo, not by this script)"
  sudo /usr/sbin/installer -pkg "$H/cache/dl/python.pkg" -target / || return 1
  PY=""; find_python || return 1
  return 0
}

if [ -z "$PY" ]; then
  step 3 "getting a private Python ${PY_VERSION%.*} (about 16 MB for uv, then about 20 to 40 MB for Python)"
  say "  uv $UV_VERSION first, the small tool that installs Python; then Python $PY_VERSION itself."
  say "  Nothing goes outside $H. A source that is down is skipped and the next one is tried; every file is checked against a pinned SHA-256."
  say "  A download that stalls for $STALL_S seconds moves to the next source (COMPOSER_STALL_SECONDS changes that)."
  say "  The download timeout is $UV_HTTP_TIMEOUT seconds when uv itself downloads (set UV_HTTP_TIMEOUT to change it). A slow connection can take several minutes."
  check_owned
  UVOK=1
  get_uv || UVOK=0
  if [ "$UVOK" = 0 ]; then
    say "  ! no source gave uv, so a private Python cannot be installed that way"
    mac_python_pkg || fail "could not get uv $UV_VERSION from any source (your own file, github.com, GitHub download API, PyPI, our mirror), so no private Python" \
      "run the same command again (a flaky connection often works the second time); if GitHub and PyPI are blocked on this network, put the mirror's address in COMPOSER_MIRROR_URL; or install Python 3.10 or newer from python.org (macOS: add --install-python-pkg to this command) and run it again"
  fi
  [ "$UVOK" = 0 ] || say "  uv $UV_VERSION is ready; now Python $PY_VERSION"
  if [ -z "$PY" ]; then   # (set already when python.org's installer was the way)
    PBS_NOTE=""
    if get_pbs; then
      export UV_PYTHON_INSTALL_MIRROR="file://$PBS_FROM"
      say "  installing Python $PY_VERSION into $H/python from the checked download"
    else
      PBS_NOTE="  No source gave Python's file directly; letting uv try its own sources."
      say "$PBS_NOTE"
    fi
    if ! try3 "the Python download" "$H/bootstrap/uv" python install "$PY_VERSION"; then
      pok=0
      if [ -z "$PBS_FROM" ]; then
        for alt in "https://registry.npmmirror.com/-/binary/python-build-standalone" "$MIRROR/python-build-standalone"; do
          say "  trying uv with the Python mirror $alt"
          if UV_PYTHON_INSTALL_MIRROR=$alt "$H/bootstrap/uv" python install "$PY_VERSION"; then pok=1; break; fi
        done
      fi
      if [ "$pok" != 1 ]; then
        mac_python_pkg && pok=1
        if [ "$pok" != 1 ]; then
          fail "could not download Python $PY_VERSION (uv's error is above)" \
            "install Python 3.10 or newer from python.org (macOS: add --install-python-pkg to this command, or use the two lines above; Linux: apt install python3 python3-venv) and run it again; on a slow connection UV_HTTP_TIMEOUT=600 sh setup.sh helps (add the options you used)"
        fi
      fi
    fi
    if [ -z "$PY" ]; then
      PY=$("$H/bootstrap/uv" python find "$PY_VERSION")
    fi
  fi
  chmod -R go-w -- "$H/python" 2>/dev/null || true
  PYVER=$("$PY" -I -c 'import sys; print("%d.%d.%d" % sys.version_info[:3])' 2>/dev/null || echo "$PY_VERSION")
else
  step 3 "using Python $PYVER (nothing to download)"
fi

VENV="$H/app/$VERSION/venv"

# ---- Composer's own files for an install made by install.sh (the pins file): the wheels of Composer, certifi (the
# CA list) and claim-seal, each checked by SHA-256. Sources per file, in order: your own file, PyPI (when it
# has the file), the release's own address, our mirror. claim-seal also has its source archive: GitHub's archive
# address, codeload.github.com, and a copy in the release kit, all pinned to the same SHA-256.
CS_FILE=""; CS_SHA=""
# get_wheel LABEL NAME SHA ENVVAR SPEC: the wheel NAME in $H/tmp/kit. SPEC (name==version) is where PyPI is asked, if at all.
get_wheel() {
  [ -n "$3" ] || return 1
  kd=$H/tmp/kit
  if have_local "$4" "$2" "$3" "" "$kd"; then mv -f -- "$GOT" "$kd/$2"; return 0; fi
  case ",${COMPOSER_SKIP_SOURCES:-}," in *",PyPI,"*) set -- "$1" "$2" "$3" "$4" "" ;; esac
  if [ -n "$5" ] && ! is_dead PyPI; then
    say "  fetching $1 from PyPI"
    mkdir -p -- "$kd/pypi"
    errf=$kd/pypi-error.txt
    if "$VENV/bin/python" -I -m pip download --no-deps --only-binary=:all: --index-url "$PYPI_INDEX" \
        --retries "${COMPOSER_PYPI_RETRIES:-1}" --timeout "${COMPOSER_PYPI_TIMEOUT:-20}" -d "$kd/pypi" "$5" > "$errf" 2>&1; then
      if [ -f "$kd/pypi/$2" ] && [ "$(sha_of "$kd/pypi/$2")" = "$3" ]; then mv -f -- "$kd/pypi/$2" "$kd/$2"; return 0; fi
      say "  ! PyPI's file for $5 is not the pinned one (SHA-256 differs), so it was not used; trying the next source"
    else
      cat "$errf" >&2
      if grep -qiE 'retrying|connection|timed out|temporary failure|name resolution|HTTP error 5|ssl' "$errf"; then
        LAST_WHY="no answer"; mark_dead PyPI
        say "  ! PyPI did not answer for $1; trying the next source"
      else
        say "  ! PyPI does not have $5 (yet); trying the next source"
      fi
    fi
  fi
  fetch_pinned "$1" "$kd/$2" "$3" "github.com|$RELEASE_BASE/$2" "our mirror|$MIRROR/kit/$2"
}
install_kit() {
  kd=$H/tmp/kit
  rm -rf -- "$kd"
  mkdir -p -- "$kd"
  need_tools
  RELEASE_BASE=${COMPOSER_RELEASE_BASE:-$(pin PIN_RELEASE_BASE)}
  RELEASE_BASE=${RELEASE_BASE%/}
  W_C=$(pin PIN_COMPOSER_WHEEL); W_C_SHA=$(pin PIN_COMPOSER_WHEEL_SHA)
  W_T=$(pin PIN_CERTIFI_WHEEL); W_T_SHA=$(pin PIN_CERTIFI_WHEEL_SHA); V_T=$(pin PIN_CERTIFI_VERSION)
  W_S=$(pin PIN_CLAIMSEAL_WHEEL); W_S_SHA=$(pin PIN_CLAIMSEAL_WHEEL_SHA); V_S=$(pin PIN_CLAIMSEAL_VERSION)
  W_SP=$(pin PIN_CLAIMSEAL_PYPI_WHEEL); W_SP_SHA=$(pin PIN_CLAIMSEAL_PYPI_SHA)
  A_S=$(pin PIN_CLAIMSEAL_SRC); A_S_SHA=$(pin PIN_CLAIMSEAL_SRC_SHA); C_S=$(pin PIN_CLAIMSEAL_COMMIT)
  [ -n "$W_C" ] && [ -n "$W_C_SHA" ] && [ -n "$W_T_SHA" ] && [ -n "$W_S_SHA" ] && [ -n "$RELEASE_BASE" ] || \
    fail "the release's pins file is incomplete" "run the install command again to fetch a complete one"
  say "  three files, each checked by SHA-256: Composer $VERSION, certifi $V_T (the list of trusted certificate authorities), claim-seal $V_S (the claim checker)"
  get_wheel "Composer $VERSION" "$W_C" "$W_C_SHA" COMPOSER_WHEEL "lensmith-composer==$VERSION" || \
    fail "could not get the Composer $VERSION wheel from any source (your own file, PyPI, the release, our mirror)" \
      "run the same command again; on a network that blocks GitHub and PyPI, put the mirror's address in COMPOSER_MIRROR_URL, or download $W_C yourself and run: COMPOSER_WHEEL=/path/to/$W_C <the same command>"
  get_wheel "certifi $V_T" "$W_T" "$W_T_SHA" COMPOSER_CERTIFI_WHEEL "certifi==$V_T" || \
    fail "could not get the certifi $V_T wheel from any source" \
      "run the same command again, or download $W_T yourself and run: COMPOSER_CERTIFI_WHEEL=/path/to/$W_T <the same command>"
  CS_FILE=""
  if [ -n "$W_SP" ] && [ -n "$W_SP_SHA" ] && get_wheel "claim-seal $V_S from PyPI" "$W_SP" "$W_SP_SHA" COMPOSER_CLAIM_SEAL_WHEEL "claim-seal==$V_S"; then
    CS_FILE=$W_SP; CS_SHA=$W_SP_SHA
  elif get_wheel "claim-seal $V_S" "$W_S" "$W_S_SHA" COMPOSER_CLAIM_SEAL_WHEEL ""; then
    CS_FILE=$W_S; CS_SHA=$W_S_SHA
  fi
  CS_SRC=""
  if [ -z "$CS_FILE" ]; then
    say "  claim-seal's wheel was not available; trying its source (commit ${C_S:-pinned}), which pip then builds"
    if [ -n "$A_S" ] && [ -n "$A_S_SHA" ] && have_local COMPOSER_CLAIM_SEAL_SOURCE "$A_S" "$A_S_SHA" "" "$kd"; then mv -f -- "$GOT" "$kd/$A_S" && CS_SRC=$kd/$A_S
    elif [ -n "$A_S" ] && [ -n "$A_S_SHA" ] && FP_ROUNDS=1 fetch_pinned "claim-seal source" "$kd/$A_S" "$A_S_SHA" \
        "GitHub's archive|https://github.com/lensmith-ai/claim-seal/archive/$C_S.tar.gz" \
        "codeload.github.com|https://codeload.github.com/lensmith-ai/claim-seal/tar.gz/$C_S" \
        "github.com|$RELEASE_BASE/$A_S" "our mirror|$MIRROR/kit/$A_S"; then CS_SRC=$GOT
    fi
    [ -n "$CS_SRC" ] || fail "could not get claim-seal $V_S from any source (wheel: your file, PyPI, the release, our mirror; source: GitHub's archive, codeload.github.com, the release, our mirror)" \
      "run the same command again, or download $W_S yourself and run: COMPOSER_CLAIM_SEAL_WHEEL=/path/to/$W_S <the same command>"
  fi
  {
    printf 'lensmith-composer==%s --hash=sha256:%s\n' "$VERSION" "$W_C_SHA"
    printf 'certifi==%s --hash=sha256:%s\n' "$V_T" "$W_T_SHA"
    [ -z "$CS_FILE" ] || printf 'claim-seal==%s --hash=sha256:%s\n' "$V_S" "$CS_SHA"
  } > "$kd/requirements.txt"
  say "  installing from the checked files (pip also checks each file's SHA-256; no index is asked)"
  "$VENV/bin/python" -I -m pip install --no-index --find-links "$kd" --no-deps --require-hashes -r "$kd/requirements.txt" || \
    fail "pip refused to install the checked files (its error is above)" "run the same command again; if it stops here again, send the log"
  if [ -n "$CS_SRC" ]; then
    # Built here from the checked source with a checked copy of setuptools, in a throwaway environment: nothing is
    # fetched unchecked and nothing from the build stays in Composer's environment but the built claim-seal.
    W_B=$(pin PIN_SETUPTOOLS_WHEEL); W_B_SHA=$(pin PIN_SETUPTOOLS_WHEEL_SHA); V_B=$(pin PIN_SETUPTOOLS_VERSION)
    say "  building claim-seal from its checked source, with a checked setuptools $V_B in a throwaway environment"
    get_wheel "setuptools $V_B" "$W_B" "$W_B_SHA" COMPOSER_SETUPTOOLS_WHEEL "setuptools==$V_B" || \
      fail "could not get the setuptools $V_B wheel that building claim-seal needs" \
        "run the same command again, or download $W_S yourself and run: COMPOSER_CLAIM_SEAL_WHEEL=/path/to/$W_S <the same command>"
    bd=$kd/build
    mkdir -p -- "$bd"
    printf 'setuptools==%s --hash=sha256:%s\n' "$V_B" "$W_B_SHA" > "$bd/setuptools.txt"
    "$VENV/bin/python" -I -m venv "$bd/env" && \
      "$bd/env/bin/python" -I -m pip install --no-index --find-links "$kd" --no-deps --require-hashes -r "$bd/setuptools.txt" && \
      "$bd/env/bin/python" -I -m pip wheel --no-index --no-build-isolation --no-deps -w "$bd/out" "$CS_SRC" || \
      fail "could not build claim-seal from its source (the error is above)" \
        "run the same command again, or download $W_S yourself and run: COMPOSER_CLAIM_SEAL_WHEEL=/path/to/$W_S <the same command>"
    "$VENV/bin/python" -I -m pip install --no-index --no-deps "$bd"/out/claim_seal-*.whl || \
      fail "pip refused the claim-seal it built" "run the same command again; if it stops here again, send the log"
  fi
  rm -rf -- "$kd"
}

if [ -x "$VENV/bin/composer" ] && "$VENV/bin/composer" --version >/dev/null 2>&1; then
  step 4 "Composer $VERSION is already installed in $H/app/$VERSION"
  step 5 "nothing to install"
else
  step 4 "making a private environment with Python $PYVER (Composer's own folder, so nothing else on this computer is touched)"
  check_owned
  MADE_VERSION=1
  : > "$H/app/.making-$VERSION"   # tracked: a rerun that finds this removes the half-made folder (see above)
  "$PY" -I -m venv "$VENV" || fail "Python could not make its private environment (its error is above)" \
    "on Debian or Ubuntu run: sudo apt install python3-venv; then run the same command again"
  # python.org's Python copies group-writable template files into every venv; the trust contract refuses those
  chmod -R go-w -- "$H/app/$VERSION"
  if [ "$KIT" = 1 ]; then
    step 5 "installing Composer $VERSION, certifi and claim-seal into it (each checked by SHA-256)"
    check_owned
    install_kit
  else
    step 5 "installing Composer $VERSION and its dependencies, certifi and claim-seal (checked by SHA-256); pip's progress follows"
    # pip builds in the folder it installs from, so it gets a copy inside $H/tmp: your checkout stays as it is.
    check_owned
    rm -rf -- "$H/tmp/source"
    mkdir -p -- "$H/tmp/source"
    cp -R -- "$SRC/pyproject.toml" "$SRC/README.md" "$SRC/LICENSE" "$SRC/composer" "$H/tmp/source/"
    find "$H/tmp/source" -name __pycache__ -prune -exec rm -rf -- {} +
    "$VENV/bin/python" -I -m pip install "$H/tmp/source" || \
      die "the install of Composer failed (pip's error is above). If it was the network, rerun the same command with PIP_DEFAULT_TIMEOUT=300 in front, for example PIP_DEFAULT_TIMEOUT=300 sh setup.sh"
    rm -rf -- "$H/tmp/source"
  fi
  chmod -R go-w -- "$H/app/$VERSION"
  "$VENV/bin/composer" --version >/dev/null || fail "the installed Composer does not start" "run the same command again; if it stops here again, send the log"
fi
step 6 "checking the install and making it the current version"
check_owned
"$VENV/bin/python" -I -c 'import os, sys
link = os.path.join(sys.argv[1], "current"); tmp = link + ".tmp"
if os.path.lexists(tmp): os.unlink(tmp)
os.symlink(sys.argv[2], tmp); os.replace(tmp, link)' "$H/app" "$VERSION"
rm -f -- "$H/app/.making-$VERSION"
if [ "${COMPOSER_KEEP_DOWNLOADS:-}" != 1 ]; then rm -rf -- "$H/cache/dl" "$H/cache/pbs"; fi

step 7 "Composer's own setup: the questions, and then your first start"
set -- setup --home "$H"
[ -n "$ANSWERS" ] && set -- "$@" --answers "$ANSWERS"
[ "$YES" = 1 ] && set -- "$@" --yes
[ "$STATE" = new ] && set -- "$@" --home-created
[ -n "$NOTEST" ] && set -- "$@" "$NOTEST"
for part in $RECONF; do set -- "$@" --reconfigure "$part"; done
if has_tty && [ -z "$ANSWERS" ] && [ "$YES" = 0 ]; then
  with_keys "$H/app/current/venv/bin/composer" "$@" < /dev/tty
else
  with_keys "$H/app/current/venv/bin/composer" "$@"
fi
