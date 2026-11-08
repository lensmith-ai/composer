# Releases you can check

Each release lists SHA256SUMS for its files, a CycloneDX SBOM of what the package installs (optional narration
parts listed with their licences), and GitHub artifact attestations for every file and the container image, so
`gh attestation verify` can show which workflow and commit built it. The release is built from a tag signed with the
maintainer's key; the workflow refuses a tag that is not signed, not on `main` or not the one named in
`pyproject.toml`. The release note's factual lines are checked by claim-seal against CHANGELOG.md and the recorded
test results before it is published. How a release is made: [docs/releasing.md](releasing.md).

## Check a download

With the [GitHub CLI](https://cli.github.com/), in the folder where you downloaded the release files:

```sh
sha256sum -c SHA256SUMS          # on a Mac: shasum -a 256 -c SHA256SUMS
gh attestation verify lensmith_composer-0.2.0-py3-none-any.whl --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
gh attestation verify oci://ghcr.io/lensmith-ai/composer:0.2.0 --repo lensmith-ai/composer \
  --signer-workflow lensmith-ai/composer/.github/workflows/release.yml
```

A checksum only shows the download is complete and matches the list next to it. The attestation shows which workflow,
commit and tag built the file. Three files on the release carry no attestation because this workflow did not build them:
certifi's wheel, setuptools' wheel and claim-seal's source archive are copies of upstream files, checked against hashes
written in this repository before they are attached (they are there so the installer has a second place to get them).

## Check the tag

```sh
git clone https://github.com/lensmith-ai/composer && cd composer
git -c gpg.ssh.allowedSignersFile=.github/allowed_signers tag -v v0.2.0
```

It should report a good signature from the key in `.github/allowed_signers`. That is the signing key GitHub lists on the
maintainer's account (it shows as "Verified" on the tag's page).

## Check the installer before you run it

`install.sh` is on the release page too, with its SHA-256. Its text pins every file it will download.
`sh install.sh --show-pins` prints them. See [docs/install.md](install.md).
