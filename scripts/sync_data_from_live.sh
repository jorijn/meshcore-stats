#!/usr/bin/env bash
# Sync data directory from live system to local testing environment
# Uses rsync to only update newer files and delete removed ones

set -euo pipefail

LIVE_HOST="192.168.1.7"
LIVE_PATH="~/apps/meshcore-stats/data/"
LOCAL_PATH="$(dirname "$0")/../data/"

rsync -av --delete "${LIVE_HOST}:${LIVE_PATH}" "${LOCAL_PATH}"
