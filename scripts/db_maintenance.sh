#!/bin/bash
# Database maintenance script
#
# Runs VACUUM and ANALYZE on the SQLite database to compact it and
# update query statistics.
#
# Recommended: Run monthly via cron
# Example crontab entry:
#   0 3 1 * * cd /home/jorijn/apps/meshcore-stats && ./scripts/db_maintenance.sh
#
# This script will:
# 1. Run VACUUM to compact the database and reclaim space
# 2. Run ANALYZE to update query optimizer statistics
#
# Note: VACUUM acquires an exclusive lock internally. Other processes
# using busy_timeout will wait for it to complete.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_DIR/data/state/metrics.db"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Database not found: $DB_PATH"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting database maintenance..."
echo "Database: $DB_PATH"

echo "Running VACUUM..."
sqlite3 "$DB_PATH" "VACUUM;"

echo "Running ANALYZE..."
sqlite3 "$DB_PATH" "ANALYZE;"

# Get database size
DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
echo "Database size after maintenance: $DB_SIZE"

echo "$(date '+%Y-%m-%d %H:%M:%S') Maintenance complete"
