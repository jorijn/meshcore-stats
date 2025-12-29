#!/usr/bin/env python3
"""Migrate existing JSON snapshots to SQLite database.

This one-time migration script reads all existing JSON snapshots
and inserts them into the SQLite database.

Usage:
    direnv exec . python scripts/migrate_json_to_db.py
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon.db import init_db, insert_companion_metrics, insert_repeater_metrics, get_db_path
from meshmon.jsondump import load_snapshot
from meshmon.snapshot import build_companion_merged_view, build_repeater_merged_view
from meshmon.extract import get_by_path
from meshmon import log


def migrate_companion_snapshots(snapshot_dir: Path) -> tuple[int, int]:
    """Migrate all companion snapshots to database.

    Args:
        snapshot_dir: Base snapshot directory

    Returns:
        (inserted_count, skipped_count)
    """
    base_dir = snapshot_dir / "companion"
    if not base_dir.exists():
        log.warn("No companion snapshots found")
        return (0, 0)

    inserted = 0
    skipped = 0
    errors = 0

    json_files = sorted(base_dir.rglob("*.json"))
    total = len(json_files)
    log.info(f"Found {total} companion snapshots to migrate")

    for i, json_file in enumerate(json_files):
        if (i + 1) % 1000 == 0:
            log.info(f"Progress: {i + 1}/{total} companion snapshots")

        try:
            data = load_snapshot(json_file)
            if not data:
                skipped += 1
                continue

            if data.get("skip_reason"):
                skipped += 1
                continue

            # Build merged view to get derived fields
            merged = build_companion_merged_view(data)
            ts = merged.get("ts")
            if not ts:
                skipped += 1
                continue

            # Extract metrics
            bat_v = get_by_path(merged, "derived.bat_v")
            contacts = get_by_path(merged, "derived.contacts_count")
            uptime = get_by_path(merged, "stats.core.uptime_secs")
            rx = get_by_path(merged, "stats.packets.recv")
            tx = get_by_path(merged, "stats.packets.sent")

            # Insert to database
            success = insert_companion_metrics(
                ts=int(ts),
                bat_v=float(bat_v) if bat_v is not None else None,
                contacts=int(contacts) if contacts is not None else None,
                uptime=int(uptime) if uptime is not None else None,
                rx=int(rx) if rx is not None else None,
                tx=int(tx) if tx is not None else None,
            )

            if success:
                inserted += 1
            else:
                skipped += 1  # Duplicate timestamp

        except Exception as e:
            log.error(f"Error migrating {json_file}: {e}")
            errors += 1

    if errors > 0:
        log.warn(f"Encountered {errors} errors during companion migration")

    return (inserted, skipped)


def migrate_repeater_snapshots(snapshot_dir: Path) -> tuple[int, int]:
    """Migrate all repeater snapshots to database.

    Args:
        snapshot_dir: Base snapshot directory

    Returns:
        (inserted_count, skipped_count)
    """
    base_dir = snapshot_dir / "repeater"
    if not base_dir.exists():
        log.warn("No repeater snapshots found")
        return (0, 0)

    inserted = 0
    skipped = 0
    errors = 0

    json_files = sorted(base_dir.rglob("*.json"))
    total = len(json_files)
    log.info(f"Found {total} repeater snapshots to migrate")

    for i, json_file in enumerate(json_files):
        if (i + 1) % 100 == 0:
            log.info(f"Progress: {i + 1}/{total} repeater snapshots")

        try:
            data = load_snapshot(json_file)
            if not data:
                skipped += 1
                continue

            if data.get("skip_reason"):
                skipped += 1
                continue

            # Build merged view to get derived fields
            merged = build_repeater_merged_view(data)
            ts = merged.get("ts")
            if not ts:
                skipped += 1
                continue

            # Check for valid status data
            status = merged.get("status") or {}
            if not status:
                skipped += 1
                continue

            # Extract metrics from derived and status
            bat_v = get_by_path(merged, "derived.bat_v")
            rssi = get_by_path(merged, "derived.rssi")
            snr = get_by_path(merged, "derived.snr")
            rx = get_by_path(merged, "derived.rx")
            tx = get_by_path(merged, "derived.tx")

            # Direct from status
            uptime = status.get("uptime")
            noise = status.get("noise_floor")
            txq = status.get("tx_queue_len")
            airtime = status.get("airtime")
            rx_air = status.get("rx_airtime")
            fl_dups = status.get("flood_dups")
            di_dups = status.get("direct_dups")
            fl_tx = status.get("sent_flood")
            fl_rx = status.get("recv_flood")
            di_tx = status.get("sent_direct")
            di_rx = status.get("recv_direct")

            # Insert to database
            success = insert_repeater_metrics(
                ts=int(ts),
                bat_v=float(bat_v) if bat_v is not None else None,
                rssi=int(rssi) if rssi is not None else None,
                snr=float(snr) if snr is not None else None,
                uptime=int(uptime) if uptime is not None else None,
                noise=int(noise) if noise is not None else None,
                txq=int(txq) if txq is not None else None,
                rx=int(rx) if rx is not None else None,
                tx=int(tx) if tx is not None else None,
                airtime=int(airtime) if airtime is not None else None,
                rx_air=int(rx_air) if rx_air is not None else None,
                fl_dups=int(fl_dups) if fl_dups is not None else None,
                di_dups=int(di_dups) if di_dups is not None else None,
                fl_tx=int(fl_tx) if fl_tx is not None else None,
                fl_rx=int(fl_rx) if fl_rx is not None else None,
                di_tx=int(di_tx) if di_tx is not None else None,
                di_rx=int(di_rx) if di_rx is not None else None,
            )

            if success:
                inserted += 1
            else:
                skipped += 1  # Duplicate timestamp

        except Exception as e:
            log.error(f"Error migrating {json_file}: {e}")
            errors += 1

    if errors > 0:
        log.warn(f"Encountered {errors} errors during repeater migration")

    return (inserted, skipped)


def main():
    """Run the migration."""
    cfg = get_config()
    db_path = get_db_path()

    # Startup messages
    log.info("=" * 60)
    log.info("JSON to SQLite Migration")
    log.info("=" * 60)
    log.info("")
    log.info("This is a one-time migration script.")
    log.info("JSON snapshots will NOT be deleted (read-only operation).")
    log.info(f"Database will be created/updated at: {db_path}")
    log.info(f"Reading snapshots from: {cfg.snapshot_dir}")
    log.info("")

    log.info("Initializing database...")
    init_db()

    log.info("Starting migration from JSON snapshots...")

    # Migrate companion
    log.info("Migrating companion snapshots...")
    comp_inserted, comp_skipped = migrate_companion_snapshots(cfg.snapshot_dir)
    log.info(f"Companion: inserted={comp_inserted}, skipped={comp_skipped}")

    # Migrate repeater
    log.info("Migrating repeater snapshots...")
    rep_inserted, rep_skipped = migrate_repeater_snapshots(cfg.snapshot_dir)
    log.info(f"Repeater: inserted={rep_inserted}, skipped={rep_skipped}")

    # Optimize database
    log.info("Optimizing database...")
    from meshmon.db import vacuum_db
    vacuum_db()

    # Print summary
    log.info("=" * 50)
    log.info("Migration complete!")
    log.info(f"Database: {db_path}")
    log.info(f"Size: {db_path.stat().st_size / 1024 / 1024:.2f} MB")
    log.info(f"Companion rows: {comp_inserted}")
    log.info(f"Repeater rows: {rep_inserted}")


if __name__ == "__main__":
    main()
