"""Tests for chart statistics I/O functions."""

import json
from pathlib import Path

import pytest

from meshmon.charts import (
    load_chart_stats,
    save_chart_stats,
)


class TestSaveChartStats:
    """Tests for save_chart_stats function."""

    def test_saves_stats_to_file(self, configured_env):
        """Saves stats dict to JSON file."""
        stats = {
            "bat": {
                "day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.85},
                "week": {"min": 3.4, "avg": 3.65, "max": 3.95, "current": 3.85},
            }
        }

        path = save_chart_stats("repeater", stats)

        assert path.exists()
        with open(path) as f:
            loaded = json.load(f)
        assert loaded == stats

    def test_creates_directories(self, configured_env):
        """Creates parent directories if needed."""
        stats = {"test": {"day": {"min": 1.0}}}

        path = save_chart_stats("repeater", stats)

        assert path.parent.exists()
        assert path.parent.name == "repeater"

    def test_returns_path(self, configured_env):
        """Returns path to saved file."""
        stats = {"test": {"day": {}}}

        path = save_chart_stats("companion", stats)

        assert isinstance(path, Path)
        assert path.name == "chart_stats.json"
        assert "companion" in str(path)

    def test_overwrites_existing(self, configured_env):
        """Overwrites existing stats file."""
        stats1 = {"metric1": {"day": {"min": 1.0}}}
        stats2 = {"metric2": {"day": {"min": 2.0}}}

        path1 = save_chart_stats("repeater", stats1)
        path2 = save_chart_stats("repeater", stats2)

        assert path1 == path2
        with open(path2) as f:
            loaded = json.load(f)
        assert loaded == stats2

    def test_empty_stats(self, configured_env):
        """Saves empty stats dict."""
        stats = {}

        path = save_chart_stats("repeater", stats)

        with open(path) as f:
            loaded = json.load(f)
        assert loaded == {}

    def test_nested_stats_structure(self, configured_env):
        """Preserves nested structure of stats."""
        stats = {
            "bat": {
                "day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.85},
                "week": {"min": 3.4, "avg": 3.65, "max": 3.95, "current": None},
            },
            "nb_recv": {
                "day": {"min": 0, "avg": 50.5, "max": 100, "current": 75},
            }
        }

        path = save_chart_stats("repeater", stats)

        with open(path) as f:
            loaded = json.load(f)
        assert loaded["bat"]["week"]["current"] is None
        assert loaded["nb_recv"]["day"]["avg"] == 50.5


class TestLoadChartStats:
    """Tests for load_chart_stats function."""

    def test_loads_existing_stats(self, configured_env):
        """Loads stats from existing file."""
        stats = {
            "bat": {
                "day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.85},
            }
        }
        save_chart_stats("repeater", stats)

        loaded = load_chart_stats("repeater")

        assert loaded == stats

    def test_returns_empty_when_missing(self, configured_env):
        """Returns empty dict when file doesn't exist."""
        loaded = load_chart_stats("repeater")

        assert loaded == {}

    def test_returns_empty_on_invalid_json(self, configured_env):
        """Returns empty dict on invalid JSON."""
        stats_path = configured_env["out_dir"] / "assets" / "repeater" / "chart_stats.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text("not valid json {{{", encoding="utf-8")

        loaded = load_chart_stats("repeater")

        assert loaded == {}

    def test_preserves_none_values(self, configured_env):
        """None values are preserved through save/load cycle."""
        stats = {
            "bat": {
                "day": {"min": None, "avg": None, "max": None, "current": None},
            }
        }
        save_chart_stats("repeater", stats)

        loaded = load_chart_stats("repeater")

        assert loaded["bat"]["day"]["min"] is None
        assert loaded["bat"]["day"]["avg"] is None

    def test_loads_different_roles(self, configured_env):
        """Loads correct file for each role."""
        companion_stats = {"battery_mv": {"day": {"min": 3.5}}}
        repeater_stats = {"bat": {"day": {"min": 3.6}}}

        save_chart_stats("companion", companion_stats)
        save_chart_stats("repeater", repeater_stats)

        assert load_chart_stats("companion") == companion_stats
        assert load_chart_stats("repeater") == repeater_stats


class TestStatsRoundTrip:
    """Tests for complete save/load round trips."""

    def test_complex_stats_roundtrip(self, configured_env):
        """Complex stats survive round trip unchanged."""
        stats = {
            "bat": {
                "day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.85},
                "week": {"min": 3.4, "avg": 3.65, "max": 3.95, "current": 3.8},
                "month": {"min": 3.3, "avg": 3.6, "max": 4.0, "current": 3.75},
                "year": {"min": 3.2, "avg": 3.55, "max": 4.1, "current": 3.7},
            },
            "bat_pct": {
                "day": {"min": 50.0, "avg": 70.0, "max": 90.0, "current": 85.0},
                "week": {"min": 45.0, "avg": 65.0, "max": 95.0, "current": 80.0},
                "month": {"min": 40.0, "avg": 60.0, "max": 100.0, "current": 75.0},
                "year": {"min": 30.0, "avg": 55.0, "max": 100.0, "current": 70.0},
            },
            "nb_recv": {
                "day": {"min": 0, "avg": 50.5, "max": 100, "current": 75},
                "week": {"min": 0, "avg": 48.2, "max": 150, "current": 60},
                "month": {"min": 0, "avg": 45.8, "max": 200, "current": 55},
                "year": {"min": 0, "avg": 42.1, "max": 250, "current": 50},
            },
        }

        save_chart_stats("repeater", stats)
        loaded = load_chart_stats("repeater")

        assert loaded == stats

    def test_float_precision_preserved(self, configured_env):
        """Float precision is preserved in round trip."""
        stats = {
            "test": {
                "day": {
                    "min": 3.141592653589793,
                    "avg": 2.718281828459045,
                    "max": 1.4142135623730951,
                    "current": 0.0001234567890123,
                }
            }
        }

        save_chart_stats("repeater", stats)
        loaded = load_chart_stats("repeater")

        assert loaded["test"]["day"]["min"] == pytest.approx(3.141592653589793)
        assert loaded["test"]["day"]["avg"] == pytest.approx(2.718281828459045)
