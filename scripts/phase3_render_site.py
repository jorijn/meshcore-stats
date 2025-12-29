#!/usr/bin/env python3
"""
Phase 3: Render static HTML site.

Generates static HTML pages using latest metrics from SQLite database
and rendered charts. Creates day/week/month/year pages for both
companion and repeater nodes.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.db import init_db, get_latest_metrics
from meshmon.env import get_config
from meshmon import log
from meshmon.html import write_site


def main():
    """Render static site."""
    # Ensure database is initialized
    init_db()

    cfg = get_config()

    log.info("Rendering static site...")

    # Load latest metrics from database
    companion_row = get_latest_metrics("companion")
    if companion_row:
        log.debug(f"Loaded companion metrics (ts={companion_row.get('ts')})")
    else:
        log.warn("No companion metrics found in database")

    repeater_row = get_latest_metrics("repeater")
    if repeater_row:
        log.debug(f"Loaded repeater metrics (ts={repeater_row.get('ts')})")
    else:
        log.warn("No repeater metrics found in database")

    # Write site
    pages = write_site(companion_row, repeater_row)

    log.info(f"Wrote {len(pages)} pages to {cfg.out_dir}")
    log.info("Site rendering complete")


if __name__ == "__main__":
    main()
