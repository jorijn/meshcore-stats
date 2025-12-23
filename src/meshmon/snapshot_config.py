"""Declarative configuration for snapshot table field extraction."""

from typing import Any, Callable, Optional, NamedTuple

from .extract import get_by_path
from .formatters import (
    format_time,
    format_value,
    format_number,
    format_duration,
    format_uptime,
    format_voltage_with_pct,
)


class SnapshotField(NamedTuple):
    """Configuration for a single snapshot table field.

    Attributes:
        label: Display label for the field
        path: Dotted path to extract from snapshot (None = computed)
        tooltip: Help text for tooltip
        formatter: Function to format the extracted value
        condition: Function to check if field should be displayed (optional)
        computer: Function to compute value from snapshot (for derived fields)
    """
    label: str
    path: Optional[str]
    tooltip: str
    formatter: Callable[[Any], str]
    condition: Optional[Callable[[dict], bool]] = None
    computer: Optional[Callable[[dict], Any]] = None


# Field configurations by role

COMPANION_FIELDS = [
    SnapshotField(
        label="Timestamp",
        path="ts",
        tooltip="When this snapshot was captured",
        formatter=format_time,
    ),
    SnapshotField(
        label="Battery Voltage",
        path="stats.core.battery_mv",
        tooltip="Current battery voltage (4.2V = full, 3.0V = empty)",
        formatter=format_voltage_with_pct,
    ),
    SnapshotField(
        label="Contacts",
        path="derived.contacts_count",
        tooltip="Number of known nodes in the mesh network",
        formatter=str,
    ),
    SnapshotField(
        label="RX Packets",
        path="stats.packets.recv",
        tooltip="Total packets received since last reboot",
        formatter=format_number,
    ),
    SnapshotField(
        label="TX Packets",
        path="stats.packets.sent",
        tooltip="Total packets transmitted since last reboot",
        formatter=format_number,
    ),
    SnapshotField(
        label="Frequency",
        path="self_info.radio_freq",
        tooltip="LoRa radio frequency",
        formatter=lambda v: f"{format_value(v)} MHz",
    ),
    SnapshotField(
        label="Spreading Factor",
        path="self_info.radio_sf",
        tooltip="LoRa spreading factor (higher = longer range, slower speed)",
        formatter=str,
    ),
    SnapshotField(
        label="Bandwidth",
        path="self_info.radio_bw",
        tooltip="LoRa channel bandwidth",
        formatter=lambda v: f"{format_value(v)} kHz",
    ),
    SnapshotField(
        label="TX Power",
        path="self_info.tx_power",
        tooltip="Transmit power in decibels relative to 1 milliwatt",
        formatter=lambda v: f"{v} dBm",
    ),
    SnapshotField(
        label="Uptime",
        path="stats.core.uptime_secs",
        tooltip="Time since last device reboot",
        formatter=format_uptime,
    ),
]

REPEATER_FIELDS = [
    SnapshotField(
        label="Timestamp",
        path="ts",
        tooltip="When this snapshot was captured",
        formatter=format_time,
    ),
    SnapshotField(
        label="Battery Voltage",
        path="status.bat",
        tooltip="Current battery voltage (4.2V = full, 3.0V = empty)",
        formatter=format_voltage_with_pct,
    ),
    SnapshotField(
        label="Battery (telemetry)",
        path=None,  # Computed from telemetry array
        tooltip="Battery voltage from telemetry channel",
        formatter=lambda v: f"{format_value(v)} V",
        computer=lambda snapshot: next(
            (item.get("value") for item in snapshot.get("telemetry", [])
             if isinstance(item, dict) and item.get("type") == "voltage"),
            None
        ),
    ),
    SnapshotField(
        label="Neighbours",
        path="derived.neighbours_count",
        tooltip="Number of directly reachable mesh nodes",
        formatter=str,
    ),
    SnapshotField(
        label="RSSI",
        path="status.last_rssi",
        tooltip="Received Signal Strength Indicator of last packet (closer to 0 = stronger)",
        formatter=lambda v: f"{v} dBm",
    ),
    SnapshotField(
        label="SNR",
        path="status.last_snr",
        tooltip="Signal-to-Noise Ratio of last packet (higher = cleaner signal)",
        formatter=lambda v: f"{format_value(v)} dB",
    ),
    SnapshotField(
        label="Noise Floor",
        path="status.noise_floor",
        tooltip="Background radio noise level (lower = quieter environment)",
        formatter=lambda v: f"{v} dBm",
    ),
    SnapshotField(
        label="RX Packets",
        path="status.nb_recv",
        tooltip="Total packets received since last reboot",
        formatter=format_number,
    ),
    SnapshotField(
        label="TX Packets",
        path="status.nb_sent",
        tooltip="Total packets transmitted since last reboot",
        formatter=format_number,
    ),
    SnapshotField(
        label="Uptime",
        path="status.uptime",
        tooltip="Time since last device reboot",
        formatter=format_uptime,
    ),
    SnapshotField(
        label="TX Airtime",
        path="status.airtime",
        tooltip="Total time spent transmitting (legal limit: 10% duty cycle)",
        formatter=format_duration,
    ),
    SnapshotField(
        label="Status",
        path="skip_reason",
        tooltip="Data collection was skipped for this snapshot",
        formatter=lambda v: f"Skipped: {v}",
        condition=lambda snapshot: snapshot.get("skip_reason") is not None,
    ),
]


def extract_snapshot_table(snapshot: dict, role: str) -> list[tuple[str, str, str]]:
    """
    Extract key-value pairs from snapshot for display.

    Args:
        snapshot: Snapshot dictionary
        role: "companion" or "repeater"

    Returns:
        List of (label, formatted_value, tooltip) tuples
    """
    fields = COMPANION_FIELDS if role == "companion" else REPEATER_FIELDS
    table = []

    for field in fields:
        # Check condition if specified
        if field.condition and not field.condition(snapshot):
            continue

        # Extract or compute value
        if field.computer:
            value = field.computer(snapshot)
        else:
            value = get_by_path(snapshot, field.path) if field.path else None

        # Skip if no value
        if value is None:
            continue

        # Format and append
        formatted = field.formatter(value)
        table.append((field.label, formatted, field.tooltip))

    return table
