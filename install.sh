#!/bin/sh
# Lensmith Composer: one command to install it and open it.
#
#   curl -fsSL https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh
#   curl -fsSL https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh -s -- --no-open        (flags after -s -- )
#
# Prefer to read it first, or check it against the checksum printed on the download page?
#   curl -fsSLO https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh && shasum -a 256 install.sh   (compare, then:)   sh install.sh
#
# Flags:
#   --home DIR              install into DIR (default ~/.lensmith-composer, or COMPOSER_HOME)
#   --demo                  do not ask for a key; try the recorded demo brief (add a key later with composer setup --reconfigure provider)
#   --no-open               do not open the browser
#   --no-start              install only; do not start the app
#   --path                  allow the shell-profile shortcut without asking (see "the shortcut" below)
#   --no-path               make no shortcut at all
#   --install-python-pkg    macOS: if no other source can give a Python, download python.org's signed installer and run it with sudo
#   --show-pins             print every pinned SHA-256 this script checks and stop
#   -h, --help              this text
#
# What it does: gets a small kit (the release's source, checked by SHA-256), then runs the kit's own setup.sh,
# which finds Python 3.10 or newer or gets a private one, installs Composer and its two dependencies into ONE
# folder, asks for your Anthropic key (hidden; Enter skips it), starts the app and prints the address. Every
# download comes from a list of sources tried in order and is checked against the SHA-256 pinned below before it
# is used; a source that is down is skipped with a one-line note. It never uses sudo (except the macOS Python
# installer, and only if you add --install-python-pkg). Outside the app folder it writes only: one log file, a temporary
# folder it removes again, and the shortcut at the end (one link named lensmith in a folder of yours on your PATH, or,
# if you say yes, 3 marked lines in your shell profile; it tells you which). It never edits anything else.
#
# The shortcut: at the end it makes `lensmith composer` work from any terminal. If a folder you own is on your
# PATH (~/.local/bin or ~/bin) it puts a link named lensmith there. Otherwise it asks once, and with your yes adds 3
# marked lines to your shell profile (an alias; `lensmith composer uninstall` takes them away). It never makes a
# command called composer and never replaces another program named lensmith. The full path always works too:
# ~/.lensmith-composer/bin/lensmith composer (and the older ~/.lensmith-composer/bin/composer up).
#
# Where files come from can be changed, for a network that blocks them (see docs/install.md):
#   COMPOSER_MIRROR_URL, COMPOSER_RELEASE_BASE, COMPOSER_PYPI_INDEX, COMPOSER_FILES_DIR (a folder of the files),
#   and one variable per file: COMPOSER_KIT, COMPOSER_UV_TARBALL, COMPOSER_PYTHON_TARBALL, COMPOSER_WHEEL,
#   COMPOSER_CERTIFI_WHEEL, COMPOSER_CLAIM_SEAL_WHEEL (also COMPOSER_CLAIM_SEAL_SOURCE, COMPOSER_SETUPTOOLS_WHEEL).
#   A file you give is copied into the installer's own folder and used only if the copy's SHA-256 matches the pin.
set -eu
umask 077

# ---- pinned values (made by scripts/install/build_install.py from the release; do not edit)
PIN_VERSION=0.2.0
PIN_MIRROR_URL=https://lensmith.ai/composer/mirror
PIN_RELEASE_BASE=https://github.com/lensmith-ai/composer/releases/download/v0.2.0
PIN_KIT=lensmith_composer-0.2.0.tar.gz
PIN_KIT_SHA=a7cf7197c79f2791ccf1a5e376016055f3adb011f9bdf31c018a3604c55b2989
PIN_KIT_PYPI_URL=
PIN_COMPOSER_WHEEL=lensmith_composer-0.2.0-py3-none-any.whl
PIN_COMPOSER_WHEEL_SHA=96f5d2224792f07887e190740a348db5b314d3bc9adce0489ab18f7d04e13838
PIN_CERTIFI_VERSION=2026.10.23
PIN_CERTIFI_WHEEL=certifi-2026.10.23-py3-none-any.whl
PIN_CERTIFI_WHEEL_SHA=e9b54de76e530bb6cf0ccd036787103acb58fd42ba930ea8bf948ddbaa2f61d1
PIN_CLAIMSEAL_VERSION=0.2.0
PIN_CLAIMSEAL_WHEEL=claim_seal-0.2.0-py3-none-any.whl
PIN_CLAIMSEAL_WHEEL_SHA=f6a473df8fb5bae36c36f2623d17a41b7862bf10c383ff66cd7b358b9aec6867
PIN_CLAIMSEAL_PYPI_WHEEL=
PIN_CLAIMSEAL_PYPI_SHA=
PIN_SETUPTOOLS_VERSION=84.2.1
PIN_SETUPTOOLS_WHEEL=setuptools-84.2.1-py3-none-any.whl
PIN_SETUPTOOLS_WHEEL_SHA=ca140b45d5325a9478f880e351484f62fef15f336462e449ca0c03c873d589c2
PIN_CLAIMSEAL_SRC=claim-seal-b0fdf6126196509984d3480867bd4cf861a19f98.tar.gz
PIN_CLAIMSEAL_SRC_SHA=cf4e8a2a419933657c548ee95ca524bbf04b4e60c8427cb02d01faeab5c5ad1e
PIN_CLAIMSEAL_COMMIT=b0fdf6126196509984d3480867bd4cf861a19f98
# ---- end of pinned values

STALL_S=${COMPOSER_STALL_SECONDS:-30}
CONNECT_S=${COMPOSER_CONNECT_SECONDS:-15}
MIRROR=${COMPOSER_MIRROR_URL:-$PIN_MIRROR_URL}
MIRROR=${MIRROR%/}

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
# Permission changes over a whole folder, the same on GNU and on BSD/macOS. BSD chmod reads the mode first and takes a
# `--` after it as a file name ("chmod: --: No such file or directory", seen on a Mac), so there is no `--` here: find
# prints the folder's own path in front of every name (absolute, or ./ when it was relative), so a name never begins
# with "-". Links are skipped: chmod would follow them, and a link has no mode of its own on Linux.
chmod_go_w() { case "$1" in /*) ;; *) set -- "./$1" ;; esac; find "$1" ! -type l \( -perm -020 -o -perm -002 \) -exec chmod go-w {} +; }
chmod_u_w() { case "$1" in /*) ;; *) set -- "./$1" ;; esac; find "$1" ! -type l ! -perm -200 -exec chmod u+w {} +; }
# END fetchlib

PROG=install.sh

# BEGIN pathlib (the shortcut so later launches are one short command; tested by tests/test_install_shortcut.py)
# What it may change outside the app folder, and nothing else: a link named lensmith in a folder you own that is
# already on your PATH, or (only if you say yes, or add --path) 3 lines in your shell's profile file. It never
# makes a command called composer (PHP's Composer is a different program), and never replaces an existing lensmith.
SC_BEGIN="# >>> lensmith (added by the Composer installer; delete these 3 lines to undo)"
SC_END="# <<< lensmith"
SHORTCUT_HOW=none      # link, have, profile, other or none
SHORTCUT_NOTE=""
on_path() { case ":$PATH:" in *":$1:"*) return 0 ;; esac; return 1; }
profile_file() {
  case "${SHELL:-}" in
    */zsh) printf '%s\n' "${ZDOTDIR:-$HOME}/.zshrc" ;;
    */bash) if [ "$(uname -s)" = Darwin ]; then printf '%s\n' "$HOME/.bash_profile"; else printf '%s\n' "$HOME/.bashrc"; fi ;;
    *) printf '%s\n' "$HOME/.profile" ;;
  esac
}
# shortcut_setup TARGET MODE: MODE is ask, yes or no. Sets SHORTCUT_HOW and SHORTCUT_NOTE (what it did, or why not).
# alias_line TARGET: the profile line. A shell reads an alias's text again as commands when the alias is used, so the path
# is quoted twice: once for the text the alias holds, once for the line itself (the text is then one word: 'PATH').
alias_line() {
  al_q="'"; al_b='\'
  printf '%s\n' "alias lensmith=${al_q}${al_q}${al_b}${al_q}${al_q}$1${al_q}${al_b}${al_q}${al_q}${al_q}"
}
# unsafe_tmp_parent DIR: true if DIR can be changed by other accounts without the sticky bit (ls adds . + or @ after the mode)
unsafe_tmp_parent() {
  um=$(ls -ldn "$1" 2>/dev/null | awk '{print substr($1, 1, 10)}')
  case "$um" in *[tT]) return 1 ;; ?????w*|????????w*) return 0 ;; esac
  return 1
}
# other_writable DIR: true if accounts outside the owner's group can write in DIR (a private user group may be group-writable)
other_writable() {
  ow=$(ls -ldn "$1" 2>/dev/null | awk '{print substr($1, 1, 10)}')
  case "$ow" in ????????w*) return 0 ;; esac
  return 1
}
# plain_path PATH: true if it holds no control character (a newline would end an alias line) and no single quote
plain_path() {
  pp_a=$(printf '%sx' "$1"); pp_b=$(printf '%s' "$1" | tr -d '[:cntrl:]'; printf x)
  [ "$pp_a" = "$pp_b" ] || return 1
  case "$1" in *"'"*) return 1 ;; esac
  return 0
}
shortcut_setup() {
  sc_t=$1; sc_mode=$2; SHORTCUT_HOW=none; SHORTCUT_NOTE=""
  [ -n "${HOME:-}" ] || { SHORTCUT_NOTE="HOME is not set, so no shortcut was made"; return 0; }
  if [ "$sc_mode" = no ]; then SHORTCUT_NOTE="no shortcut made (--no-path)"; return 0; fi
  sc_have=$(command -v lensmith 2>/dev/null || true)
  if [ -n "$sc_have" ]; then
    if [ "$sc_have" = "$sc_t" ] || [ "$(readlink "$sc_have" 2>/dev/null || true)" = "$sc_t" ]; then SHORTCUT_HOW=have; return 0; fi
    SHORTCUT_HOW=other; SHORTCUT_NOTE="another program named lensmith is already on your PATH ($sc_have); it was left alone"; return 0
  fi
  for sc_d in "$HOME/.local/bin" "$HOME/bin"; do
    on_path "$sc_d" && [ -d "$sc_d" ] && [ -w "$sc_d" ] || continue
    [ -n "$(find "$sc_d/" -maxdepth 0 -user "$(id -u)" -print 2>/dev/null)" ] || continue   # the folder itself, links followed
    if other_writable "$sc_d/"; then continue; fi   # not a folder any other account can write to
    if [ -e "$sc_d/lensmith" ] || [ -L "$sc_d/lensmith" ]; then
      SHORTCUT_NOTE="$sc_d/lensmith already exists and is not this install's; it was left alone"; continue
    fi
    if ln -s -- "$sc_t" "$sc_d/lensmith" 2>/dev/null; then
      SHORTCUT_HOW=link; SHORTCUT_NOTE="made the shortcut $sc_d/lensmith (a link to $sc_t); remove it to undo"; return 0
    fi
  done
  # no folder of yours on PATH: a shell profile line, only with your yes
  sc_rc=$(profile_file)
  plain_path "$sc_t" || { SHORTCUT_NOTE="the install folder's name has a quote or a control character in it, so no profile line was written"; return 0; }
  sc_line=$(alias_line "$sc_t")
  if [ -f "$sc_rc" ] && grep -qxF "$sc_line" "$sc_rc" 2>/dev/null && grep -qxF "$SC_BEGIN" "$sc_rc" 2>/dev/null; then
    SHORTCUT_HOW=profile; SHORTCUT_NOTE="the lensmith lines for this install are already in $sc_rc"; return 0
  fi
  if [ -f "$sc_rc" ] && grep -qxF "$SC_BEGIN" "$sc_rc" 2>/dev/null; then
    SHORTCUT_NOTE="$sc_rc already has lensmith lines for another install; they were left alone (use $sc_t composer, or remove those lines first)"; return 0
  fi
  if [ -L "$sc_rc" ]; then SHORTCUT_NOTE="$sc_rc is a link, so it was not edited"; return 0; fi
  if [ "$sc_mode" = ask ]; then
    if ! has_tty; then SHORTCUT_NOTE="no terminal to ask on, so $sc_rc was not edited (add --path to allow it)"; return 0; fi
    printf '\n  Add 3 lines to %s so you can type "lensmith composer" next time? [Y/n]: ' "$sc_rc" > /dev/tty
    sc_reply=""; read -r sc_reply < /dev/tty || sc_reply=n
    case "$sc_reply" in n|N|no|NO) SHORTCUT_NOTE="you said no, so $sc_rc was not edited"; return 0 ;; esac
  fi
  if ( umask 022; { printf '\n%s\n%s\n%s\n' "$SC_BEGIN" "$sc_line" "$SC_END"; } >> "$sc_rc" ) 2>/dev/null; then
    SHORTCUT_HOW=profile
    SHORTCUT_NOTE="added 3 lines to $sc_rc (an alias named lensmith, marked with # >>> lensmith). To undo: delete those 3 lines, or run lensmith composer uninstall"
  else
    SHORTCUT_NOTE="could not write to $sc_rc, so no shortcut was made"
  fi
  return 0
}
# END pathlib

main() {
HOME_DIR=""
DEMO=0
OPEN=1
START=1
PATHMODE=ask
PKGFLAG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --home) [ $# -ge 2 ] || fail "--home needs a folder" "give it like this: --home \$HOME/composer"; HOME_DIR=$2; shift 2 ;;
    --demo) DEMO=1; shift ;;
    --no-open) OPEN=0; shift ;;
    --no-start) START=0; shift ;;
    --path) PATHMODE=yes; shift ;;
    --no-path) PATHMODE=no; shift ;;
    --install-python-pkg) PKGFLAG=--install-python-pkg; shift ;;
    --show-pins)
      printf 'Composer %s, kit file %s\n  SHA-256 %s\n' "$PIN_VERSION" "$PIN_KIT" "$PIN_KIT_SHA"
      printf '  wheel   %s  %s\n  wheel   %s  %s\n  wheel   %s  %s\n' "$PIN_COMPOSER_WHEEL" "$PIN_COMPOSER_WHEEL_SHA" \
        "$PIN_CERTIFI_WHEEL" "$PIN_CERTIFI_WHEEL_SHA" "$PIN_CLAIMSEAL_WHEEL" "$PIN_CLAIMSEAL_WHEEL_SHA"
      printf 'The kit also pins uv, Python and the macOS Python installer; read them in the kit'"'"'s setup.sh.\n'
      exit 0 ;;
    -h|--help) sed -n '2,/^set -eu$/p' "$0" 2>/dev/null | sed '$d' | sed 's/^# \{0,1\}//' || true; exit 0 ;;
    *) fail "unknown option $1" "see the flags at the top of the script (sh install.sh --help), or leave it out" ;;
  esac
done

case "$(uname -s)" in
  Linux|Darwin) ;;
  *) fail "this is $(uname -s); the installer supports macOS and Linux" \
       "on Windows use WSL2 (Ubuntu) and run the command there, or use the container: docs/deploy-vps.md" ;;
esac
H=${HOME_DIR:-${COMPOSER_HOME:-${HOME:-}/.lensmith-composer}}
[ -n "$H" ] && case "$H" in /*) ;; *) fail "the app folder must be an absolute path, not '$H'" "give --home /full/path, or set HOME" ;; esac

STEPS=8
say "Lensmith Composer $PIN_VERSION: one-command install"
say ""
say "  What happens: 8 steps, about 1 to 3 minutes on a normal connection."
say "  Everything goes in $H. No sudo. At the end it makes a short command, lensmith: a link in ~/.local/bin if that"
say "  is yours and on your PATH, or (asked first) 3 lines in your shell profile. It tells you what it changed."
say "  Besides $H it writes only a log file and a temporary folder in ${TMPDIR:-/tmp} (the folder is removed again)."
say "  Every download is checked against a SHA-256 pinned in this release; a source that is down is skipped."

# ---- the log: outside the app folder, so it survives a failed install and can be pasted for help. It holds no key.
LOGDIR=${TMPDIR:-/tmp}
LOG=$(mktemp "${LOGDIR%/}/lensmith-composer-install-log.XXXXXX" 2>/dev/null || true)
if [ -z "$LOG" ]; then say "  (could not make a log file in $LOGDIR; carrying on without one)"; fi
export COMPOSER_INSTALL_LOG=$LOG
{ printf 'install.sh %s on %s %s, sh=%s, started %s\n' "$PIN_VERSION" "$(uname -s)" "$(uname -m)" "${BASH_VERSION:+bash}${BASH_VERSION:-sh}" "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
} >> "${LOG:-/dev/null}" 2>/dev/null || true

# ---- cleanup: the temporary folder this script made (a fresh mktemp folder, checked before it is removed)
STAGE=""
remove_stage() {
  [ -n "$STAGE" ] || return 0
  case "$STAGE" in "${LOGDIR%/}"/lensmith-composer-install-stage.*) ;; *) return 0 ;; esac
  if [ -d "$STAGE" ] && [ ! -L "$STAGE" ] && [ -z "$(find "$STAGE" -maxdepth 0 ! -user "$(id -u)" -print 2>/dev/null)" ]; then
    chmod_u_w "$STAGE" 2>/dev/null || true   # from the shared library above: no `--` after a mode (BSD chmod)
    rm -rf -- "$STAGE"
  fi
  STAGE=""
}
TTY_SAVED=""
restore_tty() { if [ -n "$TTY_SAVED" ]; then stty "$TTY_SAVED" < /dev/tty 2>/dev/null || true; TTY_SAVED=""; fi; }
on_exit() { st=$?; restore_tty; remove_stage
  if [ "$st" != 0 ] && [ "$FAILED" != 1 ]; then
    case "$st" in 130|143|129) say "" >&2; say "install.sh: stopped by you; the temporary files were removed${LOG:+. Log: $LOG}" >&2 ;;
      *) say "" >&2; say "install.sh: stopped unexpectedly (see above). Next: run the same command again; if it stops again, paste the log${LOG:+ ($LOG)}." >&2 ;; esac
  fi
}
trap on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

has_tty() { (: < /dev/tty) 2>/dev/null; }

# ---- the one question: your Anthropic key, typed hidden. Asked first, so the rest runs without you.
unset LC_INSTALL_KEY
LC_INSTALL_KEY=""
if [ "$DEMO" != 1 ]; then
  if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
    LC_INSTALL_KEY=$ANTHROPIC_API_KEY; say "  Using the key in your ANTHROPIC_API_KEY variable."
  elif has_tty; then
    say ""
    say "  One question. Your Anthropic API key writes the briefs (typing is hidden; it is stored only in $H, mode 0600)."
    say "  No key yet? Press Enter to skip: you get the recorded demo brief, and can add a key later."
    TTY_SAVED=$(stty -g < /dev/tty 2>/dev/null || true)
    printf '  Anthropic API key: ' > /dev/tty
    stty -echo < /dev/tty 2>/dev/null || true
    read -r LC_INSTALL_KEY < /dev/tty || LC_INSTALL_KEY=""
    restore_tty
    printf '\n' > /dev/tty
    LC_INSTALL_KEY=$(printf '%s' "$LC_INSTALL_KEY" | tr -d '[:space:]')
    case "$LC_INSTALL_KEY" in ""|sk-ant-*) ;; *) say "  (That does not start with sk-ant-, so it may not be an Anthropic key; setup will test it with one tiny call.)" ;; esac
  else
    say "  No terminal to ask on and no ANTHROPIC_API_KEY set: installing in demo mode (add a key later: composer setup --reconfigure provider)."
  fi
fi
[ -n "$LC_INSTALL_KEY" ] || DEMO=1
unset ANTHROPIC_API_KEY

# ---- step 1: the kit
printf '\nStep 1 of %s (%s elapsed): getting the installer kit (Composer %s'"'"'s release source, about 1 MB, checked by SHA-256)\n' "$STEPS" "$(elapsed)" "$PIN_VERSION"
[ -z "$LOG" ] || printf 'Step 1 of %s: getting the installer kit\n' "$STEPS" >> "$LOG"
need_tools
# the temporary folder's own parent must not be one other accounts can rename things in (writable without the sticky bit)
if unsafe_tmp_parent "${LOGDIR%/}/"; then fail "$LOGDIR can be changed by other accounts, so a temporary folder in it could be swapped" \
  "set TMPDIR to a folder of your own, for example: TMPDIR=\$HOME sh install.sh"; fi
STAGE=$(mktemp -d "${LOGDIR%/}/lensmith-composer-install-stage.XXXXXX" 2>/dev/null) || fail "cannot make a temporary folder in $LOGDIR" \
  "set TMPDIR to a folder you can write to, for example: TMPDIR=\$HOME sh install.sh"
chmod 700 "$STAGE"
KIT_BASE=${COMPOSER_RELEASE_BASE:-$PIN_RELEASE_BASE}
KIT_BASE=${KIT_BASE%/}
have_kit=0
if have_local COMPOSER_KIT "$PIN_KIT" "$PIN_KIT_SHA" "" "$STAGE"; then mv -f -- "$GOT" "$STAGE/kit.tar.gz"; have_kit=1
elif fetch_pinned "the installer kit" "$STAGE/kit.tar.gz" "$PIN_KIT_SHA" \
    "PyPI|$PIN_KIT_PYPI_URL" "github.com|$KIT_BASE/$PIN_KIT" "our mirror|$MIRROR/kit/$PIN_KIT"; then have_kit=1
fi
[ "$have_kit" = 1 ] || fail "could not get the installer kit $PIN_KIT from any source (your own file, PyPI, the release, our mirror)" \
  "run the same command again; on a network that blocks GitHub and PyPI, set COMPOSER_MIRROR_URL, or download $PIN_KIT yourself and run: COMPOSER_KIT=/path/to/$PIN_KIT sh install.sh"
mkdir -p -- "$STAGE/src"
tar -xzf "$STAGE/kit.tar.gz" --no-same-owner -C "$STAGE/src" --strip-components=1 || fail "the installer kit did not unpack" "run the same command again"
[ -f "$STAGE/src/setup.sh" ] && [ -f "$STAGE/src/pyproject.toml" ] || fail "the installer kit does not look like Composer's release" "run the same command again"
say "  kit ready"

# ---- hand over to the kit's setup.sh (steps 2 to 8) with the pins and the answers
PINFILE=$STAGE/pins.env
{
  for v in VERSION RELEASE_BASE COMPOSER_WHEEL COMPOSER_WHEEL_SHA CERTIFI_VERSION CERTIFI_WHEEL CERTIFI_WHEEL_SHA \
           CLAIMSEAL_VERSION CLAIMSEAL_WHEEL CLAIMSEAL_WHEEL_SHA CLAIMSEAL_PYPI_WHEEL CLAIMSEAL_PYPI_SHA CLAIMSEAL_SRC \
           CLAIMSEAL_SRC_SHA CLAIMSEAL_COMMIT SETUPTOOLS_VERSION SETUPTOOLS_WHEEL SETUPTOOLS_WHEEL_SHA; do
    eval "printf 'PIN_%s=%s\n' \"$v\" \"\$PIN_$v\""
  done
} > "$PINFILE"
ANS=$STAGE/answers.toml
if [ "$DEMO" = 1 ]; then printf '[provider]\nkind = "none"\n' > "$ANS"
else printf '[provider]\nkind = "anthropic"\nkey_from_env = "ANTHROPIC_API_KEY"\n' > "$ANS"; fi
chmod 600 "$ANS" "$PINFILE"
export COMPOSER_INSTALLER=1 COMPOSER_PINS=$PINFILE COMPOSER_STEPS=$STEPS COMPOSER_STEP_BASE=1 COMPOSER_T0=$T0 \
  COMPOSER_MIRROR_URL=$MIRROR COMPOSER_PROG=setup.sh
set -- --home "$H" --answers "$ANS" --python-download
[ -z "$PKGFLAG" ] || set -- "$@" "$PKGFLAG"
rc=0
# the key reaches setup.sh through its environment only (never its arguments, so `ps` cannot show it)
( if [ -n "$LC_INSTALL_KEY" ]; then ANTHROPIC_API_KEY=$LC_INSTALL_KEY; export ANTHROPIC_API_KEY; fi; unset LC_INSTALL_KEY; exec sh "$STAGE/src/setup.sh" "$@" < /dev/null ) || rc=$?
LC_INSTALL_KEY=""
if [ "$rc" != 0 ]; then FAILED=1; exit "$rc"; fi
remove_stage

say ""
say "Installed Composer $PIN_VERSION in $H ($(elapsed) elapsed)."
[ -z "$LOG" ] || { mkdir -p -- "$H/cache" 2>/dev/null && cp -- "$LOG" "$H/cache/install.log" 2>/dev/null && say "  The install log is $H/cache/install.log (paste it if you ask for help; it holds no key)."; } || true
shortcut_setup "$H/bin/lensmith" "$PATHMODE"
[ -z "$SHORTCUT_NOTE" ] || say "  Shortcut: $SHORTCUT_NOTE"
case "$SHORTCUT_HOW" in
  link|have) NEXT="lensmith composer" ;;
  profile) NEXT="lensmith composer     (in a NEW Terminal window; this one does not know it yet)" ;;
  *) NEXT="$H/bin/lensmith composer" ;;
esac
say ""
case "$SHORTCUT_HOW" in link|have|profile) EXTRA_CMD="lensmith composer" ;; *) EXTRA_CMD="$H/bin/lensmith composer" ;; esac
say "Optional extras, any time: $EXTRA_CMD setup --reconfigure parser | provider (model) | checker | narration | schedule | port"
say "  parser = cleaner article text, provider = your key and model, checker = the model that checks each claim,"
say "  narration = a spoken voice (Kokoro), schedule = a daily brief, port = the port Composer uses."
say "  Each one asks only about that part and changes nothing else. None of them is needed to start."
say ""
if [ "$START" != 1 ]; then
  say "Start it now:  $H/bin/lensmith composer"
  say "Next time:     $NEXT"
  exit 0
fi
if [ "$OPEN" = 1 ]; then say "Opening Composer in your browser now (the address is printed below). Ctrl+C stops it."
else say "Starting Composer (the address is printed below; --no-open, so your browser is left alone). Ctrl+C stops it."; fi
say "Next time, type:  $NEXT"
say ""
if [ "$OPEN" = 1 ]; then exec "$H/bin/lensmith" composer; fi
exec "$H/bin/lensmith" composer --no-open
}
main "$@"
