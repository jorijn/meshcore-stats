#!/usr/bin/env python3
"""
Phase 2: Initialize RRD files.

Creates RRD files for companion and repeater if they don't exist.
DS names are derived from COMPANION_METRICS and REPEATER_METRICS env vars.
"""

import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.rrd import create_rrd, get_rrd_path


def main():
    """Initialize RRD files."""
    cfg = get_config()
    start_time = int(time.time())

    log.info("Initializing RRD files...")

    # Companion RRD
    log.info(f"Companion RRD: step={cfg.companion_step}s, metrics={list(cfg.companion_metrics.keys())}")
    success = create_rrd(
        role="companion",
        metrics=cfg.companion_metrics,
        step=cfg.companion_step,
        start_time=start_time,
    )
    if success:
        log.info(f"Companion RRD ready: {get_rrd_path('companion')}")
    else:
        log.error("Failed to create companion RRD")

    # Repeater RRD
    log.info(f"Repeater RRD: step={cfg.repeater_step}s, metrics={list(cfg.repeater_metrics.keys())}")
    success = create_rrd(
        role="repeater",
        metrics=cfg.repeater_metrics,
        step=cfg.repeater_step,
        start_time=start_time,
    )
    if success:
        log.info(f"Repeater RRD ready: {get_rrd_path('repeater')}")
    else:
        log.error("Failed to create repeater RRD")


if __name__ == "__main__":
    main()
