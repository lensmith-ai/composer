# Install Composer with one command

On a Mac or a Linux computer, paste this in a terminal and press Enter:

```sh
curl -fsSL https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh | sh
```

That is all. It takes one to three minutes on a normal connection. At the end the app is running and it
prints a line like this. Cmd+click it, or paste it into your browser:

```
Open: http://127.0.0.1:8765/
```

(The script lives in the Composer repository on GitHub, on its public `main` branch; `lensmith.ai` will serve a
copy later. Until the repository is public, you were sent the script and its files in a folder. [Testing the installer](#testing-the-installer-on-your-own-computer) shows the
one paste for that.)

## What you will see

Eight numbered steps, each with what is happening and why, and how many minutes have gone by:

1. Get a small installer kit (about 1 MB).
2. Check your computer and the folder it will use. Nothing is written yet.
3. Look for Python 3.10 or newer. Composer runs on it.
4. If you have none, get a private one (about 16 MB for the tool that installs it, then about 20 MB for Python). Downloads show a progress bar.
5. Make a private environment in Composer's own folder.
6. Install Composer and its two dependencies, each checked by its SHA-256.
7. Check the install.
8. Set up, then start the app and open your browser.

It asks you one question, at the start so you can walk away afterwards: your Anthropic key. Typing is hidden. Press
Enter to skip it. Without a key you get the recorded demo brief. Add a key later with
`~/.lensmith-composer/bin/composer setup --reconfigure provider`.

Everything goes in one folder, `~/.lensmith-composer`. No sudo. Outside it, it writes only a log file, a temporary
folder it removes again, and the `lensmith` shortcut described under "Next time" (it tells you what it changed). To remove it: `lensmith composer uninstall`.

## Next time

At the end it prints two lines: it is opening your browser now, and the one short command for next time:

```sh
lensmith composer
```

That starts Composer and opens your browser. `lensmith composer doctor`, `update`, `rollback`, `uninstall` and
`--version` do what they say. `lensmith help` lists them. Stop the app with Ctrl+C.

How `lensmith` gets on your computer, so you are never surprised:

- If `~/.local/bin` or `~/bin` is already on your PATH and is yours, it puts a link named `lensmith` there.
- If not, it asks once: "Add 3 lines to your shell profile (`~/.zshrc` for zsh)?" Enter means yes. The lines are
  an alias named `lensmith`, marked `# >>> lensmith`. It tells you which file it changed. Open a new Terminal window
  for it to work. To undo: delete those 3 lines, or run `lensmith composer uninstall`, which removes the link
  and the lines too. `--path` says yes without asking, `--no-path` makes no shortcut.
- It never makes a command called `composer`: PHP's Composer is a different program and is left alone. If another
  program named `lensmith` is already on your PATH, it is left alone too.
- The full path always works: `~/.lensmith-composer/bin/lensmith composer` (and the older
  `~/.lensmith-composer/bin/composer up`).

## If something goes wrong

You never get a wall of code. You get three lines:

```
setup.sh: stopped.
  What failed: could not get uv 0.5.29 from any source ...
  Next:        run the same command again ...
  Log:         /tmp/lensmith-composer-install-log.Ab12Cd  (paste it if you ask for help; it holds no key)
```

What it made is removed again. Ctrl+C does the same. The log is a plain file you can paste to us.

Common cases:

- **GitHub is down or blocked.** Nothing to do. It tries the next place on its own and says so in one line. The
  order for each file is below.
- **A download is slow.** It keeps going. If one stalls for 30 seconds it moves to the next source.
- **No Python 3.10 or newer on your Mac, and nothing can be downloaded.** It prints the one next step: python.org's
  installer, with its checksum. Or add `--install-python-pkg` and it downloads and runs that installer for you
  (it asks for your Mac password through `sudo`; it is the only time anything here uses `sudo`. python.org's own installer may also add a line to your shell profile).
- **Your home folder cannot be written.** It says so and stops. Pick another folder: `... | sh -s -- --home /some/folder`.
- **A shared temporary folder.** If `TMPDIR` is a folder other accounts can change, it stops and says so. Set `TMPDIR` to a folder of your own.
- **A company network that blocks both GitHub and PyPI.** Put our mirror's address in `COMPOSER_MIRROR_URL`, or
  download the files yourself and point `COMPOSER_FILES_DIR` at the folder.

## Where each file comes from

Every file is checked against a SHA-256 written into the script before it is used (a file you supply is copied into the installer's own folder first, and the copy is the one that is checked). If every source for Python fails, uv is allowed to fetch it itself, and uv checks it against the same SHA-256. A file that does not match is
thrown away and the next source is tried. Sources, in order:

| file | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| the installer kit | your file | PyPI | the release | our mirror | |
| uv (installs Python) | your file | github.com release | GitHub download API | PyPI's uv wheel | our mirror |
| Python 3.12 | an existing Python 3.10+ | github.com release | GitHub download API | npmmirror.com | our mirror |
| Python on a Mac, last resort | python.org's signed installer (printed, or `--install-python-pkg`) | | | | |
| Composer, certifi | your file | PyPI | the release | our mirror | |
| claim-seal | your file | PyPI (when published) | the release's wheel | the release's source: GitHub archive, codeload.github.com, our mirror | |

"Your file" means a file you give it: `COMPOSER_KIT`, `COMPOSER_UV_TARBALL`, `COMPOSER_PYTHON_TARBALL`,
`COMPOSER_WHEEL`, `COMPOSER_CERTIFI_WHEEL`, `COMPOSER_CLAIM_SEAL_WHEEL`, or a folder of them in
`COMPOSER_FILES_DIR`. It is used only if its SHA-256 matches. `COMPOSER_SKIP_SOURCES="github.com,PyPI"` skips
sources by name, for a network where one of them hangs.

## Check it before you run it

You do not have to pipe it. Download it, look at it, and compare its checksum with the one on the download page:

```sh
curl -fsSLO https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh
shasum -a 256 install.sh      # compare with the checksum on the page
sh install.sh
```

`sh install.sh --show-pins` prints every SHA-256 the script checks.

## Flags

Put them after `sh -s --` when you pipe, or after `sh install.sh` when you downloaded it.

| flag | what it does |
|---|---|
| `--demo` | do not ask for a key |
| `--no-open` | do not open your browser |
| `--no-start` | install only |
| `--path` / `--no-path` | allow the shell-profile shortcut without asking / make no shortcut |
| `--home DIR` | use another folder |
| `--install-python-pkg` | macOS: allow python.org's installer as the last way to get a Python (uses `sudo`) |
| `--show-pins` | print the pinned SHA-256 values and stop |

## Certificates

Some Pythons have no trusted certificate list of their own. python.org's Mac Python has none until you run its
"Install Certificates" step. Composer does not need you to run it: it uses your computer's list, and if there is
none it uses certifi's, which is installed with it. Checking is never switched off.

## Testing the installer on your own computer

Until the script is hosted, you get a folder (`composer-install-test`) with `install.sh` and Composer's release
files. Unzip it into Downloads and paste this one block. It installs three times into three folders: once the normal
way, once with `github.com` skipped (what happened to you), once with GitHub's whole download side skipped. It prints
how long each took, then starts the normal one and opens your browser.

```sh
cd ~/Downloads/composer-install-test && for t in normal:- github-504:github.com github-down:github.com,GitHub\ download\ API; do n=${t%%:*}; s=${t#*:}; [ "$s" = - ] && s=""; echo "=== $n ==="; start=$(date +%s); COMPOSER_SKIP_SOURCES="$s" COMPOSER_FILES_DIR="$PWD" COMPOSER_HOME="$HOME/lc-test-$n" sh install.sh --demo --no-start --no-path && "$HOME/lc-test-$n/bin/composer" --version && echo "RESULT $n: PASS in $(( $(date +%s) - start )) seconds" || echo "RESULT $n: FAIL"; done; echo; echo "Starting the normal one; your browser opens. Ctrl+C stops it."; "$HOME/lc-test-normal/bin/lensmith" composer
```
