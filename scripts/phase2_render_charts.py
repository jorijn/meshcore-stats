#!/usr/bin/env python3
"""
Phase 2: Render charts from snapshot data.

Generates SVG charts for day/week/month/year for both companion and repeater
using matplotlib, reading directly from JSON snapshots.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.charts import render_all_charts, save_chart_stats


def main():
    """Render all charts and save statistics."""
    cfg = get_config()

    log.info("Rendering charts from snapshots...")

    # Check if snapshots exist before rendering
    companion_snapshots = cfg.snapshot_dir / "companion"
    repeater_snapshots = cfg.snapshot_dir / "repeater"

    # Companion charts
    if companion_snapshots.exists() and any(companion_snapshots.rglob("*.json")):
        charts, stats = render_all_charts("companion", cfg.companion_metrics)
        save_chart_stats("companion", stats)
        log.info(f"Rendered {len(charts)} companion charts")
    else:
        log.warn(f"No companion snapshots found in {companion_snapshots}")

    # Repeater charts
    if repeater_snapshots.exists() and any(repeater_snapshots.rglob("*.json")):
        charts, stats = render_all_charts("repeater", cfg.repeater_metrics)
        save_chart_stats("repeater", stats)
        log.info(f"Rendered {len(charts)} repeater charts")
    else:
        log.warn(f"No repeater snapshots found in {repeater_snapshots}")

    log.info("Chart rendering complete")


if __name__ == "__main__":
    main()
