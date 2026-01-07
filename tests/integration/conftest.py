"""Integration test fixtures."""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock
import time


@pytest.fixture
def populated_db_with_history(initialized_db, sample_companion_metrics, sample_repeater_metrics):
    """Database populated with 30 days of historical data for integration tests."""
    from meshmon.db import insert_metrics

    now = int(time.time())
    day_seconds = 86400

    # Insert 30 days of companion data (every hour)
    for day in range(30):
        for hour in range(24):
            ts = now - (day * day_seconds) - (hour * 3600)
            metrics = sample_companion_metrics.copy()
            # Vary values to create realistic patterns
            metrics["battery_mv"] = 3700 + (hour * 5) + (day % 7) * 10
            metrics["recv"] = 100 + day * 10 + hour
            metrics["sent"] = 50 + day * 5 + hour
            metrics["uptime_secs"] = (30 - day) * day_seconds + hour * 3600
            insert_metrics(ts, "companion", metrics, initialized_db)

    # Insert 30 days of repeater data (every 15 minutes)
    for day in range(30):
        for interval in range(96):  # 24 * 4 = 96 intervals per day
            ts = now - (day * day_seconds) - (interval * 900)
            metrics = sample_repeater_metrics.copy()
            # Vary values to create realistic patterns
            metrics["bat"] = 3800 + (interval % 24) * 5 + (day % 7) * 10
            metrics["nb_recv"] = 1000 + day * 100 + interval
            metrics["nb_sent"] = 500 + day * 50 + interval
            metrics["uptime"] = (30 - day) * day_seconds + interval * 900
            metrics["last_rssi"] = -90 + (interval % 20)
            metrics["last_snr"] = 5 + (interval % 10) * 0.5
            insert_metrics(ts, "repeater", metrics, initialized_db)

    return initialized_db


@pytest.fixture
def mock_meshcore_successful_collection(sample_companion_metrics):
    """Mock MeshCore client that returns successful responses."""
    mc = MagicMock()
    mc.commands = MagicMock()
    mc.contacts = {}
    mc.disconnect = AsyncMock()

    # Helper to create successful event
    def make_event(event_type: str, payload: dict):
        event = MagicMock()
        event.type = MagicMock()
        event.type.name = event_type
        event.payload = payload
        return event

    # Mock all commands to return success - use AsyncMock directly without invoking
    mc.commands.send_appstart = AsyncMock(return_value=make_event("SELF_INFO", {}))
    mc.commands.send_device_query = AsyncMock(return_value=make_event("DEVICE_INFO", {}))
    mc.commands.get_time = AsyncMock(return_value=make_event("TIME", {"time": 1234567890}))
    mc.commands.get_self_telemetry = AsyncMock(return_value=make_event("TELEMETRY", {}))
    mc.commands.get_custom_vars = AsyncMock(return_value=make_event("CUSTOM_VARS", {}))
    mc.commands.get_contacts = AsyncMock(
        return_value=make_event("CONTACTS", {"contact1": {}, "contact2": {}})
    )
    mc.commands.get_stats_core = AsyncMock(
        return_value=make_event(
            "STATS_CORE",
            {"battery_mv": sample_companion_metrics["battery_mv"], "uptime_secs": 86400},
        )
    )
    mc.commands.get_stats_radio = AsyncMock(
        return_value=make_event("STATS_RADIO", {"noise_floor": -115, "last_rssi": -85})
    )
    mc.commands.get_stats_packets = AsyncMock(
        return_value=make_event(
            "STATS_PACKETS",
            {"recv": sample_companion_metrics["recv"], "sent": sample_companion_metrics["sent"]},
        )
    )

    return mc


@pytest.fixture
def full_integration_env(configured_env, monkeypatch):
    """Full integration environment with all directories set up.

    Builds on top of configured_env from root conftest.py to ensure
    consistent directory paths when used with other fixtures like
    initialized_db and populated_db_with_history.
    """
    monkeypatch.setenv("REPORT_LOCATION_NAME", "Test Location")
    monkeypatch.setenv("REPORT_LOCATION_SHORT", "Test")
    monkeypatch.setenv("REPEATER_DISPLAY_NAME", "Test Repeater")
    monkeypatch.setenv("COMPANION_DISPLAY_NAME", "Test Companion")
    monkeypatch.setenv("MESH_TRANSPORT", "serial")
    monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

    import meshmon.env
    meshmon.env._config = None

    return {
        "state_dir": configured_env["state_dir"],
        "out_dir": configured_env["out_dir"],
    }
