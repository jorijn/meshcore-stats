#!/usr/bin/env python3
"""
Phase 2: Update repeater RRD with latest snapshot data.

Loads the newest repeater snapshot and updates the RRD.
Snapshots with skip_reason will update with Unknown values.
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
from meshmon.snapshot import build_repeater_merged_view


def main(snapshot_path: Optional[str] = None):
    """Update repeater RRD."""
    cfg = get_config()

    # Load snapshot
    if snapshot_path:
        path = Path(snapshot_path)
        snapshot = load_snapshot(path)
        if not snapshot:
            log.error(f"Failed to load snapshot: {path}")
            sys.exit(1)
    else:
        result = get_latest_snapshot("repeater")
        if not result:
            log.error("No repeater snapshots found")
            sys.exit(1)
        path, snapshot = result

    log.debug(f"Loaded snapshot: {path}")

    # Get timestamp
    ts = snapshot.get("ts")
    if not ts:
        log.error("Snapshot has no timestamp")
        sys.exit(1)

    # Check for skip reason
    skip_reason = snapshot.get("skip_reason")
    if skip_reason:
        log.info(f"Snapshot indicates skip: {skip_reason}")
        # Update with all Unknown values
        values = {name: None for name in cfg.repeater_metrics.keys()}
    else:
        # Build merged view for metric extraction
        merged = build_repeater_merged_view(snapshot)

        # Extract metric values
        values = extract_metrics(merged, cfg.repeater_metrics)

    log.debug(f"Extracted values: {values}")

    # Update RRD
    success = update_rrd(
        role="repeater",
        ts=ts,
        values=values,
        metrics=cfg.repeater_metrics,
    )

    if success:
        log.info(f"Updated repeater RRD with ts={ts}")
    else:
        log.error("Failed to update repeater RRD")
        sys.exit(1)


if __name__ == "__main__":
    # Accept optional path argument
    path_arg = sys.argv[1] if len(sys.argv) > 1 else None
    main(path_arg)
