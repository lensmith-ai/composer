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
    TMPDIR=/tmp
USER composer
WORKDIR /data
VOLUME ["/data"]
# Documentation only: compose.yaml publishes no app port; Caddy reaches it on the private Compose network.
EXPOSE 8765
ENTRYPOINT ["composer"]
# The planned 0.2 command (plan section 7): bind inside the container only, behind Caddy.
CMD ["up", "--host", "0.0.0.0", "--port", "8765"]

# ---------------------------------------------------------------------------------------------------------------
# Narration is NOT in the default image, and never will be by default.
#
# Optional narration uses kokoro-onnx (MIT) and espeakng-loader (MIT), and espeakng-loader bundles the eSpeak NG
# library, which is GPL-3.0. The Kokoro model and voices (Apache-2.0, about 354 MB) are downloaded into the /data
# volume only when you turn narration on; they are never baked into an image.
#
# A narration image is a separate, opt-in target and tag (`docker build --target narration`, published as
# `<version>-narration`). It is pending phase P3, which adds the narration engine. When it is built, it MUST:
#   - install the narration runtime from a hash-locked requirements file;
#   - ship eSpeak NG's GPL-3.0 licence text in the image;
#   - carry a written source offer: the exact eSpeak NG source and the espeakng-loader sdist that built it are
#     attached to the same GitHub Release for as long as that image is offered (image label + release note);
#   - have its own SBOM listing every one of those components with its licence.
# Until then this target refuses to build, so nobody can publish a narration image by accident.
FROM runtime AS narration
RUN echo "The narration image is pending phase P3 (narration engine). See the notes above this target." >&2 \
 && exit 1

# The default image is the LAST stage, so a plain `docker build .` builds it and never the narration target.
FROM runtime AS default
