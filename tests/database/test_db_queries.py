"""Tests for database query functions."""

import time

import pytest

from meshmon.db import (
    get_available_metrics,
    get_distinct_timestamps,
    get_latest_metrics,
    get_metric_count,
    get_metrics_for_period,
    insert_metrics,
)


class TestGetMetricsForPeriod:
    """Tests for get_metrics_for_period function."""

    def test_returns_dict_by_metric(self, initialized_db):
        """Returns dict with metric names as keys."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {
            "battery_mv": 3850.0,
            "contacts": 5,
        }, initialized_db)

        result = get_metrics_for_period(
            "companion", ts - 100, ts + 100, initialized_db
        )

        assert isinstance(result, dict)
        assert "battery_mv" in result
        assert "contacts" in result

    def test_returns_timestamp_value_tuples(self, initialized_db):
        """Each metric has list of (ts, value) tuples."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"test": 1.0}, initialized_db)

        result = get_metrics_for_period(
            "companion", ts - 100, ts + 100, initialized_db
        )

        assert len(result["test"]) == 1
        assert result["test"][0] == (ts, 1.0)

    def test_sorted_by_timestamp(self, initialized_db):
        """Results are sorted by timestamp ascending."""
        base_ts = int(time.time())

        # Insert out of order
        insert_metrics(base_ts + 200, "companion", {"test": 3.0}, initialized_db)
        insert_metrics(base_ts, "companion", {"test": 1.0}, initialized_db)
        insert_metrics(base_ts + 100, "companion", {"test": 2.0}, initialized_db)

        result = get_metrics_for_period(
            "companion", base_ts - 100, base_ts + 300, initialized_db
        )

        values = [v for ts, v in result["test"]]
        assert values == [1.0, 2.0, 3.0]

    def test_respects_time_range(self, initialized_db):
        """Only returns data within specified time range."""
        base_ts = int(time.time())

        insert_metrics(base_ts - 200, "companion", {"test": 1.0}, initialized_db)  # Outside
        insert_metrics(base_ts, "companion", {"test": 2.0}, initialized_db)  # Inside
        insert_metrics(base_ts + 200, "companion", {"test": 3.0}, initialized_db)  # Outside

        result = get_metrics_for_period(
            "companion", base_ts - 100, base_ts + 100, initialized_db
        )

        assert len(result["test"]) == 1
        assert result["test"][0][1] == 2.0

    def test_filters_by_role(self, initialized_db):
        """Only returns data for specified role."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"test": 1.0}, initialized_db)
        insert_metrics(ts, "repeater", {"test": 2.0}, initialized_db)

        result = get_metrics_for_period(
            "companion", ts - 100, ts + 100, initialized_db
        )

        assert result["test"][0][1] == 1.0

    def test_computes_bat_pct(self, initialized_db):
        """Computes bat_pct from battery voltage."""
        ts = int(time.time())
        # 4200 mV = 4.2V = 100%
        insert_metrics(ts, "companion", {"battery_mv": 4200.0}, initialized_db)

        result = get_metrics_for_period(
            "companion", ts - 100, ts + 100, initialized_db
        )

        assert "bat_pct" in result
        assert result["bat_pct"][0][1] == pytest.approx(100.0)

    def test_bat_pct_for_repeater(self, initialized_db):
        """Computes bat_pct for repeater using 'bat' field."""
        ts = int(time.time())
        # 3000 mV = 3.0V = 0%
        insert_metrics(ts, "repeater", {"bat": 3000.0}, initialized_db)

        result = get_metrics_for_period(
            "repeater", ts - 100, ts + 100, initialized_db
        )

        assert "bat_pct" in result
        assert result["bat_pct"][0][1] == pytest.approx(0.0)

    def test_empty_period_returns_empty(self, initialized_db):
        """Empty time period returns empty dict."""
        result = get_metrics_for_period(
            "companion", 0, 1, initialized_db
        )

        assert result == {}

    def test_invalid_role_raises(self, initialized_db):
        """Invalid role raises ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_metrics_for_period("invalid", 0, 100, initialized_db)


class TestGetLatestMetrics:
    """Tests for get_latest_metrics function."""

    def test_returns_most_recent(self, initialized_db):
        """Returns metrics at most recent timestamp."""
        base_ts = int(time.time())

        insert_metrics(base_ts, "companion", {"test": 1.0}, initialized_db)
        insert_metrics(base_ts + 100, "companion", {"test": 2.0}, initialized_db)

        result = get_latest_metrics("companion", initialized_db)

        assert result["test"] == 2.0
        assert result["ts"] == base_ts + 100

    def test_includes_ts(self, initialized_db):
        """Result includes 'ts' key with timestamp."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"test": 1.0}, initialized_db)

        result = get_latest_metrics("companion", initialized_db)

        assert "ts" in result
        assert result["ts"] == ts

    def test_includes_all_metrics(self, initialized_db):
        """Result includes all metrics at that timestamp."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {
            "battery_mv": 3850.0,
            "contacts": 5,
            "uptime_secs": 86400,
        }, initialized_db)

        result = get_latest_metrics("companion", initialized_db)

        assert result["battery_mv"] == 3850.0
        assert result["contacts"] == 5.0
        assert result["uptime_secs"] == 86400.0

    def test_computes_bat_pct(self, initialized_db):
        """Computes bat_pct from battery voltage."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"battery_mv": 3820.0}, initialized_db)

        result = get_latest_metrics("companion", initialized_db)

        assert "bat_pct" in result
        assert result["bat_pct"] == pytest.approx(50.0)

    def test_returns_none_when_empty(self, initialized_db):
        """Returns None when no data exists."""
        result = get_latest_metrics("companion", initialized_db)

        assert result is None

    def test_filters_by_role(self, initialized_db):
        """Only returns data for specified role."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"test": 1.0}, initialized_db)
        insert_metrics(ts + 100, "repeater", {"test": 2.0}, initialized_db)

        result = get_latest_metrics("companion", initialized_db)

        assert result["ts"] == ts
        assert result["test"] == 1.0

    def test_invalid_role_raises(self, initialized_db):
        """Invalid role raises ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_latest_metrics("invalid", initialized_db)


class TestGetMetricCount:
    """Tests for get_metric_count function."""

    def test_counts_rows(self, initialized_db):
        """Counts total metric rows for role."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"a": 1.0, "b": 2.0, "c": 3.0}, initialized_db)

        count = get_metric_count("companion", initialized_db)

        assert count == 3

    def test_filters_by_role(self, initialized_db):
        """Only counts rows for specified role."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"a": 1.0}, initialized_db)
        insert_metrics(ts, "repeater", {"b": 2.0, "c": 3.0}, initialized_db)

        assert get_metric_count("companion", initialized_db) == 1
        assert get_metric_count("repeater", initialized_db) == 2

    def test_returns_zero_when_empty(self, initialized_db):
        """Returns 0 when no data exists."""
        count = get_metric_count("companion", initialized_db)
        assert count == 0

    def test_invalid_role_raises(self, initialized_db):
        """Invalid role raises ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_metric_count("invalid", initialized_db)


class TestGetDistinctTimestamps:
    """Tests for get_distinct_timestamps function."""

    def test_counts_unique_timestamps(self, initialized_db):
        """Counts distinct timestamps."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"a": 1.0, "b": 2.0}, initialized_db)  # 1 ts
        insert_metrics(ts + 100, "companion", {"a": 3.0}, initialized_db)  # 2nd ts

        count = get_distinct_timestamps("companion", initialized_db)

        assert count == 2

    def test_filters_by_role(self, initialized_db):
        """Only counts timestamps for specified role."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"a": 1.0}, initialized_db)
        insert_metrics(ts + 100, "companion", {"a": 2.0}, initialized_db)
        insert_metrics(ts, "repeater", {"a": 3.0}, initialized_db)

        assert get_distinct_timestamps("companion", initialized_db) == 2
        assert get_distinct_timestamps("repeater", initialized_db) == 1

    def test_returns_zero_when_empty(self, initialized_db):
        """Returns 0 when no data exists."""
        count = get_distinct_timestamps("companion", initialized_db)
        assert count == 0


class TestGetAvailableMetrics:
    """Tests for get_available_metrics function."""

    def test_returns_metric_names(self, initialized_db):
        """Returns list of distinct metric names."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {
            "battery_mv": 3850.0,
            "contacts": 5,
            "recv": 100,
        }, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)

        assert "battery_mv" in metrics
        assert "contacts" in metrics
        assert "recv" in metrics

    def test_sorted_alphabetically(self, initialized_db):
        """Metrics are sorted alphabetically."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {
            "zebra": 1.0,
            "apple": 2.0,
            "mango": 3.0,
        }, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)

        assert metrics == sorted(metrics)

    def test_filters_by_role(self, initialized_db):
        """Only returns metrics for specified role."""
        ts = int(time.time())
        insert_metrics(ts, "companion", {"companion_metric": 1.0}, initialized_db)
        insert_metrics(ts, "repeater", {"repeater_metric": 2.0}, initialized_db)

        companion_metrics = get_available_metrics("companion", initialized_db)
        repeater_metrics = get_available_metrics("repeater", initialized_db)

        assert "companion_metric" in companion_metrics
        assert "repeater_metric" not in companion_metrics
        assert "repeater_metric" in repeater_metrics

    def test_returns_empty_when_no_data(self, initialized_db):
        """Returns empty list when no data exists."""
        metrics = get_available_metrics("companion", initialized_db)
        assert metrics == []
