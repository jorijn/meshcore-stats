#!/usr/bin/env python3
"""
Phase 1: Collect data from companion node.

Connects to the local companion node via serial and collects:
- Device info
- Battery status
- Time
- Self telemetry
- Custom vars
- Contacts list

Outputs:
- Concise summary to stdout
- Metrics written to SQLite database (EAV schema)
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.meshcore_client import connect_with_lock, run_command
from meshmon.db import init_db, insert_metrics
from meshmon.telemetry import extract_lpp_from_payload, extract_telemetry_metrics


async def collect_companion() -> int:
    """
    Collect data from companion node.

    Returns:
        Exit code (0 = success, 1 = connection failed)
    """
    cfg = get_config()
    ts = int(time.time())

    # Metrics to insert (firmware field names)
    metrics: dict[str, float] = {}
    commands_succeeded = 0

    log.debug("Connecting to companion node...")
    async with connect_with_lock() as mc:
        if mc is None:
            log.error("Failed to connect to companion node")
            return 1

        # Commands are accessed via mc.commands
        cmd = mc.commands

        try:
            # send_appstart (already called during connect, but call again to get self_info)
            ok, evt_type, payload, err = await run_command(
                mc, cmd.send_appstart(), "send_appstart"
            )
            if ok:
                commands_succeeded += 1
                log.debug(f"appstart: {evt_type}")
            else:
                log.error(f"appstart failed: {err}")

            # send_device_query
            ok, evt_type, payload, err = await run_command(
                mc, cmd.send_device_query(), "send_device_query"
            )
            if ok:
                commands_succeeded += 1
                log.debug(f"device_query: {payload}")
            else:
                log.error(f"device_query failed: {err}")

            # get_bat
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_bat(), "get_bat"
            )
            if ok:
                commands_succeeded += 1
                log.debug(f"get_bat: {payload}")
            else:
                log.error(f"get_bat failed: {err}")

            # get_time
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_time(), "get_time"
            )
            if ok:
                commands_succeeded += 1
                log.debug(f"get_time: {payload}")
            else:
                log.error(f"get_time failed: {err}")

            # get_self_telemetry - collect environmental sensor data
            # Note: The call happens regardless of telemetry_enabled for device query completeness,
            # but we only extract and store metrics if the feature is enabled.
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_self_telemetry(), "get_self_telemetry"
            )
            if ok:
                commands_succeeded += 1
                log.debug(f"get_self_telemetry: {payload}")
                # Extract and store telemetry if enabled
                if cfg.telemetry_enabled:
                    lpp_data = extract_lpp_from_payload(payload)
                    if lpp_data is not None:
                        telemetry_metrics = extract_telemetry_metrics(lpp_data)
                        if telemetry_metrics:
                            metrics.update(telemetry_metrics)
                            log.debug(f"Extracted {len(telemetry_metrics)} telemetry metrics")
            else:
                # Debug level because not all devices have sensors attached - this is expected
                log.debug(f"get_self_telemetry failed: {err}")

            # get_custom_vars
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_custom_vars(), "get_custom_vars"
            )
            if ok:
                commands_succeeded += 1
                log.debug(f"get_custom_vars: {payload}")
            else:
                log.debug(f"get_custom_vars failed: {err}")

            # get_contacts - count contacts
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_contacts(), "get_contacts"
            )
            if ok:
                commands_succeeded += 1
                contacts_count = len(payload) if payload else 0
                metrics["contacts"] = float(contacts_count)
                log.debug(f"get_contacts: found {contacts_count} contacts")
            else:
                log.error(f"get_contacts failed: {err}")

            # Get statistics - these contain the main metrics
            # Core stats (battery_mv, uptime_secs, errors, queue_len)
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_stats_core(), "get_stats_core"
            )
            if ok and payload and isinstance(payload, dict):
                commands_succeeded += 1
                # Insert all numeric fields from stats_core
                for key, value in payload.items():
                    if isinstance(value, (int, float)):
                        metrics[key] = float(value)
                log.debug(f"stats_core: {payload}")

            # Radio stats (noise_floor, last_rssi, last_snr, tx_air_secs, rx_air_secs)
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_stats_radio(), "get_stats_radio"
            )
            if ok and payload and isinstance(payload, dict):
                commands_succeeded += 1
                for key, value in payload.items():
                    if isinstance(value, (int, float)):
                        metrics[key] = float(value)
                log.debug(f"stats_radio: {payload}")

            # Packet stats (recv, sent, flood_tx, direct_tx, flood_rx, direct_rx)
            ok, evt_type, payload, err = await run_command(
                mc, cmd.get_stats_packets(), "get_stats_packets"
            )
            if ok and payload and isinstance(payload, dict):
                commands_succeeded += 1
                for key, value in payload.items():
                    if isinstance(value, (int, float)):
                        metrics[key] = float(value)
                log.debug(f"stats_packets: {payload}")

        except Exception as e:
            log.error(f"Error during collection: {e}")

    # Connection closed and lock released by context manager

    # Print summary
    summary_parts = [f"ts={ts}"]
    if "battery_mv" in metrics:
        bat_v = metrics["battery_mv"] / 1000.0
        summary_parts.append(f"bat={bat_v:.2f}V")
    if "contacts" in metrics:
        summary_parts.append(f"contacts={int(metrics['contacts'])}")
    if "recv" in metrics:
        summary_parts.append(f"rx={int(metrics['recv'])}")
    if "sent" in metrics:
        summary_parts.append(f"tx={int(metrics['sent'])}")
    # Add telemetry count to summary if present
    telemetry_count = sum(1 for k in metrics if k.startswith("telemetry."))
    if telemetry_count > 0:
        summary_parts.append(f"telem={telemetry_count}")

    log.info(f"Companion: {', '.join(summary_parts)}")

    # Write metrics to database
    if commands_succeeded > 0 and metrics:
        try:
            inserted = insert_metrics(ts=ts, role="companion", metrics=metrics)
            log.debug(f"Inserted {inserted} metrics to database (ts={ts})")
        except Exception as e:
            log.error(f"Failed to write metrics to database: {e}")
            return 1
        return 0
    else:
        log.error("No commands succeeded or no metrics collected")
        return 1


def main():
    """Entry point."""
    # Ensure database is initialized
    init_db()

    exit_code = asyncio.run(collect_companion())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
