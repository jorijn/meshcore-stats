"""Tests for chart group building, including telemetry grouping behavior."""

from __future__ import annotations

import meshmon.html as html


def test_repeater_appends_telemetry_group_when_enabled(configured_env, monkeypatch):
    """Repeater chart groups append telemetry section when enabled and available."""
    monkeypatch.setenv("TELEMETRY_ENABLED", "1")
    import meshmon.env
    meshmon.env._config = None

    monkeypatch.setattr(html, "_load_svg_content", lambda path: "<svg></svg>")

    chart_stats = {
        "bat": {"day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.8}},
        "telemetry.temperature.1": {"day": {"min": 5.0, "avg": 6.0, "max": 7.0, "current": 6.5}},
        "telemetry.humidity.1": {"day": {"min": 82.0, "avg": 84.0, "max": 86.0, "current": 85.0}},
        "telemetry.voltage.1": {"day": {"min": 3.9, "avg": 4.0, "max": 4.1, "current": 4.0}},
        "telemetry.gps.0.latitude": {"day": {"min": 52.1, "avg": 52.2, "max": 52.3, "current": 52.25}},
    }

    groups = html.build_chart_groups("repeater", "day", chart_stats)

    assert groups[-1]["title"] == "Telemetry"
    telemetry_metrics = [chart["metric"] for chart in groups[-1]["charts"]]
    assert "telemetry.temperature.1" in telemetry_metrics
    assert "telemetry.humidity.1" in telemetry_metrics
    assert "telemetry.voltage.1" not in telemetry_metrics
    assert "telemetry.gps.0.latitude" not in telemetry_metrics


def test_repeater_has_no_telemetry_group_when_disabled(configured_env, monkeypatch):
    """Repeater chart groups do not include telemetry section when disabled."""
    monkeypatch.setenv("TELEMETRY_ENABLED", "0")
    import meshmon.env
    meshmon.env._config = None

    monkeypatch.setattr(html, "_load_svg_content", lambda path: "<svg></svg>")

    chart_stats = {
        "bat": {"day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.8}},
        "telemetry.temperature.1": {"day": {"min": 5.0, "avg": 6.0, "max": 7.0, "current": 6.5}},
    }

    groups = html.build_chart_groups("repeater", "day", chart_stats)

    assert "Telemetry" not in [group["title"] for group in groups]
