# How Composer was built, and what has been checked

The short version is in the [README](../README.md#how-it-was-built).

## Who did what

- **Me (Arya):** I decide what Composer does. The private version of Composer writes briefs I read, and I click through to the cited articles to see that what a claim says is really there.
- **Claude:** wrote the code, the tests and the first draft of this documentation.
- **What I don't do:** I don't review the code line by line, and no human has audited it. The checks below stand in for that, and every reviewer named here was an AI model.

## What tools have checked

| Check | Result |
|---|---|
| Offline tests | 809 ran on Python 3.10 and 3.13 in clean containers: 0 failed, 13 skipped (they need root, another account or a tool the image lacks). The tests use invented fixture feeds and scripted model replies; no network, no key. The same suite is set to run on Linux, macOS and Windows in GitHub Actions |
| The one-command installer | 64 runs across 27 scenarios (a download source down or slow, a file that fails its checksum, no Python, a folder it must refuse), all ended as they should; installed from supplied files with the network switched off |
| Browser flows | the app page's flows run in Chromium and the WebKit engine at four screen widths (phone to desktop) |
| The commands in the README | run in those containers (the `compose` command, which needs a key, on 3.13 only) |
| Secret scan | gitleaks found nothing in any commit except one made-up marker string in a test, which its config allows (it is not a key) |
| Private-name test | one test fails if private names, server paths or key shapes appear anywhere in the files or the history (`tests/test_banned.py`) |
| Security review, 2026-11-01 | an AI reviewer attacked Composer as a hostile feed, a hostile web page and a hostile network would; what it found is fixed; a second AI reviewer attacked those fixes. See [SECURITY.md](../SECURITY.md) |
| Release review, 2026-11-08 | an AI reviewer that did not write the code read the changes between release candidate 4 and 0.2.0 (the release workflow, the installer maker, the docs); its findings were fixed and the fixes checked |

## What was checked live

One brief, written from a fresh install in a clean Python 3.13 container with a real Anthropic key and the default model. It made 7 calls in 29 seconds and cost about 8 cents. Every insight got a claim-seal verdict and the seal verified.

## What has not been checked

- The one-command installer has been run in Linux containers, not yet on a real Mac. The browser tests use Chromium and the WebKit engine, not Safari itself.
- The OpenAI-compatible path has not been run live. It is tested against the documented request and reply shapes only.

Treat Composer as a working experiment, and open an issue if something is off.
