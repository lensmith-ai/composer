# Install Composer on your computer

Want the shortest way? One command, no download first: [install.md](install.md). This page is for running
`./setup.sh` from a release folder or a checkout, and for what each question means.

```sh
./setup.sh
~/.lensmith-composer/bin/composer up
```

`composer up` prints `Open: http://127.0.0.1:8765/` on a line of its own: Cmd+click it in macOS Terminal (or paste it
into a browser). Setup offers the next free port if 8765 is taken. This page says what setup
asks, what it creates, what it never touches, and how to update, back up and remove it.

## What setup needs

- macOS or Linux (on Windows, use WSL2 or [the container](deploy-vps.md#try-it-on-your-own-computer-first)).
- Python 3.10 or newer with `venv`. If you have none, setup can download a pinned uv (checked against its SHA-256)
  into the app folder, which installs its own Python there too. It asks first; for that it needs `curl` or `wget`
  and CA certificates. It never uses sudo, apt, brew or `pip --user`. Before it asks, it says why it wants to
  download (for example, macOS ships python3 3.9.6, which is older than 3.10). Setup prints "Step N of 7" for each
  stage and leaves the download's own progress and any error on screen. Network timeouts default to 300 seconds
  (uv) and 120 seconds (pip), and the Python download is tried three times; set your own with
  `UV_HTTP_TIMEOUT=600 sh setup.sh` on a slow connection. If the download still fails, install Python 3.10 or newer
  from python.org and run `./setup.sh` again.
- The internet, once: to install Composer's one dependency (claim-seal, pinned by commit and SHA-256) and, if you
  choose narration, its runtime and model.
- About 300 MB of disk without narration; narration adds about 110 MB of runtime and 354 MB of model files.

## The questions

One at a time, with a default in [brackets]. Press Enter to take it.

1. **Model provider**: Anthropic, an OpenAI-compatible endpoint (OpenAI, OpenRouter, a local Ollama or LM Studio
   server), or skip for now (the app then shows the recorded brief; a compose stops with an error until you add a
   key with `composer setup --reconfigure provider`, and the daily brief is skipped with the reason logged). Then
   the model: for Anthropic a short numbered
   list (`claude-sonnet-5-5`, the default, `claude-opus-5-5`, `claude-haiku-5-5`) and "type another model id"; for an
   OpenAI-compatible endpoint you type the id it uses (OpenRouter's look like `anthropic/claude-opus-5-5`). The list
   is `composer/data/models.json`; edit it to change what is offered. An answers file takes any id.
2. **Key**: pasted without being shown, and stored in `data/secrets.env` (mode 0600, in a folder only you can open).
   Press Enter instead to keep using the `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` environment variable. Then one
   tiny test call (asking for at most 16 tokens, 15-second network limit) checks that the key and the model id work.
   If not, it says which: the key was refused, the model id was not found, or the endpoint could not be reached, and
   offers to enter them again or keep going (an answers file just keeps going and says so). The key is never
   printed, and the call is no part of any brief's calls or costs. `--no-test-call` (or `COMPOSER_NO_TEST_CALL=1`)
   skips it.
3. **Checker** (optional): "Check claims with the same model? [Y/n]". Yes (the default) means the model that wrote
   the brief also checks each claim against its source. No asks for a second model: Anthropic or an
   OpenAI-compatible endpoint (with its base URL), the model, and its key (hidden, stored in the same 0600 file as
   `COMPOSER_CHECKER_API_KEY`, apart from the writer's key; Enter keeps using that environment variable), with the
   same model list and the same test call. The checker
   then makes every check call (each insight and the connection) and the writer only writes. A different model can
   catch mistakes the writer would repeat when it checks its own work; it costs whatever that model costs for those
   calls. Each brief's `receipts.json` says which model wrote it and which checked it.
4. **Sources**: the six bundled feeds are always there (the Google AI, Google DeepMind, Hugging Face, Microsoft
   Research and PyTorch blogs, and arXiv cs.AI); add Hacker News, or paste any RSS or Atom address. Each one
   is read once and shown before it is added.
5. **Article parser** (optional, default no): trafilatura (Apache-2.0) and the packages it needs,
   installed into the app's own environment from the hash-locked `composer/extraction-requirements.lock` (wheels
   only, every file's SHA-256 checked). It reads news pages that have no feed (`html-index` sources that ask for it)
   better than the built-in parser. Without it, those pages are read with the built-in parser (text only) and each
   brief's receipt says so; feeds are not affected. This lock file is the only way it is installed (there is no pip
   extra, which could not hash-check the packages it needs); `composer setup --reconfigure parser` adds it later.
6. **Narration** (optional): a Listen button and three voices, made on your computer. Setup shows what it needs and
   the licences (the Kokoro-82M model and voices are Apache-2.0; kokoro-onnx and onnxruntime are MIT; espeakng-loader
   bundles eSpeak NG, and kokoro-onnx uses phonemizer-fork, both GPL-3.0-or-later; soundfile is BSD-3-Clause;
   [THIRD-PARTY.md](../THIRD-PARTY.md) lists every package and what the GPL means for you). Then it looks for a Kokoro
   you already have (below) and offers: use it, download the model into the app folder, or skip. Without narration
   briefs are text-only and the page shows no player and no voice picker.
7. **Daily brief** (optional): a time, your time zone or UTC, and a lens. It runs while `composer up` runs, and
   each one is saved to your shelf. If your computer was asleep at that time, it runs once when the app is back
   within 6 hours; later than that it is skipped and logged. Missed days never pile up. With no model provider key
   set, that day's brief is skipped and the log and `/schedule` say why.
8. **Port** on this computer.

Then it prints what it chose, how to start the app, and the three ways to get a brief every day (below). Run `./setup.sh` (or `composer setup`) again at any time: it
keeps your key, sources, lenses and briefs, and `--reconfigure provider|checker|sources|parser|narration|schedule|port` asks one
part again.

## To get this every day

Setup's last lines name three ways:

1. **This computer**: turn on the daily brief (setup asks; later, `composer setup --reconfigure schedule`). It
   runs only while `composer up` runs and the computer is awake, and you read it on that computer.
2. **Your own server with a domain**: always on, and you can read it from anywhere. See [deploy-vps.md](deploy-vps.md).
3. **No setup (coming soon)**: a daily brief by email, with nothing to install. Watch [lensmith.ai](https://lensmith.ai) for the waitlist.

## With no questions: an answers file

```sh
./setup.sh --answers answers.toml
```

```toml
[provider]
kind = "anthropic"                    # anthropic, openai or none
model = "claude-sonnet-5-5"
key_from_env = "ANTHROPIC_API_KEY"    # read once now and stored (0600); or: key = "env" to keep using the variable

[checker]                             # leave this table out to check with the same model
kind = "openai"                       # anthropic or openai
base_url = "https://api.openai.com/v1"
model = "gpt-4.1"                     # the checker's model id at that endpoint
key_from_env = "COMPOSER_CHECKER_API_KEY"  # read once now and stored (0600); or key = "env". Only this name:
                                      # the writer's key is never sent to the checker

[sources]
hacker_news = true
add = ["https://example.org/feed.xml"]

[parser]
trafilatura = false                   # true installs the optional article parser (hash-locked)

[narration]
enabled = true
accept_licences = true                # required for narration: you have read the licences above
use = "existing"                      # existing (only if it passes the check), server, download or skip

[schedule]
enabled = true
time = "07:00"
timezone = "local"                    # or UTC
lens = "what changed this week that a builder should act on"

[server]
port = 8765

[install]
python_download = true                # allow setup.sh to download a private Python if there is none
```

A key is never written in an answers file: setup refuses one. Every section and key is optional; anything left out
takes its default. `./setup.sh --yes` takes every default (no key, no narration, no daily brief). JSON works too
(`answers.json`, same sections).

## What it creates, and nothing else

Everything is in one folder, `~/.lensmith-composer` (or `--home DIR`, or `COMPOSER_HOME`):

```
bin/composer            the launcher you run
app/<version>/venv/     a private environment per version; app/current points at the one in use
python/ bootstrap/      only if setup downloaded Python for you
narration/venv/         only if you chose narration
models/kokoro/          only if you let Composer download the model
cache/ tmp/             every cache and temporary file, pointed here
data/                   YOUR DATA: briefs, settings, sources, key, backups, recovery records
install-manifest.json   what was created, and what is reused read-only from elsewhere
```

Setup refuses, before writing anything, a folder that already holds other files, your home folder itself, a
symbolic link, or a folder it cannot write to. It also refuses an app folder or data folder that another account
could change (SECURITY.md, "the trust contract"), and says what to do. The common cases:

- **Your home folder is reached through a link** (Fedora Silverblue and Kinoite: `/home` -> `var/home`; FreeBSD:
  `/home` -> `usr/home`). The refusal names the real path; pass it: `./setup.sh --home /var/home/you/.lensmith-composer`
  (or `--data <real path>` for a data folder, or `COMPOSER_HOME` / `COMPOSER_DATA`).
- **A group-writable folder** above or inside the app folder, common where every account gets umask 002 (a folder
  you made at 0775, a file copied in at 0664): `chmod -R go-w <folder>`, as the refusal says. Composer's own files
  never come out that way. This is stricter than OpenSSH's StrictModes as Debian patches it, which accepts a
  group-writable folder when you are the only member of its group; Composer does not look at group members.
- **A disk without permission bits** (FAT, exFAT, NTFS: most USB sticks and external disks; on Linux they are often
  mounted 0777): `chmod` has no effect there. Use a POSIX filesystem (ext4, btrfs, xfs, APFS), or mount the disk with
  `uid=$(id -u),dmask=077,fmask=177`. Every program it starts gets a private environment that points
`TMPDIR`, pip's and uv's caches, the XDG folders and Python's bytecode cache inside the app folder and ignores your
pip settings. It never edits your shell profile, PATH, login items or Homebrew: to type `lensmith composer` from anywhere it
prints the alias line for you to add yourself.

## A Kokoro you already have

Setup only looks, and changes nothing: `KOKORO_MODEL_PATH` (and `KOKORO_VOICES_PATH`), `kokoro-v1.0` model and
voice files under `~/.cache`, `~/Library/Application Support`, `~/models`, `~/Downloads` and your home folder (four
levels deep, for at most 10 seconds), your Hugging Face cache, and a Kokoro server on this computer at port 8880.
Finding is not reusing. Model files are used only when their SHA-256 matches the pinned release and one sentence
renders in each of the three voices (af_heart, am_michael, bf_emma) from the unchanged files; a server only at the
exact address you confirm, after it renders the voices. Files are opened read-only, recorded in the manifest as
reused, and never removed by uninstall. PyTorch weights and Hugging Face cache entries are reported as found but
not usable by this engine. Composer never downloads a second copy without asking and saying how big it is.

## Narration at run time

A brief is narrated after its text is final: the words read aloud are the brief's own narration script, which the
model writes with the brief, and the page's transcript sheet shows exactly those words. One brief at a time, at low
priority, capped in length and time. If narration fails for a brief, the brief stays text-only and its record says
why.

## Check it: composer doctor

```sh
~/.lensmith-composer/bin/composer doctor            # this install, offline, one line per check
~/.lensmith-composer/bin/composer doctor --online   # also one tiny model call, every source, one spoken sentence
~/.lensmith-composer/bin/composer doctor --parity   # also a recorded brief through the app's own routes
~/.lensmith-composer/bin/composer doctor --seals    # also re-verify the seal of every saved brief
```

It says whether a key is present, never the key, and whether the claims are checked by the writer's model or a
separate one (with that key present or not); `--online` also makes one tiny call to a separate checker. It also shows the last daily seal re-check: while `composer up`
runs, the app re-verifies the seal of every saved brief once a day (the same check as `--seals`) and logs the result;
set `"seals": {"daily": false}` in `config.json` to turn that off.

## Back up, update, roll back

```sh
composer backup                      # data/backups/composer-backup-<time>.tar.gz; not your key unless --include-secrets
composer restore <file>              # checks the archive first; keeps what it replaces
composer update --from-file <release> --sha256 <its SHA-256>   # or leave out --sha256 with SHA256SUMS (or SHA256SUMS.txt) beside the file
composer rollback
```

The app also makes a backup once a week (`...-weekly.tar.gz`) and keeps the last 8 of those; backups you make yourself are never pruned. Copy backups somewhere else too. An update installs
the new version into its own environment in `app/<version>` and checks that it starts there, copies and migrates
your data if the new version needs it (the original stays as it was), switches, runs `composer doctor` with the new
version, and undoes itself if anything fails: your data and the version you had stay current. An update that
stopped half way is undone the next time Composer starts, or by `composer rollback`. Rollback first exports every
brief made since the update to `data/recovery/exports/`, then removes the version it rolled back from. An update
never removes a version folder it did not make: if `app/<version>` is already there (an earlier try that stopped
before it could clean up), it refuses and leaves that folder for you to look at and remove. If the current version's environment cannot start at all,
`bin/composer` still runs `rollback`, `uninstall`, `backup` and `doctor`, with another installed version or your
system `python3`. Stop `composer up` before restore, update, rollback or uninstall; they refuse
while it runs.

## Remove it

```sh
~/.lensmith-composer/bin/composer uninstall                # removes what setup made; keeps data/
~/.lensmith-composer/bin/composer uninstall --delete-data  # also your data, after you type DELETE
```

Uninstall removes only the paths the manifest lists as created, after checking each one is inside the app folder
(no `..`, no way out through a link; a link is removed, never what it points to). It never touches a reused Kokoro
or anything else outside the folder. Your data stays unless you ask, and setup picks it up again if you reinstall.
If you added the alias line to your shell profile, remove it yourself.
