# Lensmith Composer: one image for a laptop (`docker compose up`) and a server (docs/deploy-vps.md).
#
# - The base image is pinned by digest, so a rebuild starts from the same bytes.
# - Composer runs as an unprivileged user (uid 10001) on a read-only root filesystem (set in compose.yaml).
# - Everything it keeps lives in ONE volume mounted at /data, the persistent data root. The mount point is never
#   renamed: an update switches the `current` pointer file INSIDE /data, so backups and recovery records under
#   /data stay where they are.
# - No published port: compose.yaml puts Caddy in front for HTTPS and the login.
# - No narration: see the `narration` target at the end.
#
# Build: docker compose build   (or: docker build -t lensmith-composer .)

ARG PYTHON_IMAGE=python:3.13.18-slim-trixie@sha256:76baad6037690d6e8c4397fbcaef17bca6f19eecef822b708fe8fa3417d30bb5

FROM ${PYTHON_IMAGE} AS build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY composer ./composer
# pip fetches claim-seal from GitHub's archive of one commit and refuses it unless its SHA-256 matches
# (see pyproject.toml). The venv is copied whole into the final image; nothing else from this stage is.
RUN python -m venv /venv \
 && /venv/bin/pip install . \
 && /venv/bin/composer --version

FROM ${PYTHON_IMAGE} AS runtime
ARG COMPOSER_VERSION=dev
LABEL org.opencontainers.image.title="Lensmith Composer" \
      org.opencontainers.image.description="Read a few feeds, write a short brief through a lens you choose, and check every claim against the article it cites." \
      org.opencontainers.image.source="https://github.com/lensmith-ai/composer" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.version="${COMPOSER_VERSION}"
RUN groupadd --system --gid 10001 composer \
 && useradd --system --uid 10001 --gid composer --no-create-home --home-dir /nonexistent \
            --shell /usr/sbin/nologin composer \
 && mkdir -p /data \
 && chown composer:composer /data \
 && chmod 0700 /data
COPY --from=build /venv /venv
ENV PATH=/venv/bin:$PATH \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp \
    COMPOSER_DATA=/data
USER composer
WORKDIR /data
VOLUME ["/data"]
# Documentation only: compose.yaml publishes no app port; Caddy reaches it on the private Compose network.
EXPOSE 8765
ENTRYPOINT ["composer"]
# Listen inside the container only, behind Caddy (compose.yaml names the proxy network and the public address).
CMD ["up", "--host", "0.0.0.0", "--port", "8765"]

# ---------------------------------------------------------------------------------------------------------------
# Narration is NOT in the default image, and never will be by default.
#
# Optional narration uses kokoro-onnx (MIT) and espeakng-loader, which bundles the eSpeak NG library
# (GPL-3.0-or-later); kokoro-onnx also uses phonemizer-fork (GPL-3.0-or-later). THIRD-PARTY.md lists every package
# in the narration runtime with its licence. The Kokoro model and voices (Apache-2.0, about 354 MB) are downloaded
# into the /data volume only when you turn narration on (`composer setup --data-only`); they are never baked into an
# image.
#
# The narration image is a separate, opt-in target and tag (`docker build --target narration`, published as
# `<version>-narration`). It:
#   - installs the narration runtime from the hash-locked composer/narration/requirements.lock (wheels only);
#   - ships eSpeak NG's GPL-3.0 licence text (fetched from the eSpeak NG 1.52.0 tag and checked by SHA-256);
#   - carries a written source offer (composer/narration/SOURCE-OFFER.txt): the exact eSpeak NG source and the
#     espeakng-loader sdist are attached to the same GitHub Release for as long as that image is offered.
FROM ${PYTHON_IMAGE} AS narration_build
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1
COPY --from=build /venv /venv
COPY composer/narration/requirements.lock /tmp/narration-requirements.lock
RUN /venv/bin/pip install --require-hashes --no-deps --only-binary :all: -r /tmp/narration-requirements.lock \
 && /venv/bin/python -c "import kokoro_onnx, soundfile, onnxruntime; print('narration runtime', kokoro_onnx.__name__)"
ADD --chmod=644 --checksum=sha256:8ceb4b9ee5adedde47b31e975c1d90c73ad27b6b165a1dcd80c7c545eb65b903 \
    https://raw.githubusercontent.com/espeak-ng/espeak-ng/1.52.0/COPYING /licenses/eSpeak-NG-1.52.0-COPYING.txt

FROM runtime AS narration
LABEL org.opencontainers.image.title="Lensmith Composer with narration" \
      org.opencontainers.image.licenses="MIT AND GPL-3.0-or-later AND BSD-3-Clause AND LGPL-2.1-or-later" \
      org.opencontainers.image.documentation="https://github.com/lensmith-ai/composer/blob/main/THIRD-PARTY.md"
COPY --from=narration_build /venv /venv
COPY --from=narration_build /licenses/ /usr/share/doc/composer-narration/
COPY --chmod=644 composer/narration/SOURCE-OFFER.txt /usr/share/doc/composer-narration/SOURCE-OFFER.txt

# The default image is the LAST stage, so a plain `docker build .` builds it and never the narration target.
FROM runtime AS default
