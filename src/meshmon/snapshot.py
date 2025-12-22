"""Snapshot processing and derived field calculation."""

from typing import Any

from .battery import voltage_to_percentage


def build_companion_merged_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Build a merged view dict for companion snapshots.

    Copies raw payload sections and calculates derived fields
    for metric extraction.

    Args:
        snapshot: Raw companion snapshot dict

    Returns:
        Merged view with derived fields populated
    """
    merged: dict[str, Any] = {}

    # Copy top-level sections
    for key in ["ts", "node", "device_info", "self_info", "bat", "time",
                "self_telemetry", "custom_vars", "contacts", "stats", "derived"]:
        if key in snapshot:
            merged[key] = snapshot[key]

    # Ensure derived exists
    if "derived" not in merged:
        merged["derived"] = {}

    # Add convenience aliases
    if snapshot.get("bat"):
        bat = snapshot["bat"]
        if isinstance(bat, dict):
            merged["bat"] = bat

    # Calculate battery voltage in volts (from millivolts) and percentage
    battery_mv = None
    if merged.get("stats", {}).get("core", {}).get("battery_mv"):
        battery_mv = merged["stats"]["core"]["battery_mv"]
    elif merged.get("bat", {}).get("level"):
        battery_mv = merged["bat"]["level"]

    if battery_mv is not None:
        bat_v = battery_mv / 1000.0
        merged["derived"]["bat_v"] = bat_v
        merged["derived"]["bat_pct"] = voltage_to_percentage(bat_v)

    return merged


def build_repeater_merged_view(snapshot: dict[str, Any]) -> dict[str, Any]:
    """
    Build a merged view dict for repeater snapshots.

    Copies raw payload sections and calculates derived fields
    for metric extraction.

    Args:
        snapshot: Raw repeater snapshot dict

    Returns:
        Merged view with derived fields populated
    """
    merged: dict[str, Any] = {}

    # Copy top-level sections
    for key in ["ts", "node", "status", "telemetry", "acl", "derived",
                "skip_reason", "circuit_breaker"]:
        if key in snapshot:
            merged[key] = snapshot[key]

    # Ensure derived exists
    if "derived" not in merged:
        merged["derived"] = {}

    status = snapshot.get("status") or {}

    # Battery voltage in volts (status.bat is millivolts)
    if status.get("bat"):
        bat_v = status["bat"] / 1000.0
        merged["derived"]["bat_v"] = bat_v
        merged["derived"]["bat_pct"] = voltage_to_percentage(bat_v)

    # RSSI and SNR from status
    if status.get("last_rssi") is not None:
        merged["derived"]["rssi"] = status["last_rssi"]
    if status.get("last_snr") is not None:
        merged["derived"]["snr"] = status["last_snr"]

    # Packet counts from status
    if status.get("nb_recv") is not None:
        merged["derived"]["rx"] = status["nb_recv"]
    if status.get("nb_sent") is not None:
        merged["derived"]["tx"] = status["nb_sent"]

    # Extract voltage from telemetry array if available
    telemetry = snapshot.get("telemetry")
    if isinstance(telemetry, list):
        for item in telemetry:
            if isinstance(item, dict) and item.get("type") == "voltage":
                merged["derived"]["bat_v_telem"] = item.get("value")
                break

    return merged
