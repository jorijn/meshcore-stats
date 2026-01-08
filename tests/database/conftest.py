"""Fixtures for database tests."""

import time
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_state_dir):
    """Database path in temp state directory."""
    return tmp_state_dir / "metrics.db"


@pytest.fixture
def migrations_dir():
    """Path to actual migrations directory."""
    return Path(__file__).parent.parent.parent / "src" / "meshmon" / "migrations"


@pytest.fixture
def initialized_db(db_path, configured_env):
    """Fresh database with migrations applied."""
    from meshmon.db import init_db
    init_db(db_path)
    return db_path


@pytest.fixture
def populated_db(initialized_db, sample_companion_metrics, sample_repeater_metrics):
    """Database with 7 days of sample data."""
    from meshmon.db import insert_metrics

    now = int(time.time())
    day_seconds = 86400

    # Insert 7 days of companion data (every hour)
    for day in range(7):
        for hour in range(24):
            ts = now - (day * day_seconds) - (hour * 3600)
            metrics = sample_companion_metrics.copy()
            # Vary values slightly
            metrics["battery_mv"] = 3700 + (hour * 10) + (day * 5)
            metrics["recv"] = 100 * (day + 1) + hour
            metrics["sent"] = 50 * (day + 1) + hour
            insert_metrics(ts, "companion", metrics, initialized_db)

    # Insert 7 days of repeater data (every 15 minutes)
    for day in range(7):
        for interval in range(96):  # 24 * 4
            ts = now - (day * day_seconds) - (interval * 900)
            metrics = sample_repeater_metrics.copy()
            # Vary values slightly
            metrics["bat"] = 3700 + (interval * 2) + (day * 5)
            metrics["nb_recv"] = 1000 * (day + 1) + interval * 10
            metrics["nb_sent"] = 500 * (day + 1) + interval * 5
            insert_metrics(ts, "repeater", metrics, initialized_db)

    return initialized_db
