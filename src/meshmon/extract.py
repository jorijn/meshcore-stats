"""Extract metrics from nested dictionaries using dotted paths."""

from typing import Any, Optional, Union


def get_by_path(obj: dict[str, Any], path: str) -> Optional[Any]:
    """
    Get a value from a nested dict using a dotted path.

    Args:
        obj: The dictionary to search
        path: Dotted path like "bat.voltage_v" or "derived.contacts_count"

    Returns:
        The value at the path, or None if not found
    """
    parts = path.split(".")
    current: Any = obj

    for part in parts:
        if current is None:
            return None
        if isinstance(current, dict):
            current = current.get(part)
        elif hasattr(current, part):
            current = getattr(current, part)
        else:
            return None

    return current


def coerce_to_float(value: Any) -> Optional[float]:
    """
    Safely coerce a value to float.

    Args:
        value: Any value

    Returns:
        Float value, or None if conversion fails
    """
    if value is None:
        return None

    if isinstance(value, (int, float)):
        return float(value)

    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None

    return None


def extract_metric(obj: dict[str, Any], path: str) -> Optional[float]:
    """
    Extract a metric value from a nested dict and coerce to float.

    Args:
        obj: The dictionary to search
        path: Dotted path to the value

    Returns:
        Float value, or None if not found or not convertible
    """
    value = get_by_path(obj, path)
    return coerce_to_float(value)


def extract_metrics(
    obj: dict[str, Any], metrics: dict[str, str]
) -> dict[str, Optional[float]]:
    """
    Extract multiple metrics from a dict.

    Args:
        obj: The dictionary to search
        metrics: Mapping of ds_name -> dotted_path

    Returns:
        Mapping of ds_name -> extracted value (or None)
    """
    return {ds_name: extract_metric(obj, path) for ds_name, path in metrics.items()}


def format_rrd_value(value: Optional[float], as_integer: bool = False) -> str:
    """Format a value for RRD update (use 'U' for unknown)."""
    if value is None:
        return "U"
    if as_integer:
        return str(int(value))
    return str(value)
