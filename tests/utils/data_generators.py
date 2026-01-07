"""Utilities for generating test data."""

import random
from datetime import datetime, timedelta
from typing import Iterator


def generate_timeseries(
    metric: str,
    role: str,
    days: int = 7,
    interval_minutes: int = 15,
    base_value: float = 3.8,
    variance: float = 0.2,
) -> Iterator[tuple[int, float]]:
    """Generate sample time series data.

    Yields (timestamp, value) tuples with realistic variance patterns.

    Args:
        metric: Metric name (for documentation)
        role: Role name (for documentation)
        days: Number of days of data to generate
        interval_minutes: Minutes between data points
        base_value: Base value around which to vary
        variance: Maximum random variance from base

    Yields:
        (timestamp, value) tuples
    """
    now = datetime.now()
    points = int(days * 24 * 60 / interval_minutes)

    for i in range(points):
        ts = now - timedelta(minutes=i * interval_minutes)
        # Add a diurnal pattern (higher at noon)
        hour_factor = 0.1 * abs(12 - ts.hour) / 12
        value = base_value + random.uniform(-variance, variance) + hour_factor
        yield (int(ts.timestamp()), value)


def generate_counter_with_reboots(
    start_value: int = 0,
    readings: int = 100,
    reboot_probability: float = 0.05,
    increment_range: tuple[int, int] = (1, 50),
) -> list[tuple[datetime, int]]:
    """Generate counter values with occasional reboots.

    Simulates a monotonically increasing counter that occasionally
    resets to a low value (simulating device reboot).

    Args:
        start_value: Initial counter value
        readings: Number of readings to generate
        reboot_probability: Chance of reboot at each reading (0.0 to 1.0)
        increment_range: (min, max) range for counter increments

    Returns:
        List of (datetime, value) tuples
    """
    now = datetime.now()
    values: list[tuple[datetime, int]] = []
    current = start_value

    for i in range(readings):
        ts = now - timedelta(minutes=(readings - i) * 15)

        if random.random() < reboot_probability:
            # Simulate reboot - counter resets to small value
            current = random.randint(0, 100)
        else:
            # Normal increment
            current += random.randint(*increment_range)

        values.append((ts, current))

    return values


def generate_battery_discharge_curve(
    hours: int = 24,
    interval_minutes: int = 15,
    start_voltage: float = 4.2,
    end_voltage: float = 3.5,
) -> list[tuple[int, float]]:
    """Generate a realistic battery discharge curve.

    Simulates 18650 Li-ion discharge with realistic curve shape.

    Args:
        hours: Duration of discharge in hours
        interval_minutes: Minutes between readings
        start_voltage: Starting voltage (fully charged)
        end_voltage: Ending voltage

    Returns:
        List of (timestamp, voltage_mv) tuples (millivolts)
    """
    now = datetime.now()
    points = int(hours * 60 / interval_minutes)
    values: list[tuple[int, float]] = []

    for i in range(points):
        ts = now - timedelta(minutes=(points - i) * interval_minutes)
        # Simple linear discharge with some noise
        progress = i / points
        voltage = start_voltage - (start_voltage - end_voltage) * progress
        # Add small random variation
        voltage += random.uniform(-0.02, 0.02)
        values.append((int(ts.timestamp()), voltage * 1000))  # Convert to mV

    return values
