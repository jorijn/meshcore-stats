"""Centralized metrics configuration.

This module defines metric display properties using firmware field names.
It is the single source of truth for:
- Metric type (gauge vs counter)
- Display labels and units
- Scaling factors for charts
- Which metrics to display per role

Firmware field names are used directly (e.g., 'bat', 'nb_recv', 'battery_mv').
See docs/firmware-responses.md for the complete field reference.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class MetricConfig:
    """Configuration for displaying a metric.

    Attributes:
        label: Human-readable label for charts/reports
        unit: Display unit (e.g., 'V', 'dBm', '/min')
        type: 'gauge' for instantaneous values, 'counter' for cumulative values
        scale: Multiply raw value by this for display (e.g., 60 for per-minute)
        transform: Optional transform to apply ('mv_to_v' for millivolts to volts)
    """
    label: str
    unit: str
    type: str = "gauge"
    scale: float = 1.0
    transform: Optional[str] = None


# =============================================================================
# Metric Definitions (firmware field names)
# =============================================================================

METRIC_CONFIG: dict[str, MetricConfig] = {
    # -------------------------------------------------------------------------
    # Companion metrics (from get_stats_core, get_stats_packets, get_contacts)
    # -------------------------------------------------------------------------
    "battery_mv": MetricConfig(
        label="Battery Voltage",
        unit="V",
        transform="mv_to_v",
    ),
    "uptime_secs": MetricConfig(
        label="System Uptime",
        unit="days",
        scale=1 / 86400,
    ),
    "contacts": MetricConfig(
        label="Known Contacts",
        unit="",
    ),
    "recv": MetricConfig(
        label="Total Packets Received",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "sent": MetricConfig(
        label="Total Packets Sent",
        unit="/min",
        type="counter",
        scale=60,
    ),

    # -------------------------------------------------------------------------
    # Repeater metrics (from req_status_sync)
    # -------------------------------------------------------------------------
    "bat": MetricConfig(
        label="Battery Voltage",
        unit="V",
        transform="mv_to_v",
    ),
    "uptime": MetricConfig(
        label="System Uptime",
        unit="days",
        scale=1 / 86400,
    ),
    "last_rssi": MetricConfig(
        label="Signal Strength (RSSI)",
        unit="dBm",
    ),
    "last_snr": MetricConfig(
        label="Signal-to-Noise Ratio",
        unit="dB",
    ),
    "noise_floor": MetricConfig(
        label="RF Noise Floor",
        unit="dBm",
    ),
    "tx_queue_len": MetricConfig(
        label="Transmit Queue Depth",
        unit="",
    ),
    "nb_recv": MetricConfig(
        label="Total Packets Received",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "nb_sent": MetricConfig(
        label="Total Packets Sent",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "airtime": MetricConfig(
        label="Transmit Airtime",
        unit="s/min",
        type="counter",
        scale=60,
    ),
    "rx_airtime": MetricConfig(
        label="Receive Airtime",
        unit="s/min",
        type="counter",
        scale=60,
    ),
    "flood_dups": MetricConfig(
        label="Flood Duplicates Dropped",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "direct_dups": MetricConfig(
        label="Direct Duplicates Dropped",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "sent_flood": MetricConfig(
        label="Flood Packets Sent",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "recv_flood": MetricConfig(
        label="Flood Packets Received",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "sent_direct": MetricConfig(
        label="Direct Packets Sent",
        unit="/min",
        type="counter",
        scale=60,
    ),
    "recv_direct": MetricConfig(
        label="Direct Packets Received",
        unit="/min",
        type="counter",
        scale=60,
    ),

    # -------------------------------------------------------------------------
    # Derived metrics (computed at query time, not stored in database)
    # -------------------------------------------------------------------------
    "bat_pct": MetricConfig(
        label="Charge Level",
        unit="%",
    ),
}


# =============================================================================
# Metrics to display in charts (in display order)
# =============================================================================

COMPANION_CHART_METRICS = [
    "battery_mv",
    "bat_pct",
    "uptime_secs",
    "contacts",
    "recv",
    "sent",
]

REPEATER_CHART_METRICS = [
    "bat",
    "bat_pct",
    "last_rssi",
    "last_snr",
    "noise_floor",
    "uptime",
    "tx_queue_len",
    "nb_recv",
    "nb_sent",
    "airtime",
    "rx_airtime",
    "flood_dups",
    "direct_dups",
    "sent_flood",
    "recv_flood",
    "sent_direct",
    "recv_direct",
]


# =============================================================================
# Helper functions
# =============================================================================

def get_chart_metrics(role: str) -> list[str]:
    """Get list of metrics to chart for a role.

    Args:
        role: 'companion' or 'repeater'

    Returns:
        List of metric names in display order
    """
    if role == "companion":
        return COMPANION_CHART_METRICS
    elif role == "repeater":
        return REPEATER_CHART_METRICS
    else:
        raise ValueError(f"Unknown role: {role}")


def get_metric_config(metric: str) -> Optional[MetricConfig]:
    """Get configuration for a metric.

    Args:
        metric: Firmware field name

    Returns:
        MetricConfig or None if metric is not configured
    """
    return METRIC_CONFIG.get(metric)


def is_counter_metric(metric: str) -> bool:
    """Check if a metric is a counter type.

    Counter metrics show rate of change (delta per time unit).
    Gauge metrics show instantaneous values.

    Args:
        metric: Firmware field name

    Returns:
        True if counter, False if gauge or unknown
    """
    config = METRIC_CONFIG.get(metric)
    return config is not None and config.type == "counter"


def get_graph_scale(metric: str) -> float:
    """Get the scaling factor for graphing a metric.

    Args:
        metric: Firmware field name

    Returns:
        Scale factor (1.0 if not configured)
    """
    config = METRIC_CONFIG.get(metric)
    return config.scale if config else 1.0


def get_metric_label(metric: str) -> str:
    """Get human-readable label for a metric.

    Args:
        metric: Firmware field name

    Returns:
        Display label or the metric name if not configured
    """
    config = METRIC_CONFIG.get(metric)
    return config.label if config else metric


def get_metric_unit(metric: str) -> str:
    """Get display unit for a metric.

    Args:
        metric: Firmware field name

    Returns:
        Unit string or empty string if not configured
    """
    config = METRIC_CONFIG.get(metric)
    return config.unit if config else ""


def transform_value(metric: str, value: float) -> float:
    """Apply any configured transform to a metric value.

    Args:
        metric: Firmware field name
        value: Raw value from database

    Returns:
        Transformed value for display
    """
    config = METRIC_CONFIG.get(metric)
    if config and config.transform == "mv_to_v":
        return value / 1000.0
    return value
