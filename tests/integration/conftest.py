"""Integration test fixtures."""

import os
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

_INTEGRATION_ENV = {
    "REPORT_LOCATION_NAME": "Test Location",
    "REPORT_LOCATION_SHORT": "Test",
    "REPEATER_DISPLAY_NAME": "Test Repeater",
    "COMPANION_DISPLAY_NAME": "Test Companion",
    "MESH_TRANSPORT": "serial",
    "MESH_SERIAL_PORT": "/dev/ttyACM0",
}
RENDERED_CHART_METRICS = {
    "companion": ["battery_mv"],
    "repeater": ["bat"],
}


def _sample_companion_metrics() -> dict[str, float]:
    return {
        "battery_mv": 3850.0,
        "uptime_secs": 86400.0,
        "contacts": 5.0,
        "recv": 1234.0,
        "sent": 567.0,
        "errors": 0.0,
    }


def _sample_repeater_metrics() -> dict[str, float]:
    return {
        "bat": 3920.0,
        "uptime": 172800.0,
        "last_rssi": -85.0,
        "last_snr": 7.5,
        "noise_floor": -115.0,
        "tx_queue_len": 0.0,
        "nb_recv": 5678.0,
        "nb_sent": 2345.0,
        "airtime": 3600.0,
        "rx_airtime": 7200.0,
        "flood_dups": 12.0,
        "direct_dups": 5.0,
        "sent_flood": 100.0,
        "recv_flood": 200.0,
        "sent_direct": 50.0,
        "recv_direct": 75.0,
    }


def _populate_db_with_history(
    db_path,
    sample_companion_metrics: dict[str, float],
    sample_repeater_metrics: dict[str, float],
    days: int = 30,
    companion_step_seconds: int = 3600,
    repeater_step_seconds: int = 900,
) -> None:
    from meshmon.db import insert_metrics

    now = int(time.time())
    day_seconds = 86400
    companion_steps = day_seconds // companion_step_seconds
    repeater_steps = day_seconds // repeater_step_seconds

    # Insert companion data (default: 30 days, hourly)
    for day in range(days):
        for step in range(companion_steps):
            ts = now - (day * day_seconds) - (step * companion_step_seconds)
            metrics = sample_companion_metrics.copy()
            # Vary values to create realistic patterns
            metrics["battery_mv"] = 3700 + (step * 5) + (day % 7) * 10
            metrics["recv"] = 100 + day * 10 + step
            metrics["sent"] = 50 + day * 5 + step
            metrics["uptime_secs"] = (days - day) * day_seconds + step * companion_step_seconds
            insert_metrics(ts, "companion", metrics, db_path=db_path)

    # Insert repeater data (default: 30 days, every 15 minutes)
    for day in range(days):
        for interval in range(repeater_steps):
            ts = now - (day * day_seconds) - (interval * repeater_step_seconds)
            metrics = sample_repeater_metrics.copy()
            # Vary values to create realistic patterns
            metrics["bat"] = 3800 + (interval % 24) * 5 + (day % 7) * 10
            metrics["nb_recv"] = 1000 + day * 100 + interval
            metrics["nb_sent"] = 500 + day * 50 + interval
            metrics["uptime"] = (days - day) * day_seconds + interval * repeater_step_seconds
            metrics["last_rssi"] = -90 + (interval % 20)
            metrics["last_snr"] = 5 + (interval % 10) * 0.5
            insert_metrics(ts, "repeater", metrics, db_path=db_path)


@pytest.fixture
def reports_env(reports_db_cache, tmp_out_dir, monkeypatch):
    """Integration env wired to the shared reports DB and per-test output."""
    monkeypatch.setenv("STATE_DIR", str(reports_db_cache["state_dir"]))
    monkeypatch.setenv("OUT_DIR", str(tmp_out_dir))
    for key, value in _INTEGRATION_ENV.items():
        monkeypatch.setenv(key, value)

    import meshmon.env
    meshmon.env._config = None

    return {
        "state_dir": reports_db_cache["state_dir"],
        "out_dir": tmp_out_dir,
    }


@pytest.fixture(scope="session")
def rendered_chart_metrics():
    """Minimal chart set to keep integration rendering tests fast."""
    return RENDERED_CHART_METRICS


@pytest.fixture
def populated_db_with_history(reports_db_cache, reports_env):
    """Shared database populated with a fixed history window for integration tests."""
    return reports_db_cache["db_path"]


@pytest.fixture(scope="module")
def reports_db_cache(tmp_path_factory):
    """Create and populate a shared reports DB once per module."""
    from meshmon.db import init_db

    root_dir = tmp_path_factory.mktemp("reports-db")
    state_dir = root_dir / "state"
    state_dir.mkdir()

    db_path = state_dir / "metrics.db"
    init_db(db_path=db_path)
    _populate_db_with_history(
        db_path,
        _sample_companion_metrics(),
        _sample_repeater_metrics(),
        days=14,
        companion_step_seconds=7200,
        repeater_step_seconds=7200,
    )

    return {
        "state_dir": state_dir,
        "db_path": db_path,
    }


@pytest.fixture(scope="module")
def rendered_charts_cache(tmp_path_factory):
    """Cache rendered charts once per module to speed up integration tests."""
    from meshmon.charts import render_all_charts, save_chart_stats
    from meshmon.db import init_db

    root_dir = tmp_path_factory.mktemp("rendered-charts")
    state_dir = root_dir / "state"
    out_dir = root_dir / "out"
    state_dir.mkdir()
    out_dir.mkdir()

    env_keys = ["STATE_DIR", "OUT_DIR", *_INTEGRATION_ENV.keys()]
    previous_env = {key: os.environ.get(key) for key in env_keys}

    os.environ["STATE_DIR"] = str(state_dir)
    os.environ["OUT_DIR"] = str(out_dir)
    for key, value in _INTEGRATION_ENV.items():
        os.environ[key] = value

    import meshmon.env
    meshmon.env._config = None

    db_path = state_dir / "metrics.db"
    init_db(db_path=db_path)
    _populate_db_with_history(
        db_path,
        _sample_companion_metrics(),
        _sample_repeater_metrics(),
        days=7,
        companion_step_seconds=3600,
        repeater_step_seconds=3600,
    )

    for role in ["companion", "repeater"]:
        charts, stats = render_all_charts(role, metrics=RENDERED_CHART_METRICS[role])
        save_chart_stats(role, stats)

    yield {
        "state_dir": state_dir,
        "out_dir": out_dir,
        "db_path": db_path,
    }

    for key, value in previous_env.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value

    meshmon.env._config = None


@pytest.fixture
def rendered_charts(rendered_charts_cache, monkeypatch):
    """Expose cached charts with env wired for per-test access."""
    state_dir = rendered_charts_cache["state_dir"]
    out_dir = rendered_charts_cache["out_dir"]

    monkeypatch.setenv("STATE_DIR", str(state_dir))
    monkeypatch.setenv("OUT_DIR", str(out_dir))
    for key, value in _INTEGRATION_ENV.items():
        monkeypatch.setenv(key, value)

    import meshmon.env
    meshmon.env._config = None

    return rendered_charts_cache


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
    """Full integration environment with per-test directories."""
    for key, value in _INTEGRATION_ENV.items():
        monkeypatch.setenv(key, value)

    import meshmon.env
    meshmon.env._config = None

    return {
        "state_dir": configured_env["state_dir"],
        "out_dir": configured_env["out_dir"],
    }
