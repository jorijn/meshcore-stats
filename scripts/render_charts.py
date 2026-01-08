#!/usr/bin/env python3
"""
Phase 2: Render charts from SQLite database.

Generates SVG charts for day/week/month/year for both companion and repeater
using matplotlib, reading directly from the SQLite metrics database.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon import log
from meshmon.charts import render_all_charts, save_chart_stats
from meshmon.db import get_metric_count, init_db


def main():
    """Render all charts and save statistics."""
    # Ensure database is initialized
    init_db()

    log.info("Rendering charts from database...")

    # Check if data exists before rendering
    companion_count = get_metric_count("companion")
    repeater_count = get_metric_count("repeater")

    # Companion charts
    if companion_count > 0:
        charts, stats = render_all_charts("companion")
        save_chart_stats("companion", stats)
        log.info(f"Rendered {len(charts)} companion charts ({companion_count} data points)")
    else:
        log.warn("No companion metrics in database")

    # Repeater charts
    if repeater_count > 0:
        charts, stats = render_all_charts("repeater")
        save_chart_stats("repeater", stats)
        log.info(f"Rendered {len(charts)} repeater charts ({repeater_count} data points)")
    else:
        log.warn("No repeater metrics in database")

    log.info("Chart rendering complete")


if __name__ == "__main__":
    main()
