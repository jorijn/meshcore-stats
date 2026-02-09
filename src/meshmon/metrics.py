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

import re
from dataclasses import dataclass

TELEMETRY_METRIC_RE = re.compile(
    r"^telemetry\.([a-z0-9_]+)\.(\d+)(?:\.([a-z0-9_]+))?$"
)
TELEMETRY_EXCLUDED_SENSOR_TYPES = {"gps", "voltage"}
HPA_TO_INHG = 0.029529983071445
M_TO_FT = 3.280839895013123


@dataclass(frozen=True)
class TelemetryMetricParts:
    """Parsed telemetry metric parts."""

    sensor_type: str
    channel: int
    subkey: str | None = None


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
    transform: str | None = None


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

def parse_telemetry_metric(metric: str) -> TelemetryMetricParts | None:
    """Parse telemetry metric key into its parts.

    Expected format: telemetry.<type>.<channel>[.<subkey>]
    """
    match = TELEMETRY_METRIC_RE.match(metric)
    if not match:
        return None
    sensor_type, channel_raw, subkey = match.groups()
    return TelemetryMetricParts(
        sensor_type=sensor_type,
        channel=int(channel_raw),
        subkey=subkey,
    )


def is_telemetry_metric(metric: str) -> bool:
    """Check if metric key is a telemetry metric."""
    return parse_telemetry_metric(metric) is not None


def _normalize_unit_system(unit_system: str) -> str:
    """Normalize unit system string to metric/imperial."""
    return unit_system if unit_system in ("metric", "imperial") else "metric"


def _humanize_token(token: str) -> str:
    """Convert snake_case token to display title, preserving common acronyms."""
    if token.lower() == "gps":
        return "GPS"
    return token.replace("_", " ").title()


def get_telemetry_metric_label(metric: str) -> str:
    """Get human-readable label for a telemetry metric key."""
    parts = parse_telemetry_metric(metric)
    if parts is None:
        return metric

    base = _humanize_token(parts.sensor_type)
    if parts.subkey:
        base = f"{base} {_humanize_token(parts.subkey)}"
    return f"{base} (CH{parts.channel})"


def get_telemetry_metric_unit(metric: str, unit_system: str = "metric") -> str:
    """Get telemetry unit based on metric type and selected unit system."""
    parts = parse_telemetry_metric(metric)
    if parts is None:
        return ""

    unit_system = _normalize_unit_system(unit_system)

    if parts.sensor_type == "temperature":
        return "°F" if unit_system == "imperial" else "°C"
    if parts.sensor_type == "humidity":
        return "%"
    if parts.sensor_type in ("barometer", "pressure"):
        return "inHg" if unit_system == "imperial" else "hPa"
    if parts.sensor_type == "altitude":
        return "ft" if unit_system == "imperial" else "m"
    return ""


def get_telemetry_metric_decimals(metric: str, unit_system: str = "metric") -> int:
    """Get display decimal precision for telemetry metrics."""
    parts = parse_telemetry_metric(metric)
    if parts is None:
        return 2

    unit_system = _normalize_unit_system(unit_system)

    if parts.sensor_type in ("temperature", "humidity", "altitude"):
        return 1
    if parts.sensor_type in ("barometer", "pressure"):
        return 2 if unit_system == "imperial" else 1
    return 2


def convert_telemetry_value(metric: str, value: float, unit_system: str = "metric") -> float:
    """Convert telemetry value to selected display unit system."""
    parts = parse_telemetry_metric(metric)
    if parts is None:
        return value

    unit_system = _normalize_unit_system(unit_system)
    if unit_system != "imperial":
        return value

    if parts.sensor_type == "temperature":
        return (value * 9.0 / 5.0) + 32.0
    if parts.sensor_type in ("barometer", "pressure"):
        return value * HPA_TO_INHG
    if parts.sensor_type == "altitude":
        return value * M_TO_FT
    return value


def discover_telemetry_chart_metrics(available_metrics: list[str]) -> list[str]:
    """Discover telemetry metrics to chart from available metric keys."""
    discovered: set[str] = set()
    for metric in available_metrics:
        parts = parse_telemetry_metric(metric)
        if parts is None:
            continue
        if parts.sensor_type in TELEMETRY_EXCLUDED_SENSOR_TYPES:
            continue
        discovered.add(metric)

    return sorted(
        discovered,
        key=lambda metric: (get_telemetry_metric_label(metric).lower(), metric),
    )


def get_chart_metrics(
    role: str,
    available_metrics: list[str] | None = None,
    telemetry_enabled: bool = False,
) -> list[str]:
    """Get list of metrics to chart for a role.

    Args:
        role: 'companion' or 'repeater'
        available_metrics: Optional list of available metrics for discovery
        telemetry_enabled: Whether telemetry charts should be included

    Returns:
        List of metric names in display order
    """
    if role == "companion":
        return list(COMPANION_CHART_METRICS)
    elif role == "repeater":
        metrics = list(REPEATER_CHART_METRICS)
        if telemetry_enabled and available_metrics:
            for metric in discover_telemetry_chart_metrics(available_metrics):
                if metric not in metrics:
                    metrics.append(metric)
        return metrics
    else:
        raise ValueError(f"Unknown role: {role}")


def get_metric_config(metric: str) -> MetricConfig | None:
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
    if config:
        return config.label
    if is_telemetry_metric(metric):
        return get_telemetry_metric_label(metric)
    return metric


def get_metric_unit(metric: str, unit_system: str = "metric") -> str:
    """Get display unit for a metric.

    Args:
        metric: Firmware field name
        unit_system: Unit system for telemetry metrics ('metric' or 'imperial')

    Returns:
        Unit string or empty string if not configured
    """
    config = METRIC_CONFIG.get(metric)
    if config:
        return config.unit
    if is_telemetry_metric(metric):
        return get_telemetry_metric_unit(metric, unit_system)
    return ""


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
