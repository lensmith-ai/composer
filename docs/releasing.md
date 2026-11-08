# Releasing Composer

A release is made from a signed tag. The maintainer signs and pushes the tag; the workflow
`.github/workflows/release.yml` checks it and does the rest, and publishes nothing unless every step before publishing
is green.

## Once, before the first release

These are repository settings and one key file, not code, so no commit can switch them on.

1. **The signing key.** `.github/allowed_signers` holds the maintainer's SSH signing public key (the one GitHub lists on
   the maintainer's account, at `https://api.github.com/users/<user>/ssh_signing_keys`). The workflow checks a release tag's signature against that
   file as it stands on `main`, never against a file the tag itself carries.
2. **A `release` environment** (Settings, Environments) with one secret, `ANTHROPIC_API_KEY`: the key the release
   note's claim-seal judge uses. Only the release-note job reads it. Add a required reviewer if you want a person to
   approve each release before it runs.
3. **Private vulnerability reporting** on (Settings, Security), because SECURITY.md sends reporters there. Secret
   scanning and push protection on.
4. **Packages:** the first image push creates `ghcr.io/lensmith-ai/composer`; make that package public when the
   repository is.

## Each release

1. Move the `[Unreleased]` entries in CHANGELOG.md under a new `## [x.y.z] - date` heading, and set the same
   version in `pyproject.toml` and `composer/__init__.py`. Pre-releases use Python's spelling, such as `0.2.0rc1`, and
   are marked as pre-releases on GitHub.
2. Write the release note draft, `release-notes/x.y.z.json`: a short brief in claim-seal's shape whose every line
   cites `{"id": "changelog", "ref": "Changelog x.y.z"}` or `{"id": "tests", "ref": "Test results x.y.z"}`.
   `tests/fixtures/release-note/draft.json` is a small example. The workflow reads the draft from `main`, not from the
   tag, so a line that fails the check can be fixed on `main` and the run repeated without moving the tag. It still
   checks every line against the tag's own changelog and test results.
3. Merge to main with CI green, then sign a tag on that commit and push it. This runs on the maintainer's machine,
   with their signing key: `git tag -s vx.y.z -m "Lensmith Composer x.y.z"`, then `git push origin vx.y.z`. The push
   starts the workflow. For a tag that is already pushed, run it by hand: Actions, release, Run workflow, branch `main`,
   tag `vx.y.z`. Never move or re-create a signed tag to trigger it.

The workflow then:

| job | what it does | what stops the release |
|---|---|---|
| verify-tag | the tag is annotated, names itself, points at the checked-out commit, is on `main`, has a good signature from the key in `.github/allowed_signers` (as on `main`), matches `pyproject.toml`, and has no release yet | any of those failing; a manual run not started from `main` |
| test | the offline suite, recorded as `test-results.json` | any failure or error |
| build | sdist and wheel with hash-locked tools; the wheel installed into an empty venv and run; a CycloneDX SBOM of that venv; SHA256SUMS | the tag not matching `pyproject.toml`; any step failing |
| installer | `install.sh` for this release with every file it fetches pinned by SHA-256, and the dependency files it may fetch from the release (certifi's and setuptools' wheels, claim-seal's pinned archive and the wheel built from it), each checked against a hash written in the repository first | a hash that does not match; a file missing |
| release-note | `scripts/release/release_note.py`: every line of the draft checked by claim-seal against this version's changelog section and `test-results.json`; the seal verified | any line partly supported, unsupported, unchecked or citing an unknown title; a missing draft |
| image | after test, build and release-note: the default image (no narration) for linux/amd64 and linux/arm64 to ghcr.io under a candidate tag only (`candidate-<commit>`, a staging image, never named as a release); its SBOM (syft, CycloneDX); provenance and SBOM attested to the image digest | a failed build, push or attestation |
| promote | after every job above: the signed tag is checked once more, then the version tag (`<version>`) is put on the attested candidate's digest, with no rebuild. This is the only step that gives an image a release's tag | the tag no longer pointing at the checked commit; no digest from the image job |
| publish | SHA256SUMS over every file; build provenance for every file; an SBOM attestation for the wheel and sdist; the GitHub Release, made as a draft and published only when every file is attached, with the note as its text | the tag no longer pointing at the checked commit; a file missing |
| installer-to-main | after the release: the release's own `install.sh` (checked against the release's SHA256SUMS) committed to `main`, where the one-line install is served from | (the release is already complete) if `main` refuses the commit, commit that file by hand |

The attestations name the workflow as it stood on `main` when it ran; the job log shows the tag and commit it built. Provenance
covers the files the workflow built or made (not certifi's and setuptools' wheels or claim-seal's source archive, which are
checked copies of upstream files). Two things to know when a run fails: if `publish` fails after `promote`, the `<version>`
image tag already exists, and a re-run replaces it with the rebuilt image; and `verify-tag` cannot see a leftover draft
release, so delete a failed draft by hand before re-running.

## The one-command installer

`scripts/install/build_install.py` makes `install.sh` for a release: the template with this release's SHA-256 pins and the
fetch library copied from `setup.sh`. The release workflow's `installer` job runs `scripts/release/make_installer.py`, which
gathers the files by their usual names (the sdist and wheel from the build job; certifi's wheel and setuptools' wheel, hashes in
`scripts/install/pinned-extras.json`; claim-seal's archive at the commit `pyproject.toml` pins, hash from `pyproject.toml`; and
claim-seal's wheel built from that archive) and calls it. To do the same by hand, put those files in one folder, then:

```sh
python scripts/install/build_install.py --release DIR --out OUT      # writes install.sh, install.sh.sha256, install-pins.json
```

The release carries `install.sh`, `install.sh.sha256` and the dependency files, and the workflow commits `install.sh` to the
root of `main` (its address is `https://raw.githubusercontent.com/lensmith-ai/composer/main/install.sh`, a build option
`--install-url`). Publish the same files at the mirror address when there is one. Before a release, run the fault-injection
benchmark (`tests/install_faults/run_faults.py --help`); every scenario must pass 3 of 3.

## Release candidates, for a test before a release

`scripts/release/rc.py` builds candidates from chosen commits the way the workflow builds a release, so a test on
a real computer (install one candidate, then update to the next) uses real release files, not a working copy:

```sh
python scripts/release/rc.py --version 0.2.0 --rc 1=<commit> --rc 2=<commit> --out rc-0.2.0
```

For each candidate it makes a fresh shallow clone of that commit, runs the test job (`pip install .` into an empty
environment, then `scripts/release/test_results.py`) and the build job (the hash-locked release tools, then
`scripts/release/build.py --tag v0.2.0rc<N>`), and writes the publish job's SHA256SUMS. The commit must already say
version `0.2.0rc<N>`, as the workflow requires; `--stamp-version` writes it into the clone instead, for a test build,
and the manifest says so. A failing test stops it, as it stops a release; `--keep-going` builds anyway and records
the failures. It does not make the release note, the container image or the attestations, which need the release
environment's key, the registry and GitHub's signing.

The output folder holds every candidate's files side by side with one SHA256SUMS for all of them (so
`shasum -a 256 -c SHA256SUMS` checks everything, and `composer update --from-file` finds each file's sum next to
it), a folder per candidate with its own SHA256SUMS, test results and build log, and `rc-manifest.json` (commit,
version, whether it was stamped, test counts, file hashes). Run it in a clean `python:3.13` container, like the
dry run below, for the workflow's Python. The source release (sdist) is the whole project (`MANIFEST.in`), so an
unpacked candidate can run `./setup.sh`.

## What the SBOM says, and why CycloneDX

The SBOM is CycloneDX 1.6 JSON. It is made by `cyclonedx-py` from the virtual environment the release actually
installed the wheel into, so it lists what was built and installed, not what a lock file hoped for. CycloneDX was
chosen over SPDX because it can describe the parts Composer does not ship but fetches on request: the optional
narration parts are listed with scope `excluded` (not in this artifact), each with its licence, and the Kokoro
model files as `data` components with their download address and SHA-256. Both formats are accepted by GitHub's
SBOM attestations; one format for the package and the image keeps them comparable.

**Narration and the GPL.** Optional narration uses espeakng-loader, which bundles eSpeak NG (GPL-3.0-or-later), and
phonemizer-fork (GPL-3.0-or-later, pure Python, so the installed package is its source). Neither is ever in the
default image or the package. The narration image (the Dockerfile's `narration` target) is a separate tag; it
ships eSpeak NG's licence text and a source offer (`composer/narration/SOURCE-OFFER.txt`), and the exact eSpeak NG
source must be attached to the same release for as long as that image is offered. The release workflow does not
build or publish the narration image yet; adding it there must add that source attachment in the same change.

## Checking a release

A dry run of the build, in a clean `python:3.13` container (the same commands the build job runs):

```sh
python -m pip install --require-hashes -r scripts/release/release-tools.txt
python scripts/release/build.py --out dist
cd dist && sha256sum -c SHA256SUMS
```

After a release is published, anyone can check a downloaded file (with the [GitHub CLI](https://cli.github.com/)):

```sh
sha256sum -c SHA256SUMS
gh attestation verify lensmith_composer-0.2.0-py3-none-any.whl --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
gh attestation verify oci://ghcr.io/lensmith-ai/composer:0.2.0 --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
```

A checksum only shows the download is complete and matches the list next to it; the attestation shows which
workflow, commit and tag built the file.
