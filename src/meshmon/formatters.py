"""Shared formatting functions for display values."""

from datetime import datetime
from typing import Any

from .battery import voltage_to_percentage

Number = int | float


def format_time(ts: int | None) -> str:
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


def format_number(value: int | None) -> str:
    """Format an integer with thousands separators."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def format_duration(seconds: int | None) -> str:
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


def format_uptime(seconds: int | None) -> str:
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


def format_voltage_with_pct(mv: float | None) -> str:
    """Format millivolts as voltage with battery percentage."""
    if mv is None:
        return "N/A"
    v = mv / 1000.0
    pct = voltage_to_percentage(v)
    return f"{v:.2f} V ({pct:.0f}%)"


def format_compact_number(value: Number | None, precision: int = 1) -> str:
    """Format a number using compact notation (k, M suffixes).

    Rules:
    - None: Returns "N/A"
    - < 1,000: Raw integer (847)
    - 1,000 - 9,999: Comma-separated (4,989)
    - 10,000 - 999,999: Compact with suffix (242.1k)
    - >= 1,000,000: Millions (1.5M)

    Args:
        value: The numeric value to format
        precision: Decimal places for compact notation (default: 1)

    Returns:
        Formatted string
    """
    if value is None:
        return "N/A"

    # Handle negative values
    if value < 0:
        return f"-{format_compact_number(abs(value), precision)}"

    if value >= 1_000_000:
        return f"{value / 1_000_000:.{precision}f}M"
    elif value >= 10_000:
        return f"{value / 1_000:.{precision}f}k"
    elif value >= 1_000:
        return f"{int(value):,}"
    else:
        return str(int(value))


def format_duration_compact(seconds: int | None) -> str:
    """Format duration showing only the two most significant units.

    Uses truncation (floor), not rounding.

    Rules:
    - None: Returns "N/A"
    - 0: Returns "0s"
    - < 60s: Seconds only (45s)
    - < 1h: Minutes + seconds (45m 12s)
    - < 1d: Hours + minutes (19h 45m)
    - >= 1d: Days + hours (1d 20h)

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds is None:
        return "N/A"
    if seconds == 0:
        return "0s"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60

    if days > 0:
        return f"{days}d {hours}h"
    elif hours > 0:
        return f"{hours}h {mins}m"
    elif mins > 0:
        return f"{mins}m {secs}s"
    else:
        return f"{secs}s"
