# Changelog

All notable changes to Lensmith Composer. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (0.y while before 1.0).
Each release note is written from this file and checked against it by claim-seal before it is published
(`scripts/release/release_note.py`).

## [Unreleased]

### Added

- One command for a stranger on macOS and Linux: `curl -fsSL <address of install.sh> | sh`. It finds Python 3.10 or
  newer or gets a private one, installs Composer and its three dependencies into `~/.lensmith-composer`, asks only for
  your Anthropic key (hidden; Enter skips it for the recorded demo), starts the app, prints `Open: http://127.0.0.1:8765/`
  and opens your browser. See `docs/install.md`.
- Every file the installer fetches has a list of places to come from, tried in order with a one-line note when it
  switches (uv: GitHub release, GitHub download API, PyPI's wheel, our mirror; Python: GitHub, the download API,
  npmmirror, our mirror, and on a Mac python.org's signed installer; Composer's wheels: PyPI, the release, our mirror),
  and every file is checked against a SHA-256 pinned in the script. `COMPOSER_FILES_DIR` and per-file variables take
  files you already have; `COMPOSER_SKIP_SOURCES` skips a source that hangs.
- `composer up --open` opens the address in your browser.
- Composer uses certifi's list of trusted certificate authorities when the Python it runs on has none (python.org's
  macOS Python before its "Install Certificates" step), so feeds and the model API verify HTTPS on any Python.

### Fixed

- setup.sh refused its own environment when python.org's Python made group-writable template files in it, and a
  rerun then died on the half-made version folder. It now takes the group-write bit off right away and removes a
  half-made folder it marked itself.
- A failed setup ends with what failed, the one next step and a log file, not a raw error.

## [0.2.0] - not released yet

The full app, on your computer or your own server. In plain words:

### Added

- One command installs the whole app: `./setup.sh`. It puts everything in one folder (`~/.lensmith-composer`), asks a
  few questions one at a time (or reads an answers file), checks everything before it writes anything, and keeps
  your key in a file only you can read. It does not touch your shell profile, PATH, sudo or system Python.
- Setup offers a short list of model ids for your service (the default is still `claude-sonnet-5-5`, or type
  another), then makes one tiny test call per key and says plainly if the key was refused, the model id was not
  found or the endpoint could not be reached. `--no-test-call` skips it.
- An optional second model to check the claims: setup asks "Check claims with the same model?". If you name another
  model, it makes every check call and the writer only writes; each brief's receipt names both.
- With no model key, Compose on the app page, `composer compose`, `composer doctor` and the daily brief all say
  "Composer needs a model key to write a brief. Run ./setup.sh --reconfigure provider." before any job starts or feed
  is read; the recorded brief still shows.
- `composer up` starts the app at http://127.0.0.1:8765/: the phone-width page, your saved briefs, a daily brief if
  you want one (run once per day, up to 6 hours late, never piled up; skipped, with the reason logged, when no key
  is set) and a weekly backup. It also re-checks the seal of every saved brief once a day.
- In the app: add a source by pasting a blog's address (Composer finds the feeds behind it and you pick one), start
  from a package of sources, and make your own lenses (name, what to look for, tone, reading level). Editing a lens
  makes a new revision, and each brief records the one it used. `composer compose --reading-level` does the same
  on the command line.
- In the app: the menu lists your saved briefs, the compose screen offers to rejoin a brief that is still being
  written, and the lens library counts the briefs made with each lens, all from a shelf index (`/data/index.json`)
  that lists titles, times, sources, lens ids and counts, never keys or file paths. Save and Delete reach the server,
  and a brief opens from its own link (`/app/?job=<id>`).
- In the app: when no feed is found at a pasted address but the page itself can be read, "Add a source" offers to
  read the page's article links instead (an `html-index` source). It shows what it would read before anything is
  saved: the host, the folder (for https://example.com/blog, only addresses under `/blog/` on example.com), at most
  10 links followed and 5 articles in a brief, and the titles of the first articles, read just now. Nothing is saved
  until you name it and press add. The front page of a site, an `http://` address, an address with a
  `user:password@` part, and a page that leads to another site get no offer.
- A feed entry with no real text (an empty description, "TBD", "coming soon", Lorem ipsum, or only the title again)
  is no longer written up as news. A brief reads such an entry from its own page, on the same site as the feed only,
  or leaves it out, and the brief's receipt says how many were filled in or left out and why (by position, never
  the title). The writer is also told never to describe how an item was published or described.
- In the app: "Add a source" now finds feeds from a site's front page that advertises none in its head: it follows
  a link such as "RSS" to the site's own page of feeds (on the same site only; `http://` addresses there are read as
  `https://`), checks each feed it lists, and shows them for you to pick, each with how it was found
  (`found_via`). Usual feed addresses (including `/rss.cms`) are guessed only when the page gave no feed.
- The app page uses the width of your screen. The phone keeps its single column; from 768 px the loom stands beside
  the reading column, and from 960 px the insight cards sit in two columns (the text is held to a readable line
  length). The compose screen is centred and larger on a laptop.
- In a brief, every checked claim is marked with the same thin amber underline the published Composer window uses.
  Pressing one (click, tap, Enter or Space) opens a sheet with the claim, the verdict in plain words (supported,
  partly supported or not supported), the cited article with its link and the passage the check located (at most 25
  words, kept in that brief's own `passages.json` on your computer, never in the shared edition, the receipts or
  `check.json`). Esc, the Close button or pressing elsewhere closes it.
- The compose animation forms its first words within 3 seconds of pressing Compose, no longer waiting for the first
  feed to answer. Tap, click or Esc skips it; with reduced motion nothing is drawn.
- Setup shows where it is: "Step 3 of 7: downloading Python 3.12 (about 40 MB)", with the download's own progress on
  screen. Before it asks to download a Python it says why ("Found python3 3.9.6 at /usr/bin/python3; Composer needs
  3.10 or newer."). A failed download prints the real error and the two ways forward (rerun with a longer
  `UV_HTTP_TIMEOUT`, or install Python 3.10 or newer from python.org) instead of hiding it. The network timeout now
  defaults to 300 seconds (uv's own is 30) and a download is tried three times; a timeout you set yourself is kept.
- `composer up` prints `Open: http://127.0.0.1:8765/` on a line of its own, so a macOS Terminal makes it Cmd+clickable
  (terminals known to draw links get a link around the same text). A brief composed from the page, or by
  `composer compose`, prints numbered progress lines on the terminal (reading sources, writing, checking claims, done)
  and, if it fails, the reason.
- `composer update --from-file` also finds the checksums in `SHA256SUMS.txt` next to the release file (a messaging app
  or browser may add `.txt`), and says it did.
- An optional article parser (trafilatura) for news pages that have no feed, installed from a hash-locked file.
- Optional narration: a Listen button that reads the brief's own spoken script aloud with Kokoro, made on your
  computer after the text is final. A Kokoro you already have is reused, read-only, after a check. If anything
  fails, the brief stays text-only. The separate `narration` container image carries the eSpeak NG licence text
  and a source offer.
- `composer doctor` checks the install one line at a time. `composer backup` and `restore`, `composer update` and
  `rollback` (a migrated copy of your data, undone if it fails or is interrupted) and `composer uninstall` (only what
  setup made; your data only if you ask). An update builds the new version where it will run and switches all or
  nothing.
- Run it on your own server: a container image (unprivileged, read-only, one data volume), a Compose file with
  Caddy in front for HTTPS and one login, and a step-by-step guide (`docs/deploy-vps.md`).
- A quote rule: the writer is asked for its own words, and a check after writing allows at most 25 words per
  quote copied from an article, at most 2 quotes from one article per brief, and never an article's opening
  sentence. A brief that breaks it is sent back once; if it still breaks it, those parts are dropped and the
  receipt says so.
- Every brief page and the app now say "AI-written summary; check the source."
- Setup ends with the three ways to get a brief every day: this computer (only while it is awake), your own server
  with a domain (always on, read anywhere), or the emailed brief on lensmith.ai (no setup). The README says the same.
- The README has a new section, "Sources and your responsibility": check a source's terms, no paywalls, short
  quotes, no logos, keep the AI note, fix and remove fast.
- Releases you can check: SHA256SUMS, a CycloneDX SBOM, GitHub attestations for every file and the container
  image, and a release note checked by claim-seal against this file. `scripts/release/rc.py` builds release
  candidates the same way, from chosen commits, for testing before a release.
- Tests on Linux, macOS and Windows with Python 3.10 and 3.13, a secret scan, a workflow lint, and a nightly check
  of the server setup and the pages in two browsers.

### Changed

- Six default sources instead of two: the Google AI blog, the Google DeepMind blog, the Hugging Face blog, the
  Microsoft Research blog, the PyTorch blog and arXiv cs.AI. The Google AI blog is read at the address its old one
  now redirects to.
- A brief can have 3 to 10 insights (it was 3 to 8).
- `/health` lists the ids of the briefs being written (`active_jobs`) and their count (`active_count`), and HEAD
  requests get the same answer as GET without the body.
- claim-seal is pinned to commit b0fdf61: a citation's evidence window now stops at the end of the cited item,
  entry or article, so a claim can no longer be backed by a sentence from the next article in the same feed.
- THIRD-PARTY.md lists every package Composer installs or ships, optional parts included, with its version and
  licence. It had left out most of narration's packages, among them phonemizer-fork, which is GPL-3.0-or-later. It
  now says plainly which parts are GPL and what that means for you, setup's narration question names
  phonemizer-fork, and a test fails if a package in a lock file is missing from THIRD-PARTY.md.

### Security

- Composer works only in a folder no other account can change: before setup (with or without `--data`), update,
  rollback, restore, uninstall, backup, recovery, `composer doctor`'s writing checks, `composer serve` or narration
  writes, removes or starts anything, the app folder and the data folder, every folder above them, and every folder
  and file inside them must belong to you or root and be writable by no one else, and the path to them may not go
  through a symbolic link (see "Where Composer works" in SECURITY.md); otherwise it refuses, before it takes the run
  lock or recovers anything, and says how to fix it (naming the option you used, `--home`, `--data` or `--out`, and
  saying when a disk has no permission bits for `chmod` to change). Composer gives every folder and file it makes an explicit private mode,
  whatever the umask or a default ACL; the programs it starts never make group-writable files under any umask.
  Recovery acts only on its own folders inside the data folder, never on a path its journal names elsewhere;
  uninstall removes and backup writes only inside the folders they opened, and the run lock is never opened
  through a link.
- When that check fails, `composer doctor` reports it and stops: even with `--online` it reads no settings, key or
  sources file from those folders and calls no model, checker or source with them, so settings another account
  wrote cannot send your key to an endpoint it chose. No command calls a model or a source, or uses your key, with
  settings from a folder that failed the check. `composer serve --out` writes to exactly the folder it checked.
- `composer doctor --online` checks the app folder again just before its narration check writes a scratch folder
  there, so an app folder that appeared after the trust row (in a folder other accounts can write) is refused,
  not written in. SECURITY.md now says that `composer up` and `composer doctor --online` read `COMPOSER_SOURCES`
  or `./composer-sources.json` when the data folder has no sources file of its own.
- Downloads, temporary files and narration audio are always written as fresh files, so a file of that name linked
  elsewhere is never written through. An update never removes a version folder it did not make; rollback removes the version it rolled
  back from.
- Setup (`composer setup` and `./setup.sh`), update, rollback, recovery and narration refuse to work through a
  symbolic link planted in place of one of Composer's own folders (bin, app, python, bootstrap, narration, models,
  cache, tmp, a version's environment); the only link allowed is app/current, naming a version folder beside it.
  Writes and removals there go through open folders, not paths, so a folder swapped for a link while setup or an
  update is running cannot redirect them either.
- `./setup.sh` gives the model keys and the server pass phrase only to `composer setup`, not to Python discovery,
  venv, pip or the build tools pip runs, even when a variable of its holding name was handed in already exported.
- A model endpoint's success reply cannot put the key into a brief's receipts: a reported model id that is malformed
  or holds the key is replaced by the configured one, token counts are kept only as whole numbers, and a reply whose
  text holds the key is refused; a token count whose digits hold a piece of the key is unknown. "Holds the key"
  means the whole key or any run of 12 or more of its characters; only five exact published key prefixes are
  exempt (see SECURITY.md).
- The release workflow pushes the container image only under a candidate tag and gives it the version tag only
  after the tests, the build, the claim-sealed release note and the image's own attestations have all passed.
- An `html-index` source now follows a link only if it is on the same port as its index page (before, a
  link to the same host on another port was followed) and its path has no dot segments (also `..;`), no `;`, no
  encoded dot, slash, backslash or `%`, and no space or control character. A redirect of an article that leads to another
  host, port or folder than the one allowed is refused before it is requested (so an escape and a return never touch
  the other site), and the index page may only move within its own host and port. Every redirect hop counts as a request
  against the request limit of the address check, the page-links preview and a source probe. A link that cannot be read as an address is skipped instead
  of stopping the page. The scope the app offers for a page with no feed is built on the
  server from the address alone (the page's own host and folder, fixed limits), never from what the browser sends.

## [0.1.0] - 2026-11-01

### Added

- `composer compose`: read the chosen feeds, write a brief through your lens with Anthropic or any
  OpenAI-compatible model, and check every claim with claim-seal.
- `composer demo`: replay a recorded brief with no key and no network, as text, a one-file page or an animated site.
- `composer sources`: list, add and test RSS or Atom feeds, the Hacker News front page and news pages without a feed.
- `composer serve`: a small web page that shows the latest brief and composes new ones, on 127.0.0.1 by default.

### Security

- Fixes from an adversarial security review and a second opinion before publication; see SECURITY.md.

[Unreleased]: https://github.com/lensmith-ai/composer/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/lensmith-ai/composer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/lensmith-ai/composer/releases/tag/v0.1.0
