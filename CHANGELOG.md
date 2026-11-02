# Changelog

All notable changes to Lensmith Composer. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (0.y while before 1.0).
Each release note is written from this file and checked against it by claim-seal before it is published
(`scripts/release/release_note.py`).

## [Unreleased]

### Added

- A container image (`Dockerfile`): a pinned Python base, an unprivileged user, a read-only root filesystem and one
  data volume at /data. Optional narration is not in it; the narration image is a separate opt-in target.
- Always-on setup (`compose.yaml` and `Caddyfile`): Caddy in front for HTTPS and one login; the app publishes no port
  of its own.
- A step-by-step guide for running Composer on a server (`docs/deploy-vps.md`), with a local trial that uses a local
  certificate authority.
- Continuous integration: the offline tests on Linux, macOS (Apple silicon) and Windows with Python 3.10 and 3.13,
  the banned-text test over the full history, a secret scan (gitleaks) and a lint of the workflows (actionlint).
- A nightly workflow that runs the always-on proof (`tests/deploy/proof.sh`) and a browser check of the pages
  in Chromium and WebKit.
- A release workflow: the sdist and wheel, a CycloneDX SBOM, SHA256SUMS, GitHub artifact attestations for every
  file and the container image, and a release note checked by claim-seal.
- Issue and pull request templates, Dependabot for the pinned actions, Python build tools and base images.
- `./setup.sh` and `composer setup`: the full app in one folder (`~/.lensmith-composer`) with a private environment,
  questions one at a time or an answers file, every check before any write, the key stored 0600, and an install
  manifest. No shell profile, PATH, sudo or global Python changes.
- `composer up`: the app page at `/` with its engine, the daily brief (once per slot, late by up to 6 hours, never
  stacked) and a weekly backup; behind a proxy it answers only the proxy network and its public address.
- Optional narration: the model writes a short spoken script with each brief; Composer reads exactly that script
  aloud with Kokoro after the text is final, and the transcript sheet shows the same words. An existing Kokoro is
  reused read-only after a hash and three-voice check; any failure leaves the brief text-only. A separate
  `narration` image ships the eSpeak NG GPL-3.0 licence text and a source offer.
- `composer doctor` (`--online`, `--parity`, `--seals`), `composer backup` / `restore`, `composer update` / `rollback`
  (a migrated copy, a journaled switch, undone on failure or after an interruption) and `composer uninstall`
  (only what setup made; your data only with `--delete-data`).
- Add a source from the app page: paste a blog's address and Composer lists the feeds behind it (the address itself,
  the feeds the page advertises, the usual feed addresses), each with its newest titles, comment feeds marked and
  duplicates folded; you pick one and name it, it is read once more and is live at once. Every request uses the
  guarded fetch, with one time limit and a request cap for the whole check.
- Source packages: the picker's package chips, from a bundled file (one package, the two bundled feeds) and your own
  `packages.json`; a package naming an unknown or hidden source is set aside and reported.
- Lenses from the app page: name, what to look for, register (earnest, sceptical or deadpan) and reading level. An
  edit is a new revision of the same lens, linked to the one it replaces; a brief records the revision it used.
- The reading level (and a saved lens's register) are written into the prompt as rules; `composer compose
  --reading-level`.
- An optional article parser for news pages without a feed: the setup question (or `--reconfigure parser`) installs
  it and every package it needs from a hash-locked file, wheels only; there is no pip extra. Without it those pages
  are read with the built-in parser and the receipt says so.
- An optional separate checker model: setup asks "Check claims with the same model?" (or a `[checker]` table in the
  answers file, `--reconfigure checker`); its key is stored in the same 0600 file under its own name. The checker
  makes every claim-seal call, the writer only writes, and the edition and receipts record the two models
  separately; `composer doctor` names the checker and whether its key is present.
- Setup offers a short list of model ids for the chosen service (from `composer/data/models.json`, plus "type
  another"), then makes one tiny test call per key that says plainly whether the key was refused, the model id was
  not found or the endpoint could not be reached, and offers to enter them again; `--no-test-call` skips it.
- With no model key, Compose on the app page, `composer compose`, `composer doctor` and the daily brief all say
  "Composer needs a model key to write a brief. Run ./setup.sh --reconfigure provider." before any job starts or feed
  is read; the recorded brief still shows. `./setup.sh --reconfigure PART` passes the part on to `composer setup`.
- While `composer up` runs it re-verifies the seal of every saved brief once a day and logs the result; with no model
  provider key set, the daily brief is skipped with the reason logged instead of failing.

## [0.1.0] - 2026-11-01

### Added

- `composer compose`: read the chosen feeds, write a brief through your lens with Anthropic or any
  OpenAI-compatible model, and check every claim with claim-seal.
- `composer demo`: replay a recorded brief with no key and no network, as text, a one-file page or an animated site.
- `composer sources`: list, add and test RSS or Atom feeds, the Hacker News front page and news pages without a feed.
- `composer serve`: a small web page that shows the latest brief and composes new ones, on 127.0.0.1 by default.

### Security

- Fixes from an adversarial security review and a second opinion before publication; see SECURITY.md.

[Unreleased]: https://github.com/lensmith-ai/composer/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/lensmith-ai/composer/releases/tag/v0.1.0
