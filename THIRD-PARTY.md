# Third-party code and licences

Composer's own code is MIT licensed (see LICENSE). This file lists everything else Composer installs or ships,
including the optional parts, with the licence each one states. The licences were read from each package's own
metadata and licence files at the pinned version (and from the project's repository where the package states none).
Every package pinned in `pyproject.toml`, `composer/narration/requirements.lock`,
`composer/extraction-requirements.lock` and `scripts/release/release-tools.txt` has a row here;
`tests/test_third_party.py` fails if one is missing or its version differs.

## In short: what is GPL, and what that means for you

- **The core install has no GPL code.** `pip install .`, `./setup.sh` without narration, and the Python packages in
  the default container image are Composer (MIT), claim-seal (MIT) and pip (MIT), on Python (PSF-2.0).
- **Optional narration brings GPL code.** Two parts of it are under **GPL-3.0-or-later**: the eSpeak NG speech
  library and its data, which come inside the espeakng-loader package, and **phonemizer-fork**, the Python package
  kokoro-onnx uses to turn text into sounds. Narration also brings parts under the LGPL (libsndfile inside soundfile,
  libquadmath inside numpy) and numpy's copy of the GCC runtime (libgfortran), which is GPL-3.0-or-later with the GCC
  Runtime Library Exception; that exception means it puts no GPL terms on the programs that use it.
- **The optional article parser brings no GPL terms you must take.** Its tld package is offered under MPL-1.1,
  GPL-2.0-only or LGPL-2.1-or-later, at your choice; lxml's wheel contains GNU libiconv (LGPL-2.1).
- **The container images contain GPL system software.** Like every Debian or Alpine based image, the default image's
  Debian 13 base and the Caddy image's Alpine base include GPL programs and libraries (for example bash and
  coreutils; BusyBox). The Python in the default image has optional `readline` and `dbm.gnu` modules that load GNU
  readline and GDBM (GPL-3.0-or-later); Composer imports neither.

What it means. The GPL sets conditions on passing copies to other people, not on using them. If you install
narration on your own computer or server and use it, including serving briefs from that server to other people,
the GPL asks nothing more of you. If you give someone else a copy that contains the GPL parts (for example, you
publish a container image with narration in it, or hand over an app folder with the narration runtime), you must
pass those parts on under GPL-3.0-or-later: include their licence text and offer their complete source. Composer's
own code stays MIT, which is compatible with the GPL; but narration's worker (`composer/narration/worker.py`) loads
phonemizer-fork and eSpeak NG in its own process, so treat a copy that includes the narration runtime as a combined
work under GPL-3.0-or-later. The opt-in narration image does this: it ships eSpeak NG's licence text and a written
source offer (`composer/narration/SOURCE-OFFER.txt`), and phonemizer-fork's source and licence are the installed
package itself. This is guidance, not legal advice.

## The package: what `pip install .` installs (required)

| name | version | licence | required or optional | how it is used |
|---|---|---|---|---|
| [claim-seal](https://github.com/lensmith-ai/claim-seal) | 0.2.0, commit `b0fdf6126196509984d3480867bd4cf861a19f98` | MIT | required | The checking and sealing step. Installed by `pip install .` from GitHub's archive of that exact commit, whose SHA-256 pip checks; not copied into this repository. It has no dependencies of its own. |
| [certifi](https://github.com/certifi/python-certifi) | 2026.10.23 (pinned in `pyproject.toml`) | MPL-2.0 | required | Mozilla's list of trusted certificate authorities. Used only when the Python you run Composer with has none of its own (python.org's macOS Python before its "Install Certificates" step, or a private Python on a computer without the ca-certificates package); otherwise your system's list is used. See `composer/tls.py`. |
| [setuptools](https://github.com/pypa/setuptools) | 84.2.1 (pinned in `pyproject.toml`) | MIT | required to build | Builds the package when you run `pip install .`. Not used at run time. |
| [pip](https://github.com/pypa/pip) | the version your Python's `venv` brings (26.2.2 in the default image) | MIT | required | Installs Composer into its private environment, and the optional parts from their lock files. |

Everything else Composer runs on is the Python standard library (Python 3.10 or newer; PSF-2.0).

## The Python `./setup.sh` can download (optional)

Only when this computer has no Python 3.10 or newer and you say yes (or pass `--python-download`).

| name | version | licence | required or optional | how it is used |
|---|---|---|---|---|
| [uv](https://github.com/astral-sh/uv) | 0.5.29, checked by SHA-256 (`setup.sh`) | MIT OR Apache-2.0 | optional | Downloads and installs the private Python into the app folder. |
| CPython from [python-build-standalone](https://github.com/astral-sh/python-build-standalone) | 3.12.9, build 20250205 (the one uv 0.5.29 installs) | PSF-2.0 (Python); the libraries built into it are under permissive licences | optional | The private Python. Its project builds it against libedit instead of GNU readline, and without the GDBM module, so that it contains no GPL code. It brings pip 24.3.1 (MIT). |

## The container images and the always-on setup

| name | version | licence | required or optional | how it is used |
|---|---|---|---|---|
| [Python](https://www.python.org/) official image | `python:3.13.18-slim-trixie`, pinned by digest in `Dockerfile` | PSF-2.0 (Python); 87 Debian 13 packages under their own licences, many GPL-2.0 or GPL-3.0 (bash, coreutils, grep, sed, tar, dpkg, GNU readline, GDBM and others) | required for the image | The base of Composer's image. The Debian packages are unmodified and their source is published by Debian. The release's image SBOM lists every package in it. |
| [Caddy](https://caddyserver.com/) official image | 2.11.7, pinned by digest in `compose.yaml` | Apache-2.0 (Caddy, built with Go modules under their own licences; `caddy build-info` lists them); its Alpine Linux 3.23 base has packages under their own licences, including BusyBox and apk-tools (GPL-2.0-only) | required for the always-on setup | HTTPS and the login in front of Composer. Pulled by Docker from Docker Hub; not part of Composer's image. |

## Narration (optional)

Not in the package or the default image. Installed only when you choose narration (in setup, or the opt-in
`narration` image), from the hash-locked `composer/narration/requirements.lock`, wheels only, with `--no-deps`: the
lock is the complete list. Some packages differ by Python version; the lock picks one row per version. Also listed
in `scripts/release/optional-components.json` and in every release SBOM.

| name | version | licence | required or optional | notes |
|---|---|---|---|---|
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | 0.5.0 | MIT | optional (narration) | The speech engine. |
| [espeakng-loader](https://github.com/thewh1teagle/espeakng-loader) | 0.2.4 | none stated in the 0.2.4 package; its repository added an MIT licence in November 2025, after 0.2.4 | optional (narration) | Loads the eSpeak NG library it contains (next row); needed by kokoro-onnx. |
| eSpeak NG (inside espeakng-loader) | 1.52.0 | **GPL-3.0-or-later** | optional (narration) | The library `libespeak-ng.so` and its `espeak-ng-data` files. The narration image ships its licence text and a source offer. |
| [phonemizer-fork](https://pypi.org/project/phonemizer-fork/) | 3.3.2 | **GPL-3.0-or-later** | optional (narration) | Turns text into phonemes for kokoro-onnx, using eSpeak NG. Pure Python: the installed package is its source, and its licence text is in its `dist-info` folder. |
| [onnxruntime](https://github.com/microsoft/onnxruntime) | 1.24.3 (Python 3.10), 1.31.1 (3.11 and newer) | MIT (its own notices for the code it includes are in `onnxruntime/ThirdPartyNotices.txt`) | optional (narration) | Runs the model; needed by kokoro-onnx. |
| [numpy](https://numpy.org/) | 2.2.6 (Python 3.10), 2.4.6 (3.11), 2.5.4 (3.12 and newer) | BSD-3-Clause (2.4.6 and 2.5.4 state BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 for the code they include); the Linux wheels contain OpenBLAS (BSD-3-Clause), libgfortran (GPL-3.0-or-later WITH GCC-exception-3.1) and libquadmath (LGPL-2.1-or-later) | optional (narration) | Needed by kokoro-onnx, onnxruntime and soundfile. |
| [soundfile](https://github.com/bastibe/python-soundfile) | 0.13.1 | BSD-3-Clause; contains libsndfile (LGPL-2.1, licence text in the wheel) | optional (narration) | Writes the audio file (MP3, or WAV where it cannot write MP3). |
| attrs | 26.1.0 | MIT | optional (narration) | Needed by jsonschema, phonemizer-fork and referencing. |
| babel | 2.18.0 | BSD-3-Clause | optional (narration) | Needed by csvw. |
| cffi | 2.1.1 | MIT-0 | optional (narration) | Needed by soundfile. |
| cloudpickle | 3.1.2 | BSD-3-Clause | optional (narration) | Needed by joblib. |
| csvw | 4.1.1 | Apache-2.0 | optional (narration) | Needed by segments. |
| dlinfo | 2.0.0 | MIT | optional (narration) | Needed by phonemizer-fork. |
| flatbuffers | 25.12.19 | Apache-2.0 | optional (narration) | Needed by onnxruntime. |
| isodate | 0.7.2 | BSD-3-Clause | optional (narration) | Needed by csvw and rdflib. |
| joblib | 1.6.0 | BSD-3-Clause | optional (narration) | Needed by phonemizer-fork. |
| jsonschema | 4.26.0 | MIT | optional (narration) | Needed by csvw. |
| jsonschema-specifications | 2025.9.1 | MIT | optional (narration) | Needed by jsonschema. |
| language-tags | 1.3.2 | MIT | optional (narration) | Needed by csvw. |
| mpmath | 1.3.0 (Python 3.10 only) | BSD-3-Clause | optional (narration) | Needed by sympy. |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | optional (narration) | Needed by onnxruntime. |
| protobuf | 7.36.2 | BSD-3-Clause | optional (narration) | Needed by onnxruntime. |
| pycparser | 3.11 (Python 3.10), 3.12 (3.11 and newer) | BSD-3-Clause | optional (narration) | Needed by cffi. |
| pyparsing | 3.3.3 | MIT | optional (narration) | Needed by rdflib. |
| python-dateutil | 3.0.0 (Python 3.10), 4.0.0 (3.11 and newer) | 3.0.0: Apache-2.0 OR BSD-3-Clause; 4.0.0: BSD-3-Clause | optional (narration) | Needed by csvw. |
| rdflib | 7.6.0 | BSD-3-Clause | optional (narration) | Needed by csvw. |
| referencing | 0.37.0 | MIT | optional (narration) | Needed by jsonschema and jsonschema-specifications. |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python | optional (narration) | Needed by segments. |
| rfc3986 | 1.5.0 | Apache-2.0 | optional (narration) | Needed by csvw. |
| rpds-py | 0.30.0 (Python 3.10), 2026.9.1 (3.11 and newer) | MIT | optional (narration) | Needed by jsonschema and referencing. |
| segments | 2.4.0 | Apache-2.0 | optional (narration) | Needed by phonemizer-fork. |
| six | 1.17.0 (Python 3.10 only) | MIT | optional (narration) | Needed by python-dateutil. |
| sympy | 1.14.0 (Python 3.10 only) | BSD-3-Clause | optional (narration) | Needed by onnxruntime (1.24.3). |
| termcolor | 3.3.0 | MIT | optional (narration) | Needed by csvw. |
| typing-extensions | 4.16.0 | PSF-2.0 | optional (narration) | Needed by phonemizer-fork and referencing. |
| tzdata | 2026.6 | Apache-2.0 | optional (narration) | Needed by python-dateutil. |
| uritemplate | 4.2.0 | BSD-3-Clause OR Apache-2.0 | optional (narration) | Needed by csvw. |
| Kokoro-82M model and voices (`kokoro-v1.0.onnx`, `voices-v1.0.bin`) | release `model-files-v1.0`, pinned by SHA-256 in `composer/narration/__init__.py` | Apache-2.0 | optional (narration) | Downloaded into your data folder only when you turn narration on; never in an image. |

## Article parser (optional)

Not in the package or the image. Installed only when you choose it in setup, from the hash-locked
`composer/extraction-requirements.lock` (every package pinned, every file's SHA-256 checked, wheels only); there is
no pip extra for it. Also listed in `scripts/release/optional-components.json` and in every release SBOM.

| name | version | licence | required or optional | notes |
|---|---|---|---|---|
| [trafilatura](https://github.com/adbar/trafilatura) | 2.3.1 | Apache-2.0 | optional (parser) | The parser itself. |
| babel | 2.18.0 | BSD-3-Clause | optional (parser) | Needed by courlan. |
| certifi | 2026.7.22 | MPL-2.0 | optional (parser) | Needed by trafilatura. |
| charset-normalizer | 3.5.2 | MIT | optional (parser) | Needed by htmldate and trafilatura. |
| courlan | 1.4.0 | Apache-2.0 | optional (parser) | Needed by trafilatura. |
| dateparser | 1.4.3 | BSD-3-Clause | optional (parser) | Needed by htmldate. |
| htmldate | 1.11.0 | Apache-2.0 | optional (parser) | Needed by trafilatura. |
| justext | 3.0.2 | BSD-2-Clause | optional (parser) | Needed by trafilatura. |
| lxml | 6.1.3 | BSD-3-Clause; the wheels contain zlib (Zlib), GNU libiconv (LGPL-2.1), libxml2, libxslt and libexslt (MIT) | optional (parser) | Needed by htmldate, justext, lxml-html-clean and trafilatura. |
| lxml-html-clean | 0.4.5 | BSD-3-Clause | optional (parser) | Needed by lxml. |
| python-dateutil | 2.9.0.post0 | Apache-2.0 OR BSD-3-Clause | optional (parser) | Needed by dateparser and htmldate. |
| pytz | 2026.5 | MIT | optional (parser) | Needed by dateparser. |
| regex | 2026.9.29 | Apache-2.0 AND CNRI-Python | optional (parser) | Needed by dateparser. |
| six | 1.17.0 | MIT | optional (parser) | Needed by python-dateutil. |
| tld | 0.13.2 | MPL-1.1 OR GPL-2.0-only OR LGPL-2.1-or-later (your choice) | optional (parser) | Needed by courlan. |
| tzdata | 2026.5 (Windows only) | Apache-2.0 | optional (parser) | Needed by tzlocal on Windows. |
| tzlocal | 5.4.4 | MIT | optional (parser) | Needed by dateparser. |
| urllib3 | 2.8.0 | MIT | optional (parser) | Needed by courlan, htmldate and trafilatura. |

## Release and CI tools (not part of Composer)

Used only by this repository's release and CI workflows; never installed by Composer. The Python tools are
hash-locked in `scripts/release/release-tools.txt`.

| name | version | licence | required or optional | how it is used |
|---|---|---|---|---|
| [build](https://github.com/pypa/build) | 1.6.1 | MIT | release only | Builds the sdist and wheel. |
| [cyclonedx-bom](https://github.com/CycloneDX/cyclonedx-python) | 7.5.0 | Apache-2.0 | release only | Makes the SBOM. |
| cyclonedx-python-lib | 11.12.0 | Apache-2.0 | release only | Needed by cyclonedx-bom. |
| arrow | 1.4.0 | Apache-2.0 | release only | Needed by isoduration. |
| attrs | 26.1.0 | MIT | release only | Needed by jsonschema and referencing. |
| boolean-py | 5.0 | BSD-2-Clause | release only | Needed by license-expression. |
| chardet | 7.7.0 | 0BSD | release only | Needed by cyclonedx-bom. |
| defusedxml | 0.7.1 | PSF-2.0 | release only | Needed by py-serializable. |
| fqdn | 1.6.0 | MPL-2.0 | release only | Needed by jsonschema. |
| idna | 3.20 | BSD-3-Clause | release only | Needed by jsonschema. |
| isoduration | 20.11.0 | ISC | release only | Needed by jsonschema. |
| jsonpointer | 3.6 | BSD-3-Clause | release only | Needed by jsonschema. |
| jsonschema | 4.26.0 | MIT | release only | Needed by cyclonedx-python-lib. |
| jsonschema-specifications | 2025.9.1 | MIT | release only | Needed by jsonschema. |
| lark | 1.3.1 | MIT | release only | Needed by rfc3987-syntax. |
| license-expression | 30.4.4 | Apache-2.0 | release only | Needed by cyclonedx-python-lib. |
| lxml | 6.1.3 | BSD-3-Clause; the wheels contain zlib, GNU libiconv (LGPL-2.1), libxml2, libxslt and libexslt | release only | Needed by cyclonedx-python-lib. |
| packageurl-python | 0.17.6 | MIT | release only | Needed by cyclonedx-bom and cyclonedx-python-lib. |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | release only | Needed by build, cyclonedx-bom and pip-requirements-parser. |
| pip-requirements-parser | 32.0.1 | MIT | release only | Needed by cyclonedx-bom. |
| py-serializable | 2.1.0 | Apache-2.0 | release only | Needed by cyclonedx-python-lib. |
| pyparsing | 3.3.3 | MIT | release only | Needed by pip-requirements-parser. |
| pyproject-hooks | 1.3.3 | MIT | release only | Needed by build. |
| python-dateutil | 4.0.0 | BSD-3-Clause | release only | Needed by arrow. |
| referencing | 0.37.0 | MIT | release only | Needed by cyclonedx-python-lib, jsonschema and jsonschema-specifications. |
| rfc3339-validator | 0.1.4 | MIT | release only | Needed by jsonschema. |
| rfc3986-validator | 0.1.1 | MIT | release only | Needed by jsonschema. |
| rfc3987-syntax | 1.1.0 | MIT | release only | Needed by jsonschema. |
| rpds-py | 2026.9.1 | MIT | release only | Needed by jsonschema and referencing. |
| setuptools | 84.2.1 | MIT | release only | Builds the package. |
| six | 1.17.0 | MIT | release only | Needed by rfc3339-validator. |
| sortedcontainers | 2.4.0 | Apache-2.0 | release only | Needed by cyclonedx-python-lib. |
| tzdata | 2026.6 | Apache-2.0 | release only | Needed by arrow and python-dateutil. |
| uri-template | 1.3.0 | MIT | release only | Needed by jsonschema. |
| webcolors | 25.10.0 | BSD-3-Clause | release only | Needed by jsonschema. |
| [gitleaks](https://github.com/gitleaks/gitleaks) | 8.30.1, checked by SHA-256 | MIT | CI only | Secret scan in CI. |
| [actionlint](https://github.com/rhysd/actionlint) | 1.7.12, checked by SHA-256 | MIT | CI only | Lints the workflows in CI. |
| GitHub Actions in `.github/workflows/` (`actions/*`; `docker/*` and `anchore/sbom-action`) | pinned by full commit SHA | MIT (`actions/*`); Apache-2.0 (`docker/*`, `anchore/sbom-action`) | CI only | CI and releases. |

## The animated replay

`composer/web/window/` (the scripts and styles of the replay window) comes from Composer's own
app screen, by the same authors, under this repository's MIT licence. Its comments, including
those inside an embedded stylesheet, were removed for publication; otherwise the code is
unchanged apart from renamed element ids. The page around the window (`docs/demo/index.html`,
`site.css`, `frame.js`) and `window/standalone.js` were written for this repository. The pages load no fonts,
scripts or styles from other sites.

## The README screenshots

| name | version | licence | required or optional | how it is used |
|---|---|---|---|---|
| [Playwright](https://github.com/microsoft/playwright) | any recent version | Apache-2.0 | not used by Composer | Took the screenshots in `docs/readme/` from the static demo (`docs/readme/capture.mjs`). Not part of the package and not needed to run Composer. |

## Audit note

No dependency-audit tool (such as pip-audit) was run, because one was not available offline
where this repository was prepared. The core install is three packages (certifi, claim-seal and setuptools), both pinned to
exact versions; every optional package is pinned and hash-checked by its lock file, listed above.
