#!/usr/bin/env python3
"""
Phase 3: Render static HTML site.

Generates static HTML pages using latest snapshots and rendered charts.
Creates day/week/month/year pages for both companion and repeater nodes.
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.jsondump import get_latest_snapshot
from meshmon.html import write_site


def main():
    """Render static site."""
    cfg = get_config()

    log.info("Rendering static site...")

    # Load latest snapshots
    companion_result = get_latest_snapshot("companion")
    companion_snapshot = companion_result[1] if companion_result else None
    if companion_snapshot:
        log.debug(f"Loaded companion snapshot: {companion_result[0]}")
    else:
        log.warn("No companion snapshot found")

    repeater_result = get_latest_snapshot("repeater")
    repeater_snapshot = repeater_result[1] if repeater_result else None
    if repeater_snapshot:
        log.debug(f"Loaded repeater snapshot: {repeater_result[0]}")
    else:
        log.warn("No repeater snapshot found")

    # Write site
    pages = write_site(companion_snapshot, repeater_snapshot)

    log.info(f"Wrote {len(pages)} pages to {cfg.out_dir}")
    log.info("Site rendering complete")


if __name__ == "__main__":
    main()
