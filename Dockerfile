# syntax=docker/dockerfile:1.7

FROM ghcr.io/astral-sh/uv:0.9.24@sha256:816fdce3387ed2142e37d2e56e1b1b97ccc1ea87731ba199dc8a25c04e4997c5 AS uv

FROM golang:1.25-bookworm@sha256:2c7c65601b020ee79db4c1a32ebee0bf3d6b298969ec683e24fcbea29305f10e AS ofelia-builder
ARG OFELIA_VERSION=0.3.12
ARG TARGETARCH

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/ofelia
RUN git clone --depth 1 --branch "v${OFELIA_VERSION}" https://github.com/mcuadros/ofelia.git .

RUN --mount=type=cache,target=/root/.cache/go-build \
    --mount=type=cache,target=/go/pkg/mod \
    set -eux; \
    case "$TARGETARCH" in \
      amd64|arm64) GOARCH="$TARGETARCH" ;; \
      *) echo "Unsupported architecture: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    CGO_ENABLED=0 GOOS=linux GOARCH="$GOARCH" \
      go build -trimpath -ldflags "-s -w" -o /usr/local/bin/ofelia .

FROM python:3.14-slim-bookworm@sha256:3be2c910db2dacfb3e576f94c7ffc07c10b115cbcd3de99d49bfb0b4ccfd75e7 AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    libpng-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /uvx /usr/local/bin/

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/opt/venv

COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project

FROM python:3.14-slim-bookworm@sha256:3be2c910db2dacfb3e576f94c7ffc07c10b115cbcd3de99d49bfb0b4ccfd75e7

ARG BUILD_DATE=1970-01-01T00:00:00Z
ARG VCS_REF=unknown
ARG VERSION=dev

LABEL org.opencontainers.image.source="https://github.com/jorijn/meshcore-stats" \
    org.opencontainers.image.description="MeshCore Stats - LoRa mesh network monitoring" \
    org.opencontainers.image.licenses="MIT" \
    org.opencontainers.image.created=$BUILD_DATE \
    org.opencontainers.image.revision=$VCS_REF \
    org.opencontainers.image.version=$VERSION

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    fontconfig \
    fonts-dejavu-core \
    libfreetype6 \
    libpng16-16 \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && fc-cache -f \
    && find /usr /bin /sbin /usr/local /usr/lib -perm /6000 -type f -exec chmod a-s {} + 2>/dev/null || true

RUN set -eux; \
    if ! getent group dialout >/dev/null; then groupadd -r dialout; fi; \
    groupadd -g 1000 meshmon; \
    useradd -u 1000 -g 1000 -G dialout -m -s /usr/sbin/nologin meshmon; \
    mkdir -p /app /data/state /out /tmp/matplotlib; \
    chown -R meshmon:meshmon /app /data /out /tmp/matplotlib

COPY --from=ofelia-builder /usr/local/bin/ofelia /usr/local/bin/ofelia
COPY --from=builder /opt/venv /opt/venv

COPY --chown=meshmon:meshmon src/ /app/src/
COPY --chown=meshmon:meshmon scripts/ /app/scripts/
COPY --chown=meshmon:meshmon docker/ofelia.ini /app/ofelia.ini

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    XDG_CACHE_HOME=/tmp \
    HOME=/tmp

WORKDIR /app

USER 1000:1000

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["ofelia", "daemon", "--config=/app/ofelia.ini"]

HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/data/state/metrics.db').execute('SELECT 1')" || exit 1
