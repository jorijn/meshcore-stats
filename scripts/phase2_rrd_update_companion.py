#!/usr/bin/env python3
"""
Phase 2: Update companion RRD with latest snapshot data.

Loads the newest companion snapshot and updates the RRD.
"""

import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.jsondump import get_latest_snapshot, load_snapshot
from meshmon.extract import extract_metrics
from meshmon.rrd import update_rrd
from meshmon.snapshot import build_companion_merged_view


def main(snapshot_path: Optional[str] = None):
    """Update companion RRD."""
    cfg = get_config()

    # Load snapshot
    if snapshot_path:
        path = Path(snapshot_path)
        snapshot = load_snapshot(path)
        if not snapshot:
            log.error(f"Failed to load snapshot: {path}")
            sys.exit(1)
    else:
        result = get_latest_snapshot("companion")
        if not result:
            log.error("No companion snapshots found")
            sys.exit(1)
        path, snapshot = result

    log.debug(f"Loaded snapshot: {path}")

    # Get timestamp
    ts = snapshot.get("ts")
    if not ts:
        log.error("Snapshot has no timestamp")
        sys.exit(1)

    # Build merged view for metric extraction
    merged = build_companion_merged_view(snapshot)

    # Extract metric values
    values = extract_metrics(merged, cfg.companion_metrics)
    log.debug(f"Extracted values: {values}")

    # Update RRD
    success = update_rrd(
        role="companion",
        ts=ts,
        values=values,
        metrics=cfg.companion_metrics,
    )

    if success:
        log.info(f"Updated companion RRD with ts={ts}")
    else:
        log.error("Failed to update companion RRD")
        sys.exit(1)


if __name__ == "__main__":
    # Accept optional path argument
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
