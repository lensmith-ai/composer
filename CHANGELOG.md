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
