"""Shared formatting functions for display values."""

from datetime import datetime
from typing import Any, Optional

from .battery import voltage_to_percentage


def format_time(ts: Optional[int]) -> str:
    """Format Unix timestamp to human readable string."""
    if ts is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return "N/A"


def format_value(value: Any) -> str:
    """Format a value for display."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def format_number(value: Optional[int]) -> str:
    """Format an integer with thousands separators."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def format_duration(seconds: Optional[int]) -> str:
    """Format duration in seconds to human readable string (days, hours, minutes, seconds)."""
    if seconds is None:
        return "N/A"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if mins > 0 or hours > 0 or days > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def format_uptime(seconds: Optional[int]) -> str:
    """Format uptime seconds to human readable string (days, hours, minutes)."""
    if seconds is None:
        return "N/A"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")

    return " ".join(parts)


def format_voltage_with_pct(mv: Optional[float]) -> str:
    """Format millivolts as voltage with battery percentage."""
    if mv is None:
        return "N/A"
    v = mv / 1000.0
    pct = voltage_to_percentage(v)
    return f"{v:.2f} V ({pct:.0f}%)"
