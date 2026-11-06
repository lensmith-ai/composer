# Changelog

All notable changes to Lensmith Composer. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (0.y while before 1.0).
Each release note is written from this file and checked against it by claim-seal before it is published
(`scripts/release/release_note.py`).

## [Unreleased]

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
  encoded dot, slash, backslash or `%`, and no space or control character. An article that leads to another host,
  port or folder than the one allowed is not read, and a link that cannot be read as an address is skipped instead
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
