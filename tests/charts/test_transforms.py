"""Tests for chart data transformations (counter-to-rate, etc.)."""

from datetime import datetime, timedelta

import pytest

from meshmon.charts import (
    PERIOD_CONFIG,
    load_timeseries_from_db,
)
from meshmon.db import insert_metrics

BASE_TIME = datetime(2024, 1, 1, 0, 0, 0)


class TestCounterToRateConversion:
    """Tests for counter metric rate conversion."""

    def test_calculates_rate_from_deltas(self, initialized_db, configured_env):
        """Counter values are converted to rate of change."""
        base_ts = 1704067200  # 2024-01-01 00:00:00 UTC

        # Insert increasing counter values (15 min apart)
        for i in range(5):
            ts = base_ts + (i * 900)  # 15 minutes
            insert_metrics(ts, "repeater", {"nb_recv": float(i * 100)}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="nb_recv",
            end_time=datetime.fromtimestamp(base_ts + 4 * 900),
            lookback=timedelta(hours=2),
            period="day",
        )

        # Counter produces N-1 rate points from N values
        assert len(ts.points) == 4

        # All rates should be positive (counter increasing)
        expected_rate = (100.0 / 900.0) * 60.0
        for p in ts.points:
            assert p.value == pytest.approx(expected_rate)

    def test_handles_counter_reset(self, initialized_db, configured_env):
        """Counter resets (negative delta) are skipped."""
        base_ts = 1704067200

        # Insert values with a reset
        insert_metrics(base_ts, "repeater", {"nb_recv": 100.0}, initialized_db)
        insert_metrics(base_ts + 900, "repeater", {"nb_recv": 200.0}, initialized_db)
        insert_metrics(base_ts + 1800, "repeater", {"nb_recv": 50.0}, initialized_db)  # Reset!
        insert_metrics(base_ts + 2700, "repeater", {"nb_recv": 150.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="nb_recv",
            end_time=datetime.fromtimestamp(base_ts + 2700),
            lookback=timedelta(hours=1),
            period="day",
        )

        # Reset point should be skipped, so fewer points
        assert len(ts.points) == 2  # Only valid deltas
        expected_rate = (100.0 / 900.0) * 60.0
        assert ts.points[0].timestamp == datetime.fromtimestamp(base_ts + 900)
        assert ts.points[1].timestamp == datetime.fromtimestamp(base_ts + 2700)
        assert ts.points[0].value == pytest.approx(expected_rate)
        assert ts.points[1].value == pytest.approx(expected_rate)

    def test_counter_rate_short_interval_under_step_is_skipped(
        self,
        initialized_db,
        configured_env,
        monkeypatch,
    ):
        """Short sampling intervals are skipped to avoid rate spikes."""
        base_ts = 1704067200

        monkeypatch.setenv("REPEATER_STEP", "900")
        import meshmon.env

        meshmon.env._config = None

        insert_metrics(base_ts, "repeater", {"nb_recv": 0.0}, initialized_db)
        insert_metrics(base_ts + 900, "repeater", {"nb_recv": 100.0}, initialized_db)
        insert_metrics(base_ts + 904, "repeater", {"nb_recv": 110.0}, initialized_db)
        insert_metrics(base_ts + 1800, "repeater", {"nb_recv": 200.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="nb_recv",
            end_time=datetime.fromtimestamp(base_ts + 1800),
            lookback=timedelta(hours=2),
            period="day",
        )

        expected_rate = (100.0 / 900.0) * 60.0
        assert len(ts.points) == 2
        assert ts.points[0].timestamp == datetime.fromtimestamp(base_ts + 900)
        assert ts.points[1].timestamp == datetime.fromtimestamp(base_ts + 1800)
        for point in ts.points:
            assert point.value == pytest.approx(expected_rate)

    def test_applies_scale_factor(self, initialized_db, configured_env, monkeypatch):
        """Counter rate is scaled (typically x60 for per-minute)."""
        base_ts = 1704067200

        monkeypatch.setenv("REPEATER_STEP", "60")
        import meshmon.env

        meshmon.env._config = None

        # Insert values 60 seconds apart for easy math
        insert_metrics(base_ts, "repeater", {"nb_recv": 0.0}, initialized_db)
        insert_metrics(base_ts + 60, "repeater", {"nb_recv": 60.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="nb_recv",
            end_time=datetime.fromtimestamp(base_ts + 60),
            lookback=timedelta(hours=1),
            period="day",
        )

        # 60 packets in 60 seconds = 1/sec = 60/min with scale=60
        assert len(ts.points) == 1
        assert ts.points[0].value == pytest.approx(60.0)

    def test_single_value_returns_empty(self, initialized_db, configured_env):
        """Single counter value cannot compute rate."""
        base_ts = 1704067200
        insert_metrics(base_ts, "repeater", {"nb_recv": 100.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="nb_recv",
            end_time=datetime.fromtimestamp(base_ts),
            lookback=timedelta(hours=1),
            period="day",
        )

        assert ts.is_empty


class TestGaugeValueTransform:
    """Tests for gauge metric value transformation."""

    def test_applies_voltage_transform(self, initialized_db, configured_env):
        """Voltage transform converts mV to V."""
        base_ts = 1704067200

        # Insert millivolt value
        insert_metrics(base_ts, "companion", {"battery_mv": 3850.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="companion",
            metric="battery_mv",
            end_time=datetime.fromtimestamp(base_ts),
            lookback=timedelta(hours=1),
            period="day",
        )

        # Should be converted to volts
        assert len(ts.points) == 1
        assert ts.points[0].value == pytest.approx(3.85)

    def test_no_transform_for_bat_pct(self, initialized_db, configured_env):
        """Battery percentage has no transform."""
        base_ts = 1704067200
        insert_metrics(base_ts, "repeater", {"bat_pct": 75.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat_pct",
            end_time=datetime.fromtimestamp(base_ts),
            lookback=timedelta(hours=1),
            period="day",
        )

        assert ts.points[0].value == pytest.approx(75.0)


class TestTimeBinning:
    """Tests for time series aggregation/binning."""

    def test_no_binning_for_day(self):
        """Day period uses raw data (no binning)."""
        assert PERIOD_CONFIG["day"].bin_seconds is None

    def test_30_min_bins_for_week(self):
        """Week period uses 30-minute bins."""
        assert PERIOD_CONFIG["week"].bin_seconds == 1800

    def test_2_hour_bins_for_month(self):
        """Month period uses 2-hour bins."""
        assert PERIOD_CONFIG["month"].bin_seconds == 7200

    def test_1_day_bins_for_year(self):
        """Year period uses 1-day bins."""
        assert PERIOD_CONFIG["year"].bin_seconds == 86400

    def test_binning_reduces_point_count(self, initialized_db, configured_env):
        """Binning aggregates multiple points per bin."""
        base_ts = 1704067200

        # Insert many points (one per minute for an hour)
        for i in range(60):
            ts = base_ts + (i * 60)
            insert_metrics(ts, "repeater", {"bat": 3850.0 + i}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=datetime.fromtimestamp(base_ts + 3600),
            lookback=timedelta(days=7),  # Week period has 30-min bins
            period="week",
        )

        # 60 points over 1 hour with 30-min bins = 2-3 bins
        assert len(ts.points) <= 3


class TestEmptyData:
    """Tests for handling empty/missing data."""

    def test_empty_when_no_metric_data(self, initialized_db, configured_env):
        """Returns empty TimeSeries when metric has no data."""
        ts = load_timeseries_from_db(
            role="repeater",
            metric="nonexistent",
            end_time=BASE_TIME,
            lookback=timedelta(days=1),
            period="day",
        )

        assert ts.is_empty
        assert ts.metric == "nonexistent"
        assert ts.role == "repeater"
        assert ts.period == "day"

    def test_empty_when_no_data_in_range(self, initialized_db, configured_env):
        """Returns empty TimeSeries when no data in time range."""
        old_ts = 1000000  # Very old timestamp
        insert_metrics(old_ts, "repeater", {"bat": 3850.0}, initialized_db)

        ts = load_timeseries_from_db(
            role="repeater",
            metric="bat",
            end_time=BASE_TIME,
            lookback=timedelta(hours=1),
            period="day",
        )

        assert ts.is_empty
