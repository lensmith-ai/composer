# Third-party code and licences

Composer's own code is MIT licensed (see LICENSE). This file lists everything else it uses.

## Runtime dependency

| name | version | licence | how it is used |
|---|---|---|---|
| [claim-seal](https://github.com/lensmith-ai/claim-seal) | 0.2.0, commit `331d6a06a223c145e286a861c7f568cdb23cbefe` | MIT | The checking and sealing step. Installed by `pip install .` from GitHub's archive of that exact commit, whose SHA-256 pip checks; not copied into this repository. It has no dependencies of its own. |

Everything else Composer runs on is the Python standard library (Python 3.10 or newer).

## Build tool

| name | version | licence | how it is used |
|---|---|---|---|
| [setuptools](https://github.com/pypa/setuptools) | 84.2.1 (pinned in `pyproject.toml`) | MIT | Builds the package when you run `pip install .`. Not used at run time. |

## The container image and the always-on setup

| name | version | licence | how it is used |
|---|---|---|---|
| [Python](https://www.python.org/) official image | `python:3.13.18-slim-trixie`, pinned by digest in `Dockerfile` | PSF-2.0 (Python); Debian packages under their own licences | The base of Composer's image. The release's image SBOM lists every package in it. |
| [Caddy](https://caddyserver.com/) official image | 2.11.7, pinned by digest in `compose.yaml` | Apache-2.0 | HTTPS and the login in front of Composer. Pulled by Docker from Docker Hub; not part of Composer's image. |

Optional narration (not in the package or the default image) uses kokoro-onnx (MIT), espeakng-loader (MIT) with
the eSpeak NG library it bundles (GPL-3.0-or-later), onnxruntime (MIT), soundfile (BSD-3-Clause, with libsndfile,
LGPL-2.1) and the Kokoro model and voices (Apache-2.0). The runtime is installed only when you choose narration, from
the hash-locked `composer/narration/requirements.lock`; the model files are downloaded only then, checked against
their pinned SHA-256 (`composer/narration/__init__.py`). The opt-in narration image ships eSpeak NG's licence text
and a source offer (`composer/narration/SOURCE-OFFER.txt`). They are also listed in
`scripts/release/optional-components.json` and in every release SBOM.

## Release and CI tools (not part of Composer)

| name | version | licence | how it is used |
|---|---|---|---|
| [build](https://github.com/pypa/build), [cyclonedx-bom](https://github.com/CycloneDX/cyclonedx-python) and their dependencies | hash-locked in `scripts/release/release-tools.txt` | MIT, Apache-2.0 and others (see that file's packages) | Build the sdist and wheel, and the SBOM, in the release workflow. |
| [gitleaks](https://github.com/gitleaks/gitleaks) | 8.30.1, checked by SHA-256 | MIT | Secret scan in CI. |
| [actionlint](https://github.com/rhysd/actionlint) | 1.7.12, checked by SHA-256 | MIT | Lints the workflows in CI. |
| GitHub Actions in `.github/workflows/` | pinned by full commit SHA | MIT and Apache-2.0 | CI and releases. |

## The animated replay

`composer/web/window/` (the scripts and styles of the replay window) comes from Composer's own
app screen, by the same authors, under this repository's MIT licence. Its comments, including
those inside an embedded stylesheet, were removed for publication; otherwise the code is
unchanged apart from renamed element ids. The page around the window (`docs/demo/index.html`,
`site.css`, `frame.js`) and `window/standalone.js` were written for this repository.

## The README screenshots

| name | version | licence | how it is used |
|---|---|---|---|
| [Playwright](https://github.com/microsoft/playwright) | any recent version | Apache-2.0 | Took the screenshots in `docs/readme/` from the static demo (`docs/readme/capture.mjs`). Not part of the package and not needed to run Composer. |

## Audit note

No dependency-audit tool (such as pip-audit) was run, because one was not available offline
where this repository was prepared. The full dependency list is the two rows above
(claim-seal and setuptools), both pinned to exact versions.
