#!/usr/bin/env python3
"""
Backfill RRD databases from historical snapshots.

Iterates through all existing snapshots in chronological order
and updates the RRD databases. Useful after recreating RRD files.

Usage:
    python scripts/backfill_rrd.py [companion|repeater|all]
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.jsondump import load_snapshot
from meshmon.extract import extract_metrics
from meshmon.rrd import create_rrd, update_rrd
from meshmon.snapshot import build_companion_merged_view, build_repeater_merged_view


def get_all_snapshots(role: str) -> list[tuple[Path, int]]:
    """
    Get all snapshot paths for a role, sorted by timestamp.

    Returns list of (path, timestamp) tuples.
    """
    cfg = get_config()
    snapshots_dir = cfg.snapshot_dir / role

    if not snapshots_dir.exists():
        return []

    snapshots = []
    for json_file in snapshots_dir.rglob("*.json"):
        snapshot = load_snapshot(json_file)
        if snapshot and snapshot.get("ts"):
            snapshots.append((json_file, snapshot["ts"]))

    # Sort by timestamp
    snapshots.sort(key=lambda x: x[1])
    return snapshots


def backfill_role(role: str) -> int:
    """
    Backfill RRD for a specific role.

    Returns number of updates processed.
    """
    cfg = get_config()

    if role == "companion":
        metrics = cfg.companion_metrics
        step = cfg.companion_step
        build_merged = build_companion_merged_view
    else:
        metrics = cfg.repeater_metrics
        step = cfg.repeater_step
        build_merged = build_repeater_merged_view

    # Get all snapshots sorted by time
    snapshots = get_all_snapshots(role)

    if not snapshots:
        log.warn(f"No {role} snapshots found")
        return 0

    log.info(f"Found {len(snapshots)} {role} snapshots")

    # Get earliest timestamp for RRD creation
    earliest_ts = snapshots[0][1]

    # Create RRD if needed (with start time before first snapshot)
    create_rrd(role, metrics, step, start_time=earliest_ts)

    # Process each snapshot
    updated = 0
    skipped = 0
    errors = 0
    last_ts = 0

    for path, ts in snapshots:
        # Skip if timestamp not strictly increasing
        if ts <= last_ts:
            skipped += 1
            continue

        snapshot = load_snapshot(path)
        if not snapshot:
            errors += 1
            continue

        # Check for skip reason (repeater)
        if snapshot.get("skip_reason"):
            values = {name: None for name in metrics.keys()}
        else:
            merged = build_merged(snapshot)
            values = extract_metrics(merged, metrics)

        # Update RRD
        if update_rrd(role, ts, values, metrics):
            updated += 1
            last_ts = ts
        else:
            errors += 1

    log.info(f"{role}: {updated} updates, {skipped} skipped (duplicate ts), {errors} errors")
    return updated


def main():
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) > 1:
        target = sys.argv[1].lower()
    else:
        target = "all"

    if target not in ("companion", "repeater", "all"):
        print(f"Usage: {sys.argv[0]} [companion|repeater|all]")
        sys.exit(1)

    log.info(f"Backfilling RRD databases: {target}")

    total = 0

    if target in ("companion", "all"):
        total += backfill_role("companion")

    if target in ("repeater", "all"):
        total += backfill_role("repeater")

    log.info(f"Backfill complete: {total} total updates")


if __name__ == "__main__":
    main()
