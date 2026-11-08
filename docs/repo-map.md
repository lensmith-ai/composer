# What is in this repository, and the tests

## What is in this repository

| path | what it is |
|---|---|
| `composer/adapters/` | the three source readers: `rss_or_atom`, `hn_json_api`, `html_index` |
| `composer/sanitize.py` | cleans feed text before it reaches a prompt |
| `composer/prompt.py` | the writing prompt and the check on the model's answer |
| `composer/providers.py` | the model layer: Anthropic Messages API and OpenAI-compatible endpoints |
| `composer/pipeline.py` | one brief from start to finish |
| `composer/cli.py`, `composer/server.py` | the `composer` command, `composer up` and `composer serve` |
| `setup.sh`, `composer/installer.py`, `composer/home.py` | the install: its checks, its questions, the app folder and its manifest |
| `composer/narration/` | optional narration: detection, the read-only reuse check, the hash-locked runtime, the worker |
| `composer/doctor.py`, `composer/lifecycle.py`, `composer/scheduler.py` | doctor; backup, restore, update, rollback, uninstall; the daily brief |
| `composer/page.py`, `composer/web/` | the one-file brief page |
| `composer/window.py`, `composer/web/window/` | the animated replay window and its scripts and styles |
| `composer/sources.json` | the six bundled feeds |
| `composer/data/recorded-run.json` | the recorded brief the demo replays |
| `docs/demo/` | the static demo: the animated replay (`index.html`) and the plain page (`brief.html`) |
| `tests/` | offline tests: fixtures only, no network, no key |
| `Dockerfile`, `compose.yaml`, `Caddyfile` | the container image and the always-on setup ([docs/deploy-vps.md](deploy-vps.md)) |
| `tests/deploy/proof.sh` | the always-on proof: HTTPS through Caddy with the login, the app port closed, a backup restored |
| `scripts/release/` | the release build (sdist, wheel, SBOM, checksums), release candidates (`rc.py`), the claim-sealed release note, and the installer maker (`make_installer.py`) |
| `scripts/install/` | the one-command installer: its template (`install.sh.in`), the builder that pins every file by SHA-256, and the pinned dependency hashes |
| `.github/workflows/` | tests on Linux, macOS and Windows, the scans, CodeQL, the nightly proof, and the release (built from the signed tag) |
| `.github/allowed_signers` | the maintainer's public signing key, which the release workflow checks the tag against |


## Tests

Every test runs offline, from invented fixture feeds and scripted model replies. The model
layer is tested with a scripted transport, and the whole pipeline (fetch, screen, write, check,
seal) runs end to end with claim-seal replaying recorded judge answers. Without claim-seal
installed, the 8 pipeline tests are skipped and the rest still run.

```sh
python -m unittest discover -s tests -t tests
```

`tests/test_banned.py` fails if the working tree or the git history holds a server path, an
internal id shape, a key shape, or one of a list of private names (stored as salted hashes). To
add your own terms without publishing them, point `COMPOSER_DENYLIST` at a file outside the
repository, one regular expression per line.
