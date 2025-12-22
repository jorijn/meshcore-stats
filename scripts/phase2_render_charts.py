#!/usr/bin/env python3
"""
Phase 2: Render charts from RRD data.

Generates PNG charts for day/week/month/year for both companion and repeater.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.rrd import render_all_charts, get_rrd_path


def main():
    """Render all charts."""
    cfg = get_config()

    log.info("Rendering charts...")

    # Companion charts
    companion_rrd = get_rrd_path("companion")
    if companion_rrd.exists():
        charts = render_all_charts("companion", cfg.companion_metrics)
        log.info(f"Rendered {len(charts)} companion charts")
    else:
        log.warn(f"Companion RRD not found: {companion_rrd}")

    # Repeater charts
    repeater_rrd = get_rrd_path("repeater")
    if repeater_rrd.exists():
        charts = render_all_charts("repeater", cfg.repeater_metrics)
        log.info(f"Rendered {len(charts)} repeater charts")
    else:
        log.warn(f"Repeater RRD not found: {repeater_rrd}")

    log.info("Chart rendering complete")


if __name__ == "__main__":
    main()
