"""Tests for render_all_charts metric selection behavior."""

from __future__ import annotations

from datetime import datetime

import meshmon.charts as charts


def test_render_all_charts_includes_repeater_telemetry_when_enabled(configured_env, monkeypatch):
    """Repeater chart rendering auto-discovers telemetry metrics when enabled."""
    monkeypatch.setenv("TELEMETRY_ENABLED", "1")
    import meshmon.env
    meshmon.env._config = None

    base_ts = int(datetime(2024, 1, 1, 0, 0, 0).timestamp())

    monkeypatch.setattr(
        charts,
        "get_available_metrics",
        lambda role: [
            "bat",
            "telemetry.temperature.1",
            "telemetry.humidity.1",
            "telemetry.voltage.1",
            "telemetry.gps.0.latitude",
        ],
    )
    monkeypatch.setattr(
        charts,
        "get_metrics_for_period",
        lambda role, start_ts, end_ts: {
            "telemetry.temperature.1": [
                (base_ts, 6.0),
                (base_ts + 900, 7.0),
            ],
            "telemetry.humidity.1": [
                (base_ts, 84.0),
                (base_ts + 900, 85.0),
            ],
        },
    )
    monkeypatch.setattr(charts, "render_chart_svg", lambda *args, **kwargs: "<svg></svg>")

    _generated, stats = charts.render_all_charts("repeater")

    assert "telemetry.temperature.1" in stats
    assert "telemetry.humidity.1" in stats
    assert "telemetry.voltage.1" not in stats
    assert "telemetry.gps.0.latitude" not in stats


def test_render_all_charts_excludes_telemetry_when_disabled(configured_env, monkeypatch):
    """Telemetry metrics are not rendered when TELEMETRY_ENABLED=0."""
    monkeypatch.setenv("TELEMETRY_ENABLED", "0")
    import meshmon.env
    meshmon.env._config = None

    monkeypatch.setattr(
        charts,
        "get_available_metrics",
        lambda role: ["bat", "telemetry.temperature.1", "telemetry.humidity.1"],
    )
    monkeypatch.setattr(charts, "get_metrics_for_period", lambda role, start_ts, end_ts: {})
    monkeypatch.setattr(charts, "render_chart_svg", lambda *args, **kwargs: "<svg></svg>")

    _generated, stats = charts.render_all_charts("repeater")

    assert not any(metric.startswith("telemetry.") for metric in stats)
