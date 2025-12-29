#!/bin/bash
# Database maintenance script
#
# Runs VACUUM and ANALYZE on the SQLite database to compact it and
# update query statistics. Uses flock to prevent concurrent access
# during maintenance.
#
# Recommended: Run monthly via cron
# Example crontab entry:
#   0 3 1 * * cd /home/jorijn/apps/meshcore-stats && ./scripts/db_maintenance.sh
#
# This script will:
# 1. Acquire an exclusive lock on the database
# 2. Run VACUUM to compact the database and reclaim space
# 3. Run ANALYZE to update query optimizer statistics
#
# Note: VACUUM requires exclusive access. Other processes will wait
# (up to busy_timeout) for the lock to be released.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
DB_PATH="$PROJECT_DIR/data/state/metrics.db"
LOCK_FILE="$DB_PATH.maintenance.lock"

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "Database not found: $DB_PATH"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') Starting database maintenance..."
echo "Database: $DB_PATH"

# Use flock to ensure exclusive access during maintenance
# -x: exclusive lock
# -w 60: wait up to 60 seconds for the lock
(
    flock -x -w 60 200 || {
        echo "ERROR: Could not acquire lock after 60 seconds"
        exit 1
    }

    echo "Lock acquired, running VACUUM..."
    sqlite3 "$DB_PATH" "VACUUM;"

    echo "Running ANALYZE..."
    sqlite3 "$DB_PATH" "ANALYZE;"

    # Get database size
    DB_SIZE=$(du -h "$DB_PATH" | cut -f1)
    echo "Database size after maintenance: $DB_SIZE"

    echo "$(date '+%Y-%m-%d %H:%M:%S') Maintenance complete"

) 200>"$LOCK_FILE"

# Clean up lock file
rm -f "$LOCK_FILE"
