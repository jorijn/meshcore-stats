#!/usr/bin/env python3
"""
Phase 1: Collect data from remote repeater node.

Connects to the local companion node, finds the repeater contact,
and queries it over LoRa using binary protocol.

Features:
- Circuit breaker to avoid spamming LoRa
- Retry with backoff
- Timeout handling

Outputs:
- Concise summary to stdout
- Metrics written to SQLite database (EAV schema)
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Callable, Coroutine, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.meshcore_client import (
    connect_with_lock,
    run_command,
    get_contact_by_name,
    get_contact_by_key_prefix,
    extract_contact_info,
)
from meshmon.db import init_db, insert_metrics
from meshmon.retry import get_repeater_circuit_breaker, with_retries
from meshmon.telemetry import extract_lpp_from_payload, extract_telemetry_metrics


async def find_repeater_contact(mc: Any) -> Optional[Any]:
    """
    Find the repeater contact by name or key prefix.

    Returns:
        Contact dict or None
    """
    cfg = get_config()

    # Get all contacts first (this populates mc.contacts)
    ok, evt_type, payload, err = await run_command(
        mc, mc.commands.get_contacts(), "get_contacts"
    )
    if not ok:
        log.error(f"Failed to get contacts: {err}")
        return None

    # payload is a dict keyed by public key, mc.contacts is also populated
    # The get_contact_by_name method searches mc._contacts
    contacts_dict = mc.contacts if hasattr(mc, "contacts") else {}
    if isinstance(payload, dict):
        contacts_dict = payload

    # Try by name first using the helper (searches mc._contacts)
    if cfg.repeater_name:
        log.debug(f"Looking for repeater by name: {cfg.repeater_name}")
        contact = get_contact_by_name(mc, cfg.repeater_name)
        if contact:
            return contact

        # Manual search in payload dict
        for pk, c in contacts_dict.items():
            if isinstance(c, dict):
                name = c.get("adv_name", "")
                if name and name.lower() == cfg.repeater_name.lower():
                    return c

    # Try by key prefix
    if cfg.repeater_key_prefix:
        log.debug(f"Looking for repeater by key prefix: {cfg.repeater_key_prefix}")
        contact = get_contact_by_key_prefix(mc, cfg.repeater_key_prefix)
        if contact:
            return contact

        # Manual search
        prefix = cfg.repeater_key_prefix.lower()
        for pk, c in contacts_dict.items():
            if pk.lower().startswith(prefix):
                return c

    # Not found - print available contacts
    log.error("Repeater contact not found")
    log.info("Available contacts:")
    for pk, c in contacts_dict.items():
        if isinstance(c, dict):
            name = c.get("adv_name", c.get("name", "unnamed"))
            key = pk[:12] if pk else ""
            log.info(f"  - {name} (key: {key}...)")

    return None


async def query_repeater_with_retry(
    mc: Any,
    contact: Any,
    command_name: str,
    command_coro_fn: Callable[[], Coroutine[Any, Any, Any]],
) -> tuple[bool, Optional[dict], Optional[str]]:
    """
    Query repeater with retry logic.

    The binary req_*_sync methods return the payload directly (or None on failure),
    not an Event object.

    Args:
        mc: MeshCore instance
        contact: Contact object
        command_name: Name for logging
        command_coro_fn: Function that returns command coroutine

    Returns:
        (success, payload, error_message)
    """
    cfg = get_config()

    async def do_query():
        result = await command_coro_fn()
        if result is None:
            raise Exception("No response received")
        return result

    success, result, exc = await with_retries(
        do_query,
        attempts=cfg.remote_retry_attempts,
        backoff_s=cfg.remote_retry_backoff_s,
        name=command_name,
    )

    if success:
        return (True, result, None)
    else:
        return (False, None, str(exc) if exc else "Failed")


async def collect_repeater() -> int:
    """Collect data from remote repeater node.

    Collects status metrics (battery, uptime, packet counters, etc.) and
    optionally telemetry data (temperature, humidity, pressure) if enabled.

    Returns:
        Exit code (0 = success, 1 = error)
    """
    cfg = get_config()
    ts = int(time.time())

    # Check circuit breaker first
    cb = get_repeater_circuit_breaker()

    if cb.is_open():
        remaining = cb.cooldown_remaining()
        log.warn(f"Circuit breaker open, cooldown active ({remaining}s remaining)")
        # Skip collection - no metrics to write
        return 0

    # Metrics to insert (firmware field names from req_status_sync)
    status_metrics: dict[str, float] = {}
    telemetry_metrics: dict[str, float] = {}
    node_name = "unknown"
    status_ok = False

    # Connect to companion
    log.debug("Connecting to companion node...")
    async with connect_with_lock() as mc:
        if mc is None:
            log.error("Failed to connect to companion node")
            return 1

        # Commands are accessed via mc.commands
        cmd = mc.commands

        try:
            # Initialize (appstart already called during connect)
            ok, evt_type, payload, err = await run_command(
                mc, cmd.send_appstart(), "send_appstart"
            )
            if not ok:
                log.error(f"appstart failed: {err}")

            # Find repeater contact
            contact = await find_repeater_contact(mc)

            if contact is None:
                log.error("Cannot find repeater contact")
                return 1

            # Store contact info
            contact_info = extract_contact_info(contact)
            node_name = contact_info.get("adv_name", "unknown")

            log.debug(f"Found repeater: {node_name}")

            # Optional login (if command exists)
            if cfg.repeater_password and hasattr(cmd, "send_login"):
                log.debug("Attempting login...")
                try:
                    ok, evt_type, payload, err = await run_command(
                        mc,
                        cmd.send_login(contact, cfg.repeater_password),
                        "send_login",
                    )
                    if ok:
                        log.debug("Login successful")
                    else:
                        log.debug(f"Login failed or not supported: {err}")
                except Exception as e:
                    log.debug(f"Login not supported: {e}")

            # Phase 1: Status collection (affects circuit breaker)
            # Use timeout=0 to let the device suggest timeout, with min_timeout as floor
            log.debug("Querying repeater status...")
            success, payload, err = await query_repeater_with_retry(
                mc,
                contact,
                "req_status_sync",
                lambda: cmd.req_status_sync(contact, timeout=0, min_timeout=cfg.remote_timeout_s),
            )
            if success and payload and isinstance(payload, dict):
                status_ok = True
                # Insert all numeric fields from status response
                for key, value in payload.items():
                    if isinstance(value, (int, float)):
                        status_metrics[key] = float(value)
                log.debug(f"req_status_sync: {payload}")
            else:
                log.warn(f"req_status_sync failed: {err}")

            # Update circuit breaker based on status result
            if status_ok:
                cb.record_success()
                log.debug("Circuit breaker: recorded success")
            else:
                cb.record_failure(cfg.remote_cb_fails, cfg.remote_cb_cooldown_s)
                log.debug(f"Circuit breaker: recorded failure ({cb.consecutive_failures}/{cfg.remote_cb_fails})")

            # CRITICAL: Store status metrics immediately before attempting telemetry
            # This ensures critical data is saved even if telemetry fails
            if status_ok and status_metrics:
                try:
                    inserted = insert_metrics(ts=ts, role="repeater", metrics=status_metrics)
                    log.debug(f"Stored {inserted} status metrics (ts={ts})")
                except Exception as e:
                    log.error(f"Failed to store status metrics: {e}")
                    return 1

            # Phase 2: Telemetry collection (does NOT affect circuit breaker)
            if cfg.telemetry_enabled and status_ok:
                log.debug("Querying repeater telemetry...")
                try:
                    # Note: Telemetry uses its own retry settings and does NOT
                    # affect circuit breaker. Status success proves the link is up;
                    # telemetry failures are likely firmware/capability issues.
                    telem_success, telem_payload, telem_err = await with_retries(
                        lambda: cmd.req_telemetry_sync(
                            contact, timeout=0, min_timeout=cfg.telemetry_timeout_s
                        ),
                        attempts=cfg.telemetry_retry_attempts,
                        backoff_s=cfg.telemetry_retry_backoff_s,
                        name="req_telemetry_sync",
                    )

                    if telem_success and telem_payload:
                        log.debug(f"req_telemetry_sync: {telem_payload}")
                        lpp_data = extract_lpp_from_payload(telem_payload)
                        if lpp_data is not None:
                            telemetry_metrics = extract_telemetry_metrics(lpp_data)
                            log.debug(f"Extracted {len(telemetry_metrics)} telemetry metrics")

                        # Store telemetry metrics
                        if telemetry_metrics:
                            try:
                                inserted = insert_metrics(ts=ts, role="repeater", metrics=telemetry_metrics)
                                log.debug(f"Stored {inserted} telemetry metrics")
                            except Exception as e:
                                log.warn(f"Failed to store telemetry metrics: {e}")
                    else:
                        log.warn(f"req_telemetry_sync failed: {telem_err}")
                except Exception as e:
                    log.warn(f"Telemetry collection error (continuing): {e}")

        except Exception as e:
            log.error(f"Error during collection: {e}")
            cb.record_failure(cfg.remote_cb_fails, cfg.remote_cb_cooldown_s)

    # Connection closed and lock released by context manager

    # Print summary
    summary_parts = [f"ts={ts}"]
    if "bat" in status_metrics:
        bat_v = status_metrics["bat"] / 1000.0
        summary_parts.append(f"bat={bat_v:.2f}V")
    if "uptime" in status_metrics:
        uptime_days = status_metrics["uptime"] // 86400
        summary_parts.append(f"uptime={int(uptime_days)}d")
    if "nb_recv" in status_metrics:
        summary_parts.append(f"rx={int(status_metrics['nb_recv'])}")
    if "nb_sent" in status_metrics:
        summary_parts.append(f"tx={int(status_metrics['nb_sent'])}")
    if telemetry_metrics:
        summary_parts.append(f"telem={len(telemetry_metrics)}")

    log.info(f"Repeater ({node_name}): {', '.join(summary_parts)}")

    return 0 if status_ok else 1


def main():
    """Entry point."""
    # Ensure database is initialized
    init_db()

    exit_code = asyncio.run(collect_repeater())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
