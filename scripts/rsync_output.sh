#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/out/"

REMOTE_USER="jorijn"
REMOTE_HOST="web02.hosting.jorijn.com"
REMOTE_PATH="/home/jorijn/domains/meshcore.jorijn.com/public_html/"

rsync -avz --delete "$OUTPUT_DIR" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_PATH}"
