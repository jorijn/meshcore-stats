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
- Full JSON snapshot to disk
"""

import asyncio
import sys
import time
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.meshcore_client import connect_from_env, run_command
from meshmon.jsondump import write_snapshot


async def collect_companion() -> int:
    """
    Collect data from companion node.

    Returns:
        Exit code (0 = success, 1 = connection failed)
    """
    cfg = get_config()
    ts = int(time.time())

    log.debug("Connecting to companion node...")
    mc = await connect_from_env()

    if mc is None:
        log.error("Failed to connect to companion node")
        return 1

    # Initialize snapshot
    snapshot = {
        "ts": ts,
        "node": {"role": "companion"},
        "device_info": None,
        "self_info": None,
        "bat": None,
        "time": None,
        "self_telemetry": None,
        "custom_vars": None,
        "contacts": None,
        "stats": None,
        "derived": {},
    }

    commands_succeeded = 0

    # Commands are accessed via mc.commands
    cmd = mc.commands

    try:
        # send_appstart (already called during connect, but call again to get self_info)
        ok, evt_type, payload, err = await run_command(
            mc, cmd.send_appstart(), "send_appstart"
        )
        if ok:
            commands_succeeded += 1
            snapshot["self_info"] = payload
            log.debug(f"appstart: {evt_type}")
        else:
            log.error(f"appstart failed: {err}")

        # send_device_query
        ok, evt_type, payload, err = await run_command(
            mc, cmd.send_device_query(), "send_device_query"
        )
        if ok:
            commands_succeeded += 1
            snapshot["device_info"] = payload
            log.debug(f"device_query: {payload}")
        else:
            log.error(f"device_query failed: {err}")

        # get_bat
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_bat(), "get_bat"
        )
        if ok:
            commands_succeeded += 1
            snapshot["bat"] = payload
            log.debug(f"get_bat: {payload}")
        else:
            log.error(f"get_bat failed: {err}")

        # get_time
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_time(), "get_time"
        )
        if ok:
            commands_succeeded += 1
            snapshot["time"] = payload
            log.debug(f"get_time: {payload}")
        else:
            log.error(f"get_time failed: {err}")

        # get_self_telemetry
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_self_telemetry(), "get_self_telemetry"
        )
        if ok:
            commands_succeeded += 1
            snapshot["self_telemetry"] = payload
            log.debug(f"get_self_telemetry: {payload}")
        else:
            log.error(f"get_self_telemetry failed: {err}")

        # get_custom_vars
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_custom_vars(), "get_custom_vars"
        )
        if ok:
            commands_succeeded += 1
            snapshot["custom_vars"] = payload
            log.debug(f"get_custom_vars: {payload}")
        else:
            log.debug(f"get_custom_vars failed: {err}")

        # get_contacts
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_contacts(), "get_contacts"
        )
        if ok:
            commands_succeeded += 1
            # Contacts payload is a dict keyed by public key
            contacts_names = []
            if payload and isinstance(payload, dict):
                for pk, c in payload.items():
                    if isinstance(c, dict) and c.get("adv_name"):
                        contacts_names.append(c["adv_name"])

            snapshot["contacts"] = {"list": payload if payload else {}}
            snapshot["derived"]["contacts_count"] = len(payload) if payload else 0
            snapshot["derived"]["contacts_names"] = contacts_names
            log.debug(f"get_contacts: found {snapshot['derived']['contacts_count']} contacts")
        else:
            log.error(f"get_contacts failed: {err}")
            snapshot["derived"]["contacts_count"] = 0

        # Get statistics
        stats = {}

        # Core stats
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_stats_core(), "get_stats_core"
        )
        if ok and payload:
            stats["core"] = payload
            commands_succeeded += 1

        # Radio stats
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_stats_radio(), "get_stats_radio"
        )
        if ok and payload:
            stats["radio"] = payload
            commands_succeeded += 1

        # Packet stats
        ok, evt_type, payload, err = await run_command(
            mc, cmd.get_stats_packets(), "get_stats_packets"
        )
        if ok and payload:
            stats["packets"] = payload
            commands_succeeded += 1
            # Extract rx/tx for convenience (actual field names are recv/sent)
            if isinstance(payload, dict):
                if "recv" in payload:
                    snapshot["derived"]["rx_packets"] = payload["recv"]
                if "sent" in payload:
                    snapshot["derived"]["tx_packets"] = payload["sent"]

        if stats:
            snapshot["stats"] = stats

    except Exception as e:
        log.error(f"Error during collection: {e}")

    finally:
        # Close connection
        if hasattr(mc, "disconnect"):
            try:
                await mc.disconnect()
            except Exception:
                pass

    # Print summary
    bat_mv = None
    if snapshot.get("stats") and snapshot["stats"].get("core"):
        bat_mv = snapshot["stats"]["core"].get("battery_mv")
    contacts_count = snapshot["derived"].get("contacts_count", 0)
    rx = snapshot["derived"].get("rx_packets")
    tx = snapshot["derived"].get("tx_packets")

    summary_parts = [f"ts={ts}"]
    if bat_mv is not None:
        summary_parts.append(f"bat={bat_mv/1000:.2f}V")
    summary_parts.append(f"contacts={contacts_count}")
    if rx is not None:
        summary_parts.append(f"rx={rx}")
    if tx is not None:
        summary_parts.append(f"tx={tx}")

    log.info(f"Companion: {', '.join(summary_parts)}")

    # Write snapshot
    if commands_succeeded > 0:
        path = write_snapshot("companion", ts, snapshot)
        log.info(f"Snapshot written to {path}")
        return 0
    else:
        log.error("No commands succeeded")
        return 1


def main():
    """Entry point."""
    exit_code = asyncio.run(collect_companion())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
