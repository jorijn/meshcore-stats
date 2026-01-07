"""Tests for TimeSeries data class and loading."""

import pytest
from datetime import datetime, timedelta

from meshmon.charts import (
    DataPoint,
    TimeSeries,
    load_timeseries_from_db,
)
from meshmon.db import insert_metrics


class TestDataPoint:
    """Tests for DataPoint dataclass."""

    def test_stores_timestamp_and_value(self):
        """Stores timestamp and value."""
        ts = datetime.now()
        dp = DataPoint(timestamp=ts, value=3.85)

        assert dp.timestamp == ts
        assert dp.value == 3.85

    def test_value_types(self):
        """Accepts float and int values."""
        ts = datetime.now()

        dp_float = DataPoint(timestamp=ts, value=3.85)
        assert dp_float.value == 3.85

        dp_int = DataPoint(timestamp=ts, value=100.0)
        assert dp_int.value == 100.0


class TestTimeSeries:
    """Tests for TimeSeries dataclass."""

    def test_stores_metadata(self):
        """Stores metric, role, period metadata."""
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
        )

        assert ts.metric == "bat"
        assert ts.role == "repeater"
        assert ts.period == "day"

    def test_empty_by_default(self):
        """Points list is empty by default."""
        ts = TimeSeries(metric="bat", role="repeater", period="day")

        assert ts.points == []
        assert ts.is_empty is True

    def test_timestamps_property(self, sample_timeseries):
        """timestamps property returns list of timestamps."""
        timestamps = sample_timeseries.timestamps

        assert len(timestamps) == len(sample_timeseries.points)
        assert all(isinstance(t, datetime) for t in timestamps)

    def test_values_property(self, sample_timeseries):
        """values property returns list of values."""
        values = sample_timeseries.values

        assert len(values) == len(sample_timeseries.points)
        assert all(isinstance(v, float) for v in values)

    def test_is_empty_false_with_data(self, sample_timeseries):
        """is_empty is False when points exist."""
        assert sample_timeseries.is_empty is False

    def test_is_empty_true_without_data(self, empty_timeseries):
        """is_empty is True when no points."""
        assert empty_timeseries.is_empty is True


class TestLoadTimeseriesFromDb:
    """Tests for load_timeseries_from_db function."""

    def test_loads_metric_data(self, initialized_db, configured_env):
        """Loads metric data from database."""
        base_ts = 1704067200
        insert_metrics(base_ts, "repeater", {"bat": 3850.0}, initialized_db)
        insert_metrics(base_ts + 900, "repeater", {"bat": 3860.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=datetime.fromtimestamp(base_ts + 1000),
            lookback=timedelta(hours=1),
            period="day",
        )

        assert len(ts.points) == 2

    def test_filters_by_time_range(self, initialized_db, configured_env):
        """Only loads data within time range."""
        base_ts = 1704067200

        # Insert data outside and inside range
        insert_metrics(base_ts - 7200, "repeater", {"bat": 3800.0}, initialized_db)  # Outside
        insert_metrics(base_ts, "repeater", {"bat": 3850.0}, initialized_db)  # Inside
        insert_metrics(base_ts + 7200, "repeater", {"bat": 3900.0}, initialized_db)  # Outside

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=datetime.fromtimestamp(base_ts + 1800),
            lookback=timedelta(hours=1),
            period="day",
        )

        assert len(ts.points) == 1
        assert ts.points[0].value == pytest.approx(3.85)  # Transformed to volts

    def test_returns_correct_metadata(self, initialized_db, configured_env):
        """Returned TimeSeries has correct metadata."""
        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=datetime.now(),
            lookback=timedelta(hours=1),
            period="week",
        )

        assert ts.metric == "bat"
        assert ts.role == "repeater"
        assert ts.period == "week"

    def test_uses_prefetched_metrics(self, initialized_db, configured_env):
        """Can use pre-fetched metrics dict."""
        base_ts = 1704067200
        insert_metrics(base_ts, "repeater", {"bat": 3850.0}, initialized_db)

        # Pre-fetch metrics
        from meshmon.db import get_metrics_for_period
        all_metrics = get_metrics_for_period("repeater", base_ts - 3600, base_ts + 3600)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=datetime.fromtimestamp(base_ts + 3600),
            lookback=timedelta(hours=2),
            period="day",
            all_metrics=all_metrics,
        )

        assert len(ts.points) == 1

    def test_handles_missing_metric(self, initialized_db, configured_env):
        """Returns empty TimeSeries for missing metric."""
        ts = load_timeseries_from_db(
            role="repeater",
            metric="nonexistent_metric",
            end_time=datetime.now(),
            lookback=timedelta(hours=1),
            period="day",
        )

        assert ts.is_empty

    def test_sorts_by_timestamp(self, initialized_db, configured_env):
        """Points are sorted by timestamp."""
        base_ts = 1704067200

        # Insert out of order
        insert_metrics(base_ts + 300, "repeater", {"bat": 3860.0}, initialized_db)
        insert_metrics(base_ts, "repeater", {"bat": 3850.0}, initialized_db)
        insert_metrics(base_ts + 150, "repeater", {"bat": 3855.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=datetime.fromtimestamp(base_ts + 600),
            lookback=timedelta(hours=1),
            period="day",
        )

        timestamps = [p.timestamp for p in ts.points]
        assert timestamps == sorted(timestamps)
