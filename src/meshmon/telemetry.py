"""Telemetry data extraction from Cayenne LPP format."""

from typing import Any
from . import log

__all__ = ["extract_lpp_from_payload", "extract_telemetry_metrics"]


def extract_lpp_from_payload(payload: Any) -> list | None:
    """Extract LPP data list from telemetry payload.

    Handles both formats returned by the MeshCore API:
    - Dict format: {'pubkey_pre': '...', 'lpp': [...]}
    - Direct list format: [...]

    Args:
        payload: Raw telemetry payload from get_self_telemetry() or req_telemetry_sync()

    Returns:
        The LPP data list, or None if not extractable.
    """
    if payload is None:
        return None

    if isinstance(payload, dict):
        lpp = payload.get("lpp")
        if lpp is None:
            log.debug("No 'lpp' key in telemetry payload dict")
            return None
        if not isinstance(lpp, list):
            log.debug(f"Unexpected LPP data type in payload: {type(lpp).__name__}")
            return None
        return lpp

    if isinstance(payload, list):
        return payload

    log.debug(f"Unexpected telemetry payload type: {type(payload).__name__}")
    return None


def extract_telemetry_metrics(lpp_data: Any) -> dict[str, float]:
    """Extract numeric telemetry values from Cayenne LPP response.

    Expected format:
    [
        {"type": "temperature", "channel": 0, "value": 23.5},
        {"type": "gps", "channel": 1, "value": {"latitude": 51.5, "longitude": -0.1, "altitude": 10}}
    ]

    Keys are formatted as:
    - telemetry.{type}.{channel} for scalar values
    - telemetry.{type}.{channel}.{subkey} for compound values (e.g., GPS)

    Returns:
        Dict mapping metric keys to float values. Invalid readings are skipped.
    """
    if not isinstance(lpp_data, list):
        log.warn(f"Expected list for LPP data, got {type(lpp_data).__name__}")
        return {}

    metrics: dict[str, float] = {}

    for i, reading in enumerate(lpp_data):
        if not isinstance(reading, dict):
            log.debug(f"Skipping non-dict LPP reading at index {i}")
            continue

        sensor_type = reading.get("type")
        if not isinstance(sensor_type, str) or not sensor_type.strip():
            log.debug(f"Skipping reading with invalid type at index {i}")
            continue

        # Normalize sensor type for use as metric key component
        sensor_type = sensor_type.strip().lower().replace(" ", "_")

        channel = reading.get("channel", 0)
        if not isinstance(channel, int):
            channel = 0

        value = reading.get("value")
        base_key = f"telemetry.{sensor_type}.{channel}"

        # Note: Check bool before int because bool is a subclass of int in Python.
        # Some sensors may report digital on/off values as booleans.
        if isinstance(value, bool):
            metrics[base_key] = float(value)
        elif isinstance(value, (int, float)):
            metrics[base_key] = float(value)
        elif isinstance(value, dict):
            for subkey, subval in value.items():
                if not isinstance(subkey, str):
                    continue
                subkey_clean = subkey.strip().lower().replace(" ", "_")
                if not subkey_clean:
                    continue
                if isinstance(subval, bool):
                    metrics[f"{base_key}.{subkey_clean}"] = float(subval)
                elif isinstance(subval, (int, float)):
                    metrics[f"{base_key}.{subkey_clean}"] = float(subval)

    return metrics
