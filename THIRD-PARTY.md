# Third-party code and licences

Composer's own code is MIT licensed (see LICENSE). This file lists everything else it uses.

## Runtime dependency

| name | version | licence | how it is used |
|---|---|---|---|
| [claim-seal](https://github.com/lensmith-ai/claim-seal) | 0.2.0, commit `f0e0a90ab62532a498f63bb7887e079bd0dc8641` | MIT | The checking and sealing step. Installed by `pip install .` from that exact commit; not copied into this repository. It has no dependencies of its own. |

Everything else Composer runs on is the Python standard library (Python 3.10 or newer).

## Build tool

| name | version | licence | how it is used |
|---|---|---|---|
| [setuptools](https://github.com/pypa/setuptools) | 84.2.1 (pinned in `pyproject.toml`) | MIT | Builds the package when you run `pip install .`. Not used at run time. |

## The animated replay

`composer/web/window/` (the scripts and styles of the replay window) comes from Composer's own
app screen, by the same authors, under this repository's MIT licence. Its comments, including
those inside an embedded stylesheet, were removed for publication; otherwise the code is
unchanged apart from renamed element ids.

## The README screenshots

| name | version | licence | how it is used |
|---|---|---|---|
| [Playwright](https://github.com/microsoft/playwright) | any recent version | Apache-2.0 | Took the screenshots in `docs/readme/` from the static demo (`docs/readme/capture.mjs`). Not part of the package and not needed to run Composer. |

## Audit note

No dependency-audit tool (such as pip-audit) was run, because one was not available offline
where this repository was prepared. The full dependency list is the two rows above
(claim-seal and setuptools), both pinned to exact versions.
