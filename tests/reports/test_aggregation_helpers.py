"""Tests for report aggregation helper functions."""

from datetime import date, datetime

import pytest

from meshmon.reports import (
    DailyAggregate,
    MetricStats,
    MonthlyAggregate,
    _aggregate_daily_counter_to_summary,
    _aggregate_daily_gauge_to_summary,
    _aggregate_monthly_counter_to_summary,
    _aggregate_monthly_gauge_to_summary,
    _compute_counter_stats,
    _compute_gauge_stats,
)


class TestComputeGaugeStats:
    """Tests for _compute_gauge_stats function."""

    def test_returns_metric_stats(self):
        """Returns a MetricStats dataclass."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 3.8),
            (datetime(2024, 1, 1, 1, 0), 3.9),
            (datetime(2024, 1, 1, 2, 0), 4.0),
        ]
        result = _compute_gauge_stats(values)
        assert isinstance(result, MetricStats)

    def test_computes_min_max_mean(self):
        """Computes correct min, max, and mean."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 3.8),
            (datetime(2024, 1, 1, 1, 0), 3.9),
            (datetime(2024, 1, 1, 2, 0), 4.0),
        ]
        result = _compute_gauge_stats(values)
        assert result.min_value == 3.8
        assert result.max_value == 4.0
        assert result.mean == pytest.approx(3.9)
        assert result.count == 3

    def test_handles_single_value(self):
        """Handles single value correctly."""
        values = [(datetime(2024, 1, 1, 0, 0), 3.85)]
        result = _compute_gauge_stats(values)
        assert result.min_value == 3.85
        assert result.max_value == 3.85
        assert result.mean == 3.85
        assert result.count == 1
        assert result.min_time == datetime(2024, 1, 1, 0, 0)
        assert result.max_time == datetime(2024, 1, 1, 0, 0)

    def test_handles_empty_list(self):
        """Handles empty list gracefully."""
        result = _compute_gauge_stats([])
        assert result.min_value is None
        assert result.max_value is None
        assert result.mean is None
        assert result.count == 0

    def test_tracks_count(self):
        """Tracks the number of values."""
        values = [
            (datetime(2024, 1, 1, i, 0), 3.8 + i * 0.01)
            for i in range(10)
        ]
        result = _compute_gauge_stats(values)
        assert result.count == 10

    def test_tracks_min_time(self):
        """Tracks timestamp of minimum value."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 3.9),
            (datetime(2024, 1, 1, 1, 0), 3.7),  # Min
            (datetime(2024, 1, 1, 2, 0), 3.8),
        ]
        result = _compute_gauge_stats(values)
        assert result.min_time == datetime(2024, 1, 1, 1, 0)

    def test_tracks_max_time(self):
        """Tracks timestamp of maximum value."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 3.9),
            (datetime(2024, 1, 1, 1, 0), 4.1),  # Max
            (datetime(2024, 1, 1, 2, 0), 3.8),
        ]
        result = _compute_gauge_stats(values)
        assert result.max_time == datetime(2024, 1, 1, 1, 0)


class TestComputeCounterStats:
    """Tests for _compute_counter_stats function."""

    def test_returns_metric_stats(self):
        """Returns a MetricStats dataclass."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 150),
            (datetime(2024, 1, 1, 2, 0), 200),
        ]
        result = _compute_counter_stats(values)
        assert isinstance(result, MetricStats)

    def test_computes_total_delta(self):
        """Computes total delta from counter values."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 150),  # +50
            (datetime(2024, 1, 1, 2, 0), 200),  # +50
        ]
        result = _compute_counter_stats(values)
        # Total should be 100 (50 + 50)
        assert result.total == 100
        assert result.count == 3
        assert result.reboot_count == 0

    def test_handles_counter_reboot(self):
        """Handles counter reboot (value decrease)."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 150),  # +50
            (datetime(2024, 1, 1, 2, 0), 20),   # Reboot - counts from 0
            (datetime(2024, 1, 1, 3, 0), 50),   # +30
        ]
        result = _compute_counter_stats(values)
        # Total: 50 + 20 + 30 = 100
        assert result.total == 100
        assert result.reboot_count == 1
        assert result.count == 4

    def test_tracks_reboot_count(self):
        """Tracks number of reboots."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 150),
            (datetime(2024, 1, 1, 2, 0), 20),   # Reboot 1
            (datetime(2024, 1, 1, 3, 0), 50),
            (datetime(2024, 1, 1, 4, 0), 10),   # Reboot 2
        ]
        result = _compute_counter_stats(values)
        assert result.reboot_count == 2
        assert result.total == 110
        assert result.count == 5

    def test_handles_empty_list(self):
        """Handles empty list gracefully."""
        result = _compute_counter_stats([])
        assert result.total is None
        assert result.count == 0
        assert result.reboot_count == 0

    def test_handles_single_value(self):
        """Handles single value (no delta possible)."""
        values = [(datetime(2024, 1, 1, 0, 0), 100)]
        result = _compute_counter_stats(values)
        # Single value means no delta can be computed
        assert result.total is None
        assert result.count == 1
        assert result.reboot_count == 0


class TestAggregateDailyGaugeToSummary:
    """Tests for _aggregate_daily_gauge_to_summary function."""

    @pytest.fixture
    def daily_gauge_data(self):
        """Sample daily gauge aggregates."""
        return [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "battery": MetricStats(
                        min_value=3.7, min_time=datetime(2024, 1, 1, 3, 0),
                        max_value=3.9, max_time=datetime(2024, 1, 1, 15, 0),
                        mean=3.8, count=96
                    )
                }
            ),
            DailyAggregate(
                date=date(2024, 1, 2),
                metrics={
                    "battery": MetricStats(
                        min_value=3.6, min_time=datetime(2024, 1, 2, 4, 0),
                        max_value=4.0, max_time=datetime(2024, 1, 2, 12, 0),
                        mean=3.85, count=96
                    )
                }
            ),
            DailyAggregate(
                date=date(2024, 1, 3),
                metrics={
                    "battery": MetricStats(
                        min_value=3.8, min_time=datetime(2024, 1, 3, 2, 0),
                        max_value=4.1, max_time=datetime(2024, 1, 3, 18, 0),
                        mean=3.95, count=96
                    )
                }
            ),
        ]

    def test_returns_metric_stats(self, daily_gauge_data):
        """Returns a MetricStats object."""
        result = _aggregate_daily_gauge_to_summary(daily_gauge_data, "battery")
        assert isinstance(result, MetricStats)

    def test_finds_overall_min(self, daily_gauge_data):
        """Finds minimum across all days."""
        result = _aggregate_daily_gauge_to_summary(daily_gauge_data, "battery")
        assert result.min_value == 3.6
        assert result.min_time == datetime(2024, 1, 2, 4, 0)

    def test_finds_overall_max(self, daily_gauge_data):
        """Finds maximum across all days."""
        result = _aggregate_daily_gauge_to_summary(daily_gauge_data, "battery")
        assert result.max_value == 4.1
        assert result.max_time == datetime(2024, 1, 3, 18, 0)

    def test_computes_weighted_mean(self, daily_gauge_data):
        """Computes weighted mean based on count."""
        result = _aggregate_daily_gauge_to_summary(daily_gauge_data, "battery")
        # All have same count, so simple average: (3.8 + 3.85 + 3.95) / 3 = 3.8667
        assert result.mean == pytest.approx(3.8667, rel=0.01)
        assert result.count == 288

    def test_handles_empty_list(self):
        """Handles empty daily list."""
        result = _aggregate_daily_gauge_to_summary([], "battery")
        assert result.min_value is None
        assert result.max_value is None
        assert result.mean is None
        assert result.count == 0

    def test_handles_missing_metric(self, daily_gauge_data):
        """Handles when metric doesn't exist in daily data."""
        result = _aggregate_daily_gauge_to_summary(daily_gauge_data, "nonexistent")
        assert result.min_value is None
        assert result.max_value is None
        assert result.mean is None
        assert result.count == 0


class TestAggregateDailyCounterToSummary:
    """Tests for _aggregate_daily_counter_to_summary function."""

    @pytest.fixture
    def daily_counter_data(self):
        """Sample daily counter aggregates."""
        return [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "packets_rx": MetricStats(total=1000, reboot_count=0, count=96)
                }
            ),
            DailyAggregate(
                date=date(2024, 1, 2),
                metrics={
                    "packets_rx": MetricStats(total=1500, reboot_count=1, count=96)
                }
            ),
            DailyAggregate(
                date=date(2024, 1, 3),
                metrics={
                    "packets_rx": MetricStats(total=800, reboot_count=0, count=96)
                }
            ),
        ]

    def test_returns_metric_stats(self, daily_counter_data):
        """Returns a MetricStats object."""
        result = _aggregate_daily_counter_to_summary(daily_counter_data, "packets_rx")
        assert isinstance(result, MetricStats)

    def test_sums_totals(self, daily_counter_data):
        """Sums totals across all days."""
        result = _aggregate_daily_counter_to_summary(daily_counter_data, "packets_rx")
        assert result.total == 3300  # 1000 + 1500 + 800
        assert result.count == 288

    def test_sums_reboots(self, daily_counter_data):
        """Sums reboot counts across all days."""
        result = _aggregate_daily_counter_to_summary(daily_counter_data, "packets_rx")
        assert result.reboot_count == 1

    def test_handles_empty_list(self):
        """Handles empty daily list."""
        result = _aggregate_daily_counter_to_summary([], "packets_rx")
        assert result.total is None
        assert result.count == 0
        assert result.reboot_count == 0

    def test_handles_missing_metric(self, daily_counter_data):
        """Handles when metric doesn't exist in daily data."""
        result = _aggregate_daily_counter_to_summary(daily_counter_data, "nonexistent")
        assert result.total is None
        assert result.count == 0
        assert result.reboot_count == 0


class TestAggregateMonthlyGaugeToSummary:
    """Tests for _aggregate_monthly_gauge_to_summary function."""

    @pytest.fixture
    def monthly_gauge_data(self):
        """Sample monthly gauge aggregates."""
        return [
            MonthlyAggregate(
                year=2024,
                month=1,
                role="companion",
                summary={
                    "battery": MetricStats(
                        min_value=3.6, min_time=datetime(2024, 1, 15, 4, 0),
                        max_value=4.0, max_time=datetime(2024, 1, 20, 14, 0),
                        mean=3.8, count=2976
                    )
                }
            ),
            MonthlyAggregate(
                year=2024,
                month=2,
                role="companion",
                summary={
                    "battery": MetricStats(
                        min_value=3.5, min_time=datetime(2024, 2, 10, 5, 0),
                        max_value=4.1, max_time=datetime(2024, 2, 25, 16, 0),
                        mean=3.9, count=2784
                    )
                }
            ),
        ]

    def test_returns_metric_stats(self, monthly_gauge_data):
        """Returns a MetricStats object."""
        result = _aggregate_monthly_gauge_to_summary(monthly_gauge_data, "battery")
        assert isinstance(result, MetricStats)

    def test_finds_overall_min(self, monthly_gauge_data):
        """Finds minimum across all months."""
        result = _aggregate_monthly_gauge_to_summary(monthly_gauge_data, "battery")
        assert result.min_value == 3.5
        assert result.min_time == datetime(2024, 2, 10, 5, 0)

    def test_finds_overall_max(self, monthly_gauge_data):
        """Finds maximum across all months."""
        result = _aggregate_monthly_gauge_to_summary(monthly_gauge_data, "battery")
        assert result.max_value == 4.1
        assert result.max_time == datetime(2024, 2, 25, 16, 0)

    def test_computes_weighted_mean(self, monthly_gauge_data):
        """Computes weighted mean based on count."""
        result = _aggregate_monthly_gauge_to_summary(monthly_gauge_data, "battery")
        # Weighted: (3.8 * 2976 + 3.9 * 2784) / (2976 + 2784)
        expected = (3.8 * 2976 + 3.9 * 2784) / (2976 + 2784)
        assert result.mean == pytest.approx(expected, rel=0.01)
        assert result.count == 5760

    def test_handles_empty_list(self):
        """Handles empty monthly list."""
        result = _aggregate_monthly_gauge_to_summary([], "battery")
        assert result.min_value is None
        assert result.max_value is None
        assert result.mean is None
        assert result.count == 0


class TestAggregateMonthlyCounterToSummary:
    """Tests for _aggregate_monthly_counter_to_summary function."""

    @pytest.fixture
    def monthly_counter_data(self):
        """Sample monthly counter aggregates."""
        return [
            MonthlyAggregate(
                year=2024,
                month=1,
                role="companion",
                summary={
                    "packets_rx": MetricStats(total=50000, reboot_count=2, count=2976)
                }
            ),
            MonthlyAggregate(
                year=2024,
                month=2,
                role="companion",
                summary={
                    "packets_rx": MetricStats(total=45000, reboot_count=1, count=2784)
                }
            ),
        ]

    def test_returns_metric_stats(self, monthly_counter_data):
        """Returns a MetricStats object."""
        result = _aggregate_monthly_counter_to_summary(monthly_counter_data, "packets_rx")
        assert isinstance(result, MetricStats)

    def test_sums_totals(self, monthly_counter_data):
        """Sums totals across all months."""
        result = _aggregate_monthly_counter_to_summary(monthly_counter_data, "packets_rx")
        assert result.total == 95000
        assert result.count == 5760

    def test_sums_reboots(self, monthly_counter_data):
        """Sums reboot counts across all months."""
        result = _aggregate_monthly_counter_to_summary(monthly_counter_data, "packets_rx")
        assert result.reboot_count == 3

    def test_handles_empty_list(self):
        """Handles empty monthly list."""
        result = _aggregate_monthly_counter_to_summary([], "packets_rx")
        assert result.total is None
        assert result.count == 0
        assert result.reboot_count == 0

    def test_handles_missing_metric(self, monthly_counter_data):
        """Handles when metric doesn't exist in monthly data."""
        result = _aggregate_monthly_counter_to_summary(monthly_counter_data, "nonexistent")
        assert result.total is None
        assert result.count == 0
        assert result.reboot_count == 0
