"""Root fixtures for all tests."""

import os
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Clear mesh-related env vars and reset config singleton before each test."""
    env_prefixes = (
        "MESH_",
        "REPEATER_",
        "COMPANION_",
        "REMOTE_",
        "TELEMETRY_",
        "DISPLAY_",
        "REPORT_",
        "RADIO_",
        "STATE_DIR",
        "OUT_DIR",
    )

    for key in list(os.environ.keys()):
        for prefix in env_prefixes:
            if key.startswith(prefix):
                monkeypatch.delenv(key, raising=False)
                break

    # Reset config singleton
    import meshmon.env

    meshmon.env._config = None

    yield

    # Reset again after test
    meshmon.env._config = None


@pytest.fixture
def tmp_state_dir(tmp_path):
    """Create temp directory for state files (DB, circuit breaker)."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    return state_dir


@pytest.fixture
def tmp_out_dir(tmp_path):
    """Create temp directory for rendered output."""
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    return out_dir


@pytest.fixture
def configured_env(tmp_state_dir, tmp_out_dir, monkeypatch):
    """Set up test environment with temp directories."""
    monkeypatch.setenv("STATE_DIR", str(tmp_state_dir))
    monkeypatch.setenv("OUT_DIR", str(tmp_out_dir))
    # Reset config to pick up new values
    import meshmon.env

    meshmon.env._config = None
    return {"state_dir": tmp_state_dir, "out_dir": tmp_out_dir}


@pytest.fixture
def sample_companion_metrics():
    """Sample companion metrics using firmware field names."""
    return {
        "battery_mv": 3850.0,
        "uptime_secs": 86400,
        "contacts": 5,
        "recv": 1234,
        "sent": 567,
        "errors": 0,
    }


@pytest.fixture
def sample_repeater_metrics():
    """Sample repeater metrics using firmware field names."""
    return {
        "bat": 3920.0,
        "uptime": 172800,
        "last_rssi": -85,
        "last_snr": 7.5,
        "noise_floor": -115,
        "tx_queue_len": 0,
        "nb_recv": 5678,
        "nb_sent": 2345,
        "airtime": 3600,
        "rx_airtime": 7200,
        "flood_dups": 12,
        "direct_dups": 5,
        "sent_flood": 100,
        "recv_flood": 200,
        "sent_direct": 50,
        "recv_direct": 75,
    }


@pytest.fixture
def project_root():
    """Path to the project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture
def src_root(project_root):
    """Path to the src/meshmon directory."""
    return project_root / "src" / "meshmon"


@pytest.fixture
def db_path(tmp_state_dir):
    """Database path in temp state directory."""
    return tmp_state_dir / "metrics.db"


@pytest.fixture
def migrations_dir(project_root):
    """Path to actual migrations directory."""
    return project_root / "src" / "meshmon" / "migrations"


@pytest.fixture
def initialized_db(db_path, configured_env, monkeypatch):
    """Fresh database with migrations applied."""
    from meshmon.db import init_db

    init_db()
    return db_path


@pytest.fixture
def populated_db(initialized_db, sample_companion_metrics, sample_repeater_metrics):
    """Database with 7 days of sample data."""
    import time

    from meshmon.db import insert_metrics

    now = int(time.time())
    day_seconds = 86400

    # Insert 7 days of companion data (every hour)
    for day in range(7):
        for hour in range(24):
            ts = now - (day * day_seconds) - (hour * 3600)
            metrics = sample_companion_metrics.copy()
            metrics["battery_mv"] = 3700 + (hour * 10) + (day * 5)
            metrics["recv"] = 100 * (day + 1) + hour
            metrics["sent"] = 50 * (day + 1) + hour
            insert_metrics(ts, "companion", metrics)

    # Insert 7 days of repeater data (every 15 minutes)
    for day in range(7):
        for interval in range(96):  # 24 * 4
            ts = now - (day * day_seconds) - (interval * 900)
            metrics = sample_repeater_metrics.copy()
            metrics["bat"] = 3700 + (interval * 2) + (day * 5)
            metrics["nb_recv"] = 1000 * (day + 1) + interval * 10
            metrics["nb_sent"] = 500 * (day + 1) + interval * 5
            insert_metrics(ts, "repeater", metrics)

    return initialized_db
