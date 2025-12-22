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
- Full JSON snapshot to disk
"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.env import get_config
from meshmon import log
from meshmon.meshcore_client import (
    connect_from_env,
    run_command,
    get_contact_by_name,
    get_contact_by_key_prefix,
    extract_contact_info,
    list_contacts_summary,
)
from meshmon.jsondump import write_snapshot
from meshmon.retry import get_repeater_circuit_breaker, with_retries


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
    command_coro_fn,
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
    """
    Collect data from remote repeater node.

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

        # Write a skip snapshot
        snapshot = {
            "ts": ts,
            "node": {"role": "repeater", "name": cfg.repeater_name},
            "skip_reason": f"Circuit breaker cooldown ({remaining}s remaining)",
            "circuit_breaker": cb.to_dict(),
            "status": None,
            "telemetry": None,
            "derived": {},
        }
        write_snapshot("repeater", ts, snapshot)
        return 0

    # Connect to companion
    log.debug("Connecting to companion node...")
    mc = await connect_from_env()

    if mc is None:
        log.error("Failed to connect to companion node")
        return 1

    # Initialize snapshot
    snapshot = {
        "ts": ts,
        "node": {"role": "repeater"},
        "status": None,
        "telemetry": None,
        "acl": None,
        "derived": {},
    }

    any_success = False

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
        snapshot["node"]["name"] = contact_info.get("adv_name", "unknown")
        snapshot["node"]["pubkey_prefix"] = contact_info.get("pubkey_prefix", "")[:12]

        log.debug(f"Found repeater: {snapshot['node']['name']}")

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

        # Query status (using _sync version which returns payload directly)
        # Use timeout=0 to let the device suggest timeout, with min_timeout as floor
        log.debug("Querying repeater status...")
        success, payload, err = await query_repeater_with_retry(
            mc,
            contact,
            "req_status_sync",
            lambda: cmd.req_status_sync(contact, timeout=0, min_timeout=cfg.remote_timeout_s),
        )
        if success:
            any_success = True
            snapshot["status"] = payload
            log.debug(f"req_status_sync: {payload}")
        else:
            log.warn(f"req_status_sync failed: {err} (repeater may be unreachable or not support binary requests)")

        # Query telemetry (using _sync version which returns payload directly)
        log.debug("Querying repeater telemetry...")
        success, payload, err = await query_repeater_with_retry(
            mc,
            contact,
            "req_telemetry_sync",
            lambda: cmd.req_telemetry_sync(contact, timeout=0, min_timeout=cfg.remote_timeout_s),
        )
        if success:
            any_success = True
            snapshot["telemetry"] = payload
            log.debug(f"req_telemetry_sync: {payload}")
        else:
            log.warn(f"req_telemetry_sync failed: {err} (repeater may be unreachable or not support binary requests)")

        # Optional ACL query (using _sync version)
        if cfg.repeater_fetch_acl:
            log.debug("Querying repeater ACL...")
            success, payload, err = await query_repeater_with_retry(
                mc,
                contact,
                "req_acl_sync",
                lambda: cmd.req_acl_sync(contact, timeout=0, min_timeout=cfg.remote_timeout_s),
            )
            if success:
                snapshot["acl"] = payload
                log.debug(f"req_acl_sync: {payload}")
            else:
                log.debug(f"req_acl_sync failed: {err}")

        # Derive values
        if snapshot["telemetry"]:
            tel = snapshot["telemetry"]
            # Try to extract neighbour count
            if isinstance(tel, dict):
                if "neighbours" in tel:
                    neigh = tel["neighbours"]
                    if isinstance(neigh, list):
                        snapshot["derived"]["neighbours_count"] = len(neigh)
                    elif isinstance(neigh, int):
                        snapshot["derived"]["neighbours_count"] = neigh

        # Update circuit breaker
        if any_success:
            cb.record_success()
            log.debug("Circuit breaker: recorded success")
        else:
            cb.record_failure(cfg.remote_cb_fails, cfg.remote_cb_cooldown_s)
            log.debug(f"Circuit breaker: recorded failure ({cb.consecutive_failures}/{cfg.remote_cb_fails})")

    except Exception as e:
        log.error(f"Error during collection: {e}")
        cb.record_failure(cfg.remote_cb_fails, cfg.remote_cb_cooldown_s)

    finally:
        # Close connection
        if hasattr(mc, "disconnect"):
            try:
                await mc.disconnect()
            except Exception:
                pass

    # Print summary
    summary_parts = [f"ts={ts}"]

    if snapshot["telemetry"]:
        tel = snapshot["telemetry"]
        if isinstance(tel, dict):
            bat = tel.get("bat") or tel.get("battery_v")
            if bat is not None:
                summary_parts.append(f"bat={bat}V")

            bat_pct = tel.get("bat_pct") or tel.get("battery_pct")
            if bat_pct is not None:
                summary_parts.append(f"bat_pct={bat_pct}%")

    neigh = snapshot["derived"].get("neighbours_count")
    if neigh is not None:
        summary_parts.append(f"neighbours={neigh}")

    if snapshot["status"]:
        status = snapshot["status"]
        if isinstance(status, dict):
            rx = status.get("rx_packets")
            tx = status.get("tx_packets")
            if rx is not None:
                summary_parts.append(f"rx={rx}")
            if tx is not None:
                summary_parts.append(f"tx={tx}")

    log.info(f"Repeater ({snapshot['node'].get('name', 'unknown')}): {', '.join(summary_parts)}")

    # Write snapshot
    path = write_snapshot("repeater", ts, snapshot)
    log.info(f"Snapshot written to {path}")

    return 0 if any_success else 1


def main():
    """Entry point."""
    exit_code = asyncio.run(collect_repeater())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
