"""Fixtures for reports tests."""

from datetime import date, datetime, timedelta

import pytest


@pytest.fixture
def sample_daily_data():
    """Sample daily metrics data for report generation."""
    base_date = date(2024, 1, 15)
    return {
        "date": base_date,
        "bat": {
            "min": 3.5,
            "avg": 3.7,
            "max": 3.9,
            "count": 96,  # 15-min intervals for a day
        },
        "bat_pct": {
            "min": 50.0,
            "avg": 70.0,
            "max": 90.0,
            "count": 96,
        },
        "nb_recv": {
            "total": 12000,  # Counter total for the day
            "count": 96,
        },
        "nb_sent": {
            "total": 5000,
            "count": 96,
        },
    }


@pytest.fixture
def sample_monthly_data():
    """Sample monthly aggregated data."""
    return {
        "year": 2024,
        "month": 1,
        "bat": {
            "min": 3.3,
            "avg": 3.65,
            "max": 4.0,
            "count": 2976,  # ~31 days * 96 readings
        },
        "bat_pct": {
            "min": 40.0,
            "avg": 65.0,
            "max": 100.0,
            "count": 2976,
        },
        "nb_recv": {
            "total": 360000,
            "count": 2976,
        },
    }


@pytest.fixture
def sample_yearly_data():
    """Sample yearly aggregated data."""
    return {
        "year": 2024,
        "bat": {
            "min": 3.0,
            "avg": 3.6,
            "max": 4.2,
            "count": 35040,  # ~365 days * 96 readings
        },
        "nb_recv": {
            "total": 4320000,
            "count": 35040,
        },
    }


@pytest.fixture
def sample_counter_values():
    """Sample counter values with timestamps for reboot detection."""
    base_ts = datetime(2024, 1, 15, 0, 0, 0)
    return [
        (base_ts, 100),
        (base_ts + timedelta(minutes=15), 150),
        (base_ts + timedelta(minutes=30), 200),
        (base_ts + timedelta(minutes=45), 250),
        (base_ts + timedelta(hours=1), 300),
    ]


@pytest.fixture
def sample_counter_values_with_reboot():
    """Sample counter values with a device reboot."""
    base_ts = datetime(2024, 1, 15, 0, 0, 0)
    return [
        (base_ts, 100),
        (base_ts + timedelta(minutes=15), 150),
        (base_ts + timedelta(minutes=30), 200),
        (base_ts + timedelta(minutes=45), 50),  # Reboot! Counter reset
        (base_ts + timedelta(hours=1), 100),
    ]


@pytest.fixture
def reports_out_dir(configured_env):
    """Output directory for reports."""
    reports_dir = configured_env["out_dir"] / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir
