# How Composer was built, and what has been checked

The short version is in the [README](../README.md#how-this-was-built).

## Who did what

- **Me (Arya):** I designed Composer and I decide what it does. The private version of Composer writes briefs I read, and I click through to the cited articles to see that what a claim says is really there.
- **My agent team:** Sal, which runs on Hermes, and my agent command center, which uses several models, including Claude and OpenAI's Codex and GPT models. They wrote the code, the tests and the first draft of this documentation.
- **What I did not do:** I have not read every line of the code, and no human has audited it. The checks below stand in for that, and every reviewer named here was an AI model.

## What tools have checked

| Check | Result |
|---|---|
| Offline tests | 837 tests pass on Python 3.12, with 4 skipped (they need `expect`, Docker, a network install, or an account other than root). Run on 2026-11-09 on the release branch. Before the release they also ran on Python 3.10 and 3.13 in clean containers. The tests use invented fixture feeds and scripted model replies: no network, no key. CI runs them on Ubuntu and macOS (`.github/workflows/ci.yml`) |
| The one-command installer | 64 runs across 27 scenarios (a download source down or slow, a file that fails its checksum, no Python, a folder it must refuse), all ended as they should; installed from supplied files with the network switched off. CI also runs the real install on macOS. It passed on my own Mac on 2026-11-09, from the files built at commit 926837d |
| Browser flows | the demo pages and the app page's flows run in Chromium and the WebKit engine at 390, 1280 and 1600 px (`.github/workflows/stranger.yml`) |
| The commands in the README | `composer demo`, `demo --fast`, `--version`, `sources list`, `compose --help` and `pip install .` were run again on 2026-11-09. `compose` itself was not, because it needs a key and costs money |
| Secret scan | gitleaks found nothing in any commit except one made-up marker string in a test, which its config allows (it is not a key) |
| Private-name test | one test fails if private names, server paths or key shapes appear anywhere in the files or the history (`tests/test_banned.py`) |
| Security review, 2026-11-01 | an AI reviewer attacked Composer as a hostile feed, a hostile web page and a hostile network would; what it found is fixed; a second AI reviewer attacked those fixes. See [SECURITY.md](../SECURITY.md) |
| Release review, 2026-11-08 | an AI reviewer that did not write the code read the changes between release candidate 4 and 0.2.0 (the release workflow, the installer maker, the docs); its findings were fixed and the fixes checked |

## What was checked live

One brief, written from a fresh install in a clean Python 3.13 container with a real Anthropic key and the default model. It made 7 calls in 29 seconds and cost about 8 cents. Every insight got a claim-seal verdict and the seal verified.

## What has not been checked

- The browser tests use Chromium and the WebKit engine, not Safari itself. The installer has run in Linux containers, on GitHub's macOS test machines and on one real Mac (mine, 2026-11-09). Macs differ, so if it fails on yours, open an issue.
- The OpenAI-compatible path has not been run live. It is tested against the documented request and reply shapes only.

Treat Composer as a working experiment, and open an issue if something is off.
