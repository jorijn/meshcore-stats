# =============================================================================
# Stage 1: Build dependencies
# =============================================================================
FROM python:3.12-slim-bookworm AS builder

# Ofelia version and checksums (verified from GitHub releases)
ARG OFELIA_VERSION=0.3.12
ARG TARGETARCH
ARG OFELIA_SHA256_AMD64=cf06d2199abafbd3aa5afe0f8266e478818faacd11555b99200707321035c931
ARG OFELIA_SHA256_ARM64=57760ef7f17a2cd55b5b1e1946f79b91b24bde40d47e81a0d75fd1470d883c1a

# Install build dependencies for Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    libpng-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Download and verify Ofelia binary in builder stage (keeps curl out of runtime)
RUN set -ex; \
    if [ "$TARGETARCH" = "amd64" ]; then \
        OFELIA_SHA256="$OFELIA_SHA256_AMD64"; \
    elif [ "$TARGETARCH" = "arm64" ]; then \
        OFELIA_SHA256="$OFELIA_SHA256_ARM64"; \
    else \
        echo "Unsupported architecture: $TARGETARCH" && exit 1; \
    fi; \
    curl -fsSL "https://github.com/mcuadros/ofelia/releases/download/v${OFELIA_VERSION}/ofelia_${OFELIA_VERSION}_linux_${TARGETARCH}.tar.gz" -o /tmp/ofelia.tar.gz \
    && echo "${OFELIA_SHA256}  /tmp/ofelia.tar.gz" | sha256sum -c - \
    && tar -xzf /tmp/ofelia.tar.gz -C /usr/local/bin ofelia \
    && rm /tmp/ofelia.tar.gz \
    && chmod +x /usr/local/bin/ofelia

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# =============================================================================
# Stage 2: Runtime
# =============================================================================
FROM python:3.12-slim-bookworm

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
COPY --from=builder /usr/local/bin/ofelia /usr/local/bin/ofelia

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
# - STATE_DIR/OUT_DIR: Default paths for Docker volumes
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    MPLCONFIGDIR=/tmp/matplotlib \
    STATE_DIR=/data/state \
    OUT_DIR=/out

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
