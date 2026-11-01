# Changelog

All notable changes to Lensmith Composer. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html) (0.y while before 1.0).
Each release note is written from this file and checked against it by claim-seal before it is published
(`scripts/release/release_note.py`).

## [Unreleased]

### Added

- A container image (`Dockerfile`): a pinned Python base, an unprivileged user, a read-only root filesystem and one
  data volume at /data. Optional narration is not in it; a narration image will be a separate opt-in tag.
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
