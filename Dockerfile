# =============================================================================
# Stage 0: Ofelia binary
# =============================================================================
FROM golang:1.25-bookworm@sha256:2c7c65601b020ee79db4c1a32ebee0bf3d6b298969ec683e24fcbea29305f10e AS ofelia-builder

# Ofelia version (built from source for multi-arch support)
ARG OFELIA_VERSION=0.3.12
ARG TARGETARCH
ARG TARGETVARIANT

RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /src/ofelia
RUN git clone --depth 1 --branch "v${OFELIA_VERSION}" https://github.com/mcuadros/ofelia.git /src/ofelia

RUN set -ex; \
    if [ "$TARGETARCH" = "amd64" ]; then \
        GOARCH="amd64"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        GOARCH="arm64"; \
    elif [ "$TARGETARCH" = "arm" ] && [ "$TARGETVARIANT" = "v7" ]; then \
        GOARCH="arm"; \
        GOARM="7"; \
    else \
        echo "Unsupported architecture: $TARGETARCH${TARGETVARIANT:+/$TARGETVARIANT}" && exit 1; \
    fi; \
    if [ -n "${GOARM:-}" ]; then \
        export GOARM; \
    fi; \
    CGO_ENABLED=0 GOOS=linux GOARCH="$GOARCH" go build -o /usr/local/bin/ofelia .

# =============================================================================
# Stage 1: Build dependencies
# =============================================================================
FROM python:3.14-slim-bookworm@sha256:3be2c910db2dacfb3e576f94c7ffc07c10b115cbcd3de99d49bfb0b4ccfd75e7 AS builder

# uv version and checksums (verified from GitHub releases)
ARG UV_VERSION=0.9.24
ARG UV_SHA256_AMD64=fb13ad85106da6b21dd16613afca910994446fe94a78ee0b5bed9c75cd066078
ARG UV_SHA256_ARM64=9b291a1a4f2fefc430e4fc49c00cb93eb448d41c5c79edf45211ceffedde3334
ARG UV_SHA256_ARMV7=8d05b55fe2108ecab3995c2b656679a72c543fd9dc72eeb3a525106a709cfdcb
ARG TARGETARCH
ARG TARGETVARIANT

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download and verify uv binary in builder stage
RUN set -ex; \
    if [ "$TARGETARCH" = "amd64" ]; then \
        UV_ARCH="x86_64"; \
        UV_SHA256="$UV_SHA256_AMD64"; \
        UV_LIBC="gnu"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        UV_ARCH="aarch64"; \
        UV_SHA256="$UV_SHA256_ARM64"; \
        UV_LIBC="gnu"; \
    elif [ "$TARGETARCH" = "arm" ] && [ "$TARGETVARIANT" = "v7" ]; then \
        UV_ARCH="armv7"; \
        UV_SHA256="$UV_SHA256_ARMV7"; \
        UV_LIBC="gnueabihf"; \
    else \
        echo "Unsupported architecture: $TARGETARCH${TARGETVARIANT:+/$TARGETVARIANT}" && exit 1; \
    fi; \
    curl -fsSL "https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-${UV_ARCH}-unknown-linux-${UV_LIBC}.tar.gz" \
    -o /tmp/uv.tar.gz \
    && echo "${UV_SHA256}  /tmp/uv.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/uv.tar.gz -C /usr/local/bin --strip-components=1 --wildcards "*/uv" \
    && rm /tmp/uv.tar.gz \
    && chmod +x /usr/local/bin/uv

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH" \
    UV_PROJECT_ENVIRONMENT=/opt/venv

# Install Python dependencies
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir --upgrade pip && \
    uv sync --frozen --no-dev --no-install-project

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.14-slim-bookworm@sha256:3be2c910db2dacfb3e576f94c7ffc07c10b115cbcd3de99d49bfb0b4ccfd75e7

# OCI Labels
LABEL org.opencontainers.image.source="https://github.com/jorijn/meshcore-stats"
LABEL org.opencontainers.image.description="MeshCore Stats - LoRa mesh network monitoring"
LABEL org.opencontainers.image.licenses="MIT"

# Install runtime dependencies
# - tini: init system for proper signal handling
# - libfreetype6, libpng16-16: matplotlib runtime libraries
# - fontconfig, fonts-dejavu-core: fonts for chart text rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    tini \
    libfreetype6 \
    libpng16-16 \
    fontconfig \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    # Build font cache for matplotlib
    && fc-cache -f \
    # Remove setuid/setgid binaries for security
    && find / -perm /6000 -type f -exec chmod a-s {} \; 2>/dev/null || true

# Create non-root user with dialout group for serial access
RUN groupadd -g 1000 meshmon \
    && useradd -u 1000 -g meshmon -G dialout -s /sbin/nologin meshmon \
    && mkdir -p /data/state /out /tmp/matplotlib \
    && chown -R meshmon:meshmon /data /out /tmp/matplotlib

# Copy Ofelia binary from builder (keeps curl out of runtime image)
COPY --from=ofelia-builder /usr/local/bin/ofelia /usr/local/bin/ofelia

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
COPY --chown=meshmon:meshmon src/ /app/src/
COPY --chown=meshmon:meshmon scripts/ /app/scripts/
COPY --chown=meshmon:meshmon docker/ofelia.ini /app/ofelia.ini

# Environment configuration
# - PATH: Include venv so Ofelia can run Python
# - PYTHONPATH: Allow imports from src/meshmon
# - PYTHONUNBUFFERED: Ensure logs are output immediately
# - PYTHONDONTWRITEBYTECODE: Don't create .pyc files
# - MPLCONFIGDIR: Matplotlib font cache directory
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib

WORKDIR /app

# Run as non-root user
USER meshmon

# Use tini as init system for proper signal handling
ENTRYPOINT ["/usr/bin/tini", "--"]

# Run Ofelia scheduler
CMD ["ofelia", "daemon", "--config=/app/ofelia.ini"]

# Health check - verify database is accessible
HEALTHCHECK --interval=5m --timeout=30s --start-period=60s --retries=3 \
    CMD python -c "import sqlite3; sqlite3.connect('/data/state/metrics.db').execute('SELECT 1')" || exit 1
