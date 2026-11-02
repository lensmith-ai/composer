# Releasing Composer

A release is made by pushing a tag. The workflow `.github/workflows/release.yml` does the rest, and publishes
nothing unless every step before publishing is green.

## Once, before the first release

These are repository settings, not files, so no commit can switch them on.

1. **A `release` environment** (Settings, Environments) with one secret, `ANTHROPIC_API_KEY`: the key the release
   note's claim-seal judge uses. Only the release-note job reads it. Add a required reviewer if you want a person to
   approve each release before it runs.
2. **Private vulnerability reporting** on (Settings, Security), because SECURITY.md sends reporters there.
3. **Packages:** the first image push creates `ghcr.io/lensmith-ai/composer`; make that package public when the
   repository is.

## Each release

1. Move the `[Unreleased]` entries in CHANGELOG.md under a new `## [x.y.z] - date` heading, and set the same
   version in `pyproject.toml`. Pre-releases use Python's spelling, such as `0.2.0rc1`, and are marked as
   pre-releases on GitHub.
2. Write the release note draft, `release-notes/x.y.z.json`: a short brief in claim-seal's shape whose every line
   cites `{"id": "changelog", "ref": "Changelog x.y.z"}` or `{"id": "tests", "ref": "Test results x.y.z"}`.
   `tests/fixtures/release-note/draft.json` is a small example.
3. Merge to main with CI green, then tag that commit and push the tag. This runs on the maintainer's machine, with
   their signing key: `git tag -s vx.y.z`, then `git push origin vx.y.z`.

The workflow then:

| job | what it does | what stops the release |
|---|---|---|
| test | the offline suite, recorded as `test-results.json` | any failure or error |
| build | sdist and wheel with hash-locked tools; the wheel installed into an empty venv and run; a CycloneDX SBOM of that venv; SHA256SUMS | the tag not matching `pyproject.toml`; any step failing |
| release-note | `scripts/release/release_note.py`: every line of the draft checked by claim-seal against this version's changelog section and `test-results.json`; the seal verified | any line partly supported, unsupported, unchecked or citing an unknown title; a missing draft |
| image | the default image (no narration) for linux/amd64 and linux/arm64 to ghcr.io; its SBOM (syft, CycloneDX); provenance and SBOM attested to the image digest | a failed build or push |
| publish | SHA256SUMS over every file; build provenance for every file; an SBOM attestation for the wheel and sdist; the GitHub Release with the note as its text | |

## What the SBOM says, and why CycloneDX

The SBOM is CycloneDX 1.6 JSON. It is made by `cyclonedx-py` from the virtual environment the release actually
installed the wheel into, so it lists what was built and installed, not what a lock file hoped for. CycloneDX was
chosen over SPDX because it can describe the parts Composer does not ship but fetches on request: the optional
narration parts are listed with scope `excluded` (not in this artifact), each with its licence, and the Kokoro
model files as `data` components with their download address and SHA-256. Both formats are accepted by GitHub's
SBOM attestations; one format for the package and the image keeps them comparable.

**Narration and the GPL.** Optional narration uses espeakng-loader, which bundles eSpeak NG (GPL-3.0). It is never
in the default image or the package. The narration image (the Dockerfile's `narration` target) is a separate tag; it
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
# after the first release
sha256sum -c SHA256SUMS
gh attestation verify lensmith_composer-0.2.0-py3-none-any.whl --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
gh attestation verify oci://ghcr.io/lensmith-ai/composer:0.2.0 --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
```

A checksum only shows the download is complete and matches the list next to it; the attestation shows which
workflow, commit and tag built the file.
