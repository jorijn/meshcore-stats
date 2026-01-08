"""Tests for chart statistics calculation."""

from datetime import datetime, timedelta

import pytest

from meshmon.charts import (
    ChartStatistics,
    DataPoint,
    TimeSeries,
    calculate_statistics,
)

BASE_TIME = datetime(2024, 1, 1, 0, 0, 0)


class TestCalculateStatistics:
    """Tests for calculate_statistics function."""

    def test_calculates_min(self, sample_timeseries):
        """Calculates minimum value."""
        stats = calculate_statistics(sample_timeseries)

        assert stats.min_value is not None
        assert stats.min_value == min(p.value for p in sample_timeseries.points)

    def test_calculates_max(self, sample_timeseries):
        """Calculates maximum value."""
        stats = calculate_statistics(sample_timeseries)

        assert stats.max_value is not None
        assert stats.max_value == max(p.value for p in sample_timeseries.points)

    def test_calculates_avg(self, sample_timeseries):
        """Calculates average value."""
        stats = calculate_statistics(sample_timeseries)

        expected_avg = sum(p.value for p in sample_timeseries.points) / len(sample_timeseries.points)
        assert stats.avg_value is not None
        assert stats.avg_value == pytest.approx(expected_avg)

    def test_calculates_current(self, sample_timeseries):
        """Current is the last value."""
        stats = calculate_statistics(sample_timeseries)

        assert stats.current_value is not None
        assert stats.current_value == sample_timeseries.points[-1].value

    def test_empty_series_returns_none_values(self, empty_timeseries):
        """Empty time series returns None for all stats."""
        stats = calculate_statistics(empty_timeseries)

        assert stats.min_value is None
        assert stats.avg_value is None
        assert stats.max_value is None
        assert stats.current_value is None

    def test_single_point_stats(self, single_point_timeseries):
        """Single point: min=avg=max=current."""
        stats = calculate_statistics(single_point_timeseries)
        value = single_point_timeseries.points[0].value

        assert stats.min_value == value
        assert stats.avg_value == value
        assert stats.max_value == value
        assert stats.current_value == value


class TestChartStatistics:
    """Tests for ChartStatistics dataclass."""

    def test_to_dict(self):
        """Converts to dict with correct keys."""
        stats = ChartStatistics(
            min_value=3.0,
            avg_value=3.5,
            max_value=4.0,
            current_value=3.8,
        )

        d = stats.to_dict()

        assert d == {
            "min": 3.0,
            "avg": 3.5,
            "max": 4.0,
            "current": 3.8,
        }

    def test_to_dict_with_none_values(self):
        """None values preserved in dict."""
        stats = ChartStatistics()

        d = stats.to_dict()

        assert d == {
            "min": None,
            "avg": None,
            "max": None,
            "current": None,
        }

    def test_default_values_are_none(self):
        """Default values are all None."""
        stats = ChartStatistics()

        assert stats.min_value is None
        assert stats.avg_value is None
        assert stats.max_value is None
        assert stats.current_value is None


class TestStatisticsWithVariousData:
    """Tests for statistics with various data patterns."""

    def test_constant_values(self):
        """All same values gives min=avg=max."""
        now = BASE_TIME
        points = [DataPoint(timestamp=now + timedelta(hours=i), value=5.0) for i in range(10)]
        ts = TimeSeries(metric="test", role="companion", period="day", points=points)

        stats = calculate_statistics(ts)

        assert stats.min_value == 5.0
        assert stats.avg_value == 5.0
        assert stats.max_value == 5.0

    def test_increasing_values(self):
        """Increasing values have correct stats."""
        now = BASE_TIME
        points = [DataPoint(timestamp=now + timedelta(hours=i), value=float(i)) for i in range(10)]
        ts = TimeSeries(metric="test", role="companion", period="day", points=points)

        stats = calculate_statistics(ts)

        assert stats.min_value == 0.0
        assert stats.max_value == 9.0
        assert stats.avg_value == 4.5  # Mean of 0-9
        assert stats.current_value == 9.0  # Last value

    def test_negative_values(self):
        """Handles negative values correctly."""
        now = BASE_TIME
        points = [
            DataPoint(timestamp=now, value=-10.0),
            DataPoint(timestamp=now + timedelta(hours=1), value=-5.0),
            DataPoint(timestamp=now + timedelta(hours=2), value=0.0),
        ]
        ts = TimeSeries(metric="test", role="companion", period="day", points=points)

        stats = calculate_statistics(ts)

        assert stats.min_value == -10.0
        assert stats.max_value == 0.0
        assert stats.avg_value == -5.0

    def test_large_values(self):
        """Handles large values correctly."""
        now = BASE_TIME
        points = [
            DataPoint(timestamp=now, value=1e10),
            DataPoint(timestamp=now + timedelta(hours=1), value=1e11),
        ]
        ts = TimeSeries(metric="test", role="companion", period="day", points=points)

        stats = calculate_statistics(ts)

        assert stats.min_value == 1e10
        assert stats.max_value == 1e11

    def test_small_decimal_values(self):
        """Handles small decimal values correctly."""
        now = BASE_TIME
        points = [
            DataPoint(timestamp=now, value=0.001),
            DataPoint(timestamp=now + timedelta(hours=1), value=0.002),
            DataPoint(timestamp=now + timedelta(hours=2), value=0.003),
        ]
        ts = TimeSeries(metric="test", role="companion", period="day", points=points)

        stats = calculate_statistics(ts)

        assert stats.min_value == pytest.approx(0.001)
        assert stats.max_value == pytest.approx(0.003)
        assert stats.avg_value == pytest.approx(0.002)
