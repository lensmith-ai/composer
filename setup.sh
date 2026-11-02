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

UV_VERSION=0.5.29
PY_VERSION=3.12.9
NEED_KB=307200

say() { printf '%s\n' "$*"; }
die() { printf 'setup.sh: %s\n' "$*" >&2; exit 2; }
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
  mode=$(printf '%s' "$2" | awk '{print $1}'); owner=$(printf '%s' "$2" | awk '{print $3}')
  if [ "$owner" != "$(id -u)" ] && [ "$owner" != 0 ]; then say "$1 belongs to another account (uid $owner); fix: chown $(id -un) $1"; return 1; fi
  case "$mode" in
    *[tT]) case "$mode" in ?????w*|????????w*) say "$1 is a folder shared by every account ($mode); put the app folder under your own home instead"; return 1 ;; esac ;;
    ?????w*|????????w*) say "$1 can be written by other accounts ($mode); fix: chmod go-w $1"; return 1 ;;
  esac
  return 0
}
trust_ok() {
  d=$H
  while [ ! -e "$d" ] && [ ! -L "$d" ] && [ "$d" != / ]; do d=$(dirname "$d"); done
  # no symbolic link on the way: the folders a link leads through are on neither path, so they would go unchecked
  p=$d
  while :; do
    if [ -L "$p" ]; then say "$p is a symbolic link; give the real path instead ($(cd "$d" 2>/dev/null && pwd -P)${H#"$d"})"; return 1; fi
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
  why=$(trust_ok) || die "refused: $why. Composer's folder and every folder above it must be writable only by you (or root), so no other account can change what it runs; or put the app folder somewhere else (the default is ~/.lensmith-composer). Nothing was written."
}

H=${COMPOSER_HOME:-${HOME:-}/.lensmith-composer}
ANSWERS=""
YES=0
PYDL=0
NOTEST=""
RECONF=""
while [ $# -gt 0 ]; do
  case "$1" in
    --home) [ $# -ge 2 ] || die "--home needs a folder"; H=$2; shift 2 ;;
    --answers) [ $# -ge 2 ] || die "--answers needs a file"; ANSWERS=$2; shift 2 ;;
    --yes) YES=1; shift ;;
    --python-download) PYDL=1; shift ;;
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

SRC=$(cd "$(dirname "$0")" && pwd)
[ -f "$SRC/pyproject.toml" ] && [ -d "$SRC/composer" ] || die "run this from a Composer folder (it installs that folder)"
VERSION=$(sed -n 's/^version = "\([0-9][0-9A-Za-z.+_-]*\)"$/\1/p' "$SRC/pyproject.toml" | head -n 1)
[ -n "$VERSION" ] || die "cannot read the version from pyproject.toml"

# ---------------------------------------------------------------------------------------- checks (read only)
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
  [ -w "$PARENT" ] || die "refused: you cannot create folders in $PARENT"
  STATE=new
fi
if [ -n "$ANSWERS" ]; then
  [ -f "$ANSWERS" ] && [ -r "$ANSWERS" ] || die "cannot read the answers file $ANSWERS"
  case "$ANSWERS" in /*) ;; *) ANSWERS=$(pwd)/$ANSWERS ;; esac
  if grep -Eq '^[[:space:]]*python_download[[:space:]]*=[[:space:]]*true' "$ANSWERS"; then PYDL=1; fi
fi
[ "$YES" = 1 ] && PYDL=1

PY=""
for cand in python3 python3.14 python3.13 python3.12 python3.11 python3.10; do
  p=$(command -v "$cand" 2>/dev/null || true)
  [ -n "$p" ] || continue
  if "$p" -c 'import sys, venv, ensurepip; sys.exit(0 if sys.version_info >= (3, 10) else 1)' >/dev/null 2>&1; then
    PY=$p; break
  fi
done

FETCH=""
if [ -z "$PY" ]; then
  say "No Python 3.10 or newer (with venv) was found on this computer."
  case "$(uname -s)-$(uname -m)" in
    Linux-x86_64) UV_ASSET=uv-x86_64-unknown-linux-gnu; UV_SHA=46d3fcf04d64be42bded914d648657cd62d968172604e3aaf8386142c09d2317 ;;
    Linux-aarch64|Linux-arm64) UV_ASSET=uv-aarch64-unknown-linux-gnu; UV_SHA=d1f716e8362d7da654a154b8331054a987c1fc16562bd719190a42458e945785 ;;
    Darwin-arm64) UV_ASSET=uv-aarch64-apple-darwin; UV_SHA=c89e96bde40402cc4db2f59bcb886882ab69e557235279283a2db9dea61135c3 ;;
    Darwin-x86_64) UV_ASSET=uv-x86_64-apple-darwin; UV_SHA=2f13ef5a82b91ba137fd6441f478c406a0a8b0df41e9573d1e61551a1de5a3a2 ;;
    *) die "install Python 3.10 or newer yourself (python.org, or your package manager), then run this again" ;;
  esac
  if command -v curl >/dev/null 2>&1; then FETCH=curl
  elif command -v wget >/dev/null 2>&1; then FETCH=wget
  else die "to download Python this needs curl or wget (and CA certificates); or install Python 3.10+ yourself"; fi
  if command -v sha256sum >/dev/null 2>&1; then SHACMD="sha256sum"
  elif command -v shasum >/dev/null 2>&1; then SHACMD="shasum -a 256"
  else die "no sha256sum or shasum to check the download with"; fi
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
    if ! why=$(owned_ok); then
      say "setup.sh: stopped; nothing it made was removed, because $why" >&2
      return
    fi
    [ "$MADE_VERSION" = 1 ] && [ "$(readlink "$H/app/current" 2>/dev/null)" != "$VERSION" ] && rm -rf -- "$H/app/$VERSION"
    if [ "$STATE" != ours ] && [ ! -e "$H/data" ]; then
      rm -rf -- "$H/bootstrap" "$H/python" "$H/app" "$H/cache" "$H/tmp" "$H/bin"
      rm -f -- "$H/.composer-home" "$H/install-manifest.json"
      [ "$STATE" = new ] && rmdir -- "$H" 2>/dev/null || true
      say "setup.sh: stopped; what it had made in $H was removed again" >&2
    fi
  fi
}
MADE_VERSION=0
trap cleanup EXIT

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

if [ -z "$PY" ]; then
  check_owned
  mkdir -p -- "$H/bootstrap"
  url="https://github.com/astral-sh/uv/releases/download/$UV_VERSION/$UV_ASSET.tar.gz"
  say "downloading uv $UV_VERSION"
  if [ "$FETCH" = curl ]; then
    curl --fail --location --proto '=https' --tlsv1.2 --silent --show-error -o "$H/bootstrap/uv.tar.gz" "$url"
  else
    wget --quiet --https-only -O "$H/bootstrap/uv.tar.gz" "$url"
  fi
  got=$($SHACMD "$H/bootstrap/uv.tar.gz" | awk '{print $1}')
  [ "$got" = "$UV_SHA" ] || die "the uv download did not match its pinned SHA-256; nothing was run"
  tar -xzf "$H/bootstrap/uv.tar.gz" -C "$H/bootstrap" --strip-components=1
  say "installing Python $PY_VERSION into $H/python"
  "$H/bootstrap/uv" python install --quiet "$PY_VERSION"
  PY=$("$H/bootstrap/uv" python find "$PY_VERSION")
fi

VENV="$H/app/$VERSION/venv"
if [ -x "$VENV/bin/composer" ] && "$VENV/bin/composer" --version >/dev/null 2>&1; then
  say "Composer $VERSION is already installed in $H/app/$VERSION"
else
  say "making a private environment with $("$PY" -c 'import sys; print("Python %d.%d.%d" % sys.version_info[:3])')"
  check_owned
  MADE_VERSION=1
  "$PY" -m venv "$VENV"
  say "installing Composer $VERSION into it (and its one dependency, claim-seal, checked by SHA-256)"
  # pip builds in the folder it installs from, so it gets a copy inside $H/tmp: your checkout stays as it is.
  check_owned
  rm -rf -- "$H/tmp/source"
  mkdir -p -- "$H/tmp/source"
  cp -R -- "$SRC/pyproject.toml" "$SRC/README.md" "$SRC/LICENSE" "$SRC/composer" "$H/tmp/source/"
  find "$H/tmp/source" -name __pycache__ -prune -exec rm -rf -- {} +
  "$VENV/bin/python" -m pip install --quiet "$H/tmp/source"
  rm -rf -- "$H/tmp/source"
  "$VENV/bin/composer" --version >/dev/null
fi
check_owned
"$VENV/bin/python" -c 'import os, sys
link = os.path.join(sys.argv[1], "current"); tmp = link + ".tmp"
if os.path.lexists(tmp): os.unlink(tmp)
os.symlink(sys.argv[2], tmp); os.replace(tmp, link)' "$H/app" "$VERSION"

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
