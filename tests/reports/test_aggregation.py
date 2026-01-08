"""Tests for report data aggregation functions."""

from datetime import date, datetime

import pytest

from meshmon.db import insert_metrics
from meshmon.reports import (
    DailyAggregate,
    aggregate_daily,
    aggregate_monthly,
    aggregate_yearly,
    get_rows_for_date,
)

BASE_DATE = date(2024, 1, 15)
BASE_TS = int(datetime(2024, 1, 15, 0, 0, 0).timestamp())


class TestGetRowsForDate:
    """Tests for get_rows_for_date function."""

    def test_returns_list(self, initialized_db, configured_env):
        """Returns a list."""
        result = get_rows_for_date("repeater", BASE_DATE)
        assert isinstance(result, list)

    def test_filters_by_date(self, initialized_db, configured_env):
        """Only returns rows for the specified date."""
        # Insert data for different dates
        ts_jan14 = int(datetime(2024, 1, 14, 12, 0, 0).timestamp())
        ts_jan15 = int(datetime(2024, 1, 15, 12, 0, 0).timestamp())
        ts_jan16 = int(datetime(2024, 1, 16, 12, 0, 0).timestamp())

        insert_metrics(ts_jan14, "repeater", {"bat": 3800.0})
        insert_metrics(ts_jan15, "repeater", {"bat": 3850.0})
        insert_metrics(ts_jan16, "repeater", {"bat": 3900.0})

        result = get_rows_for_date("repeater", BASE_DATE)

        # Should have data for Jan 15 only
        assert len(result) == 1
        assert result[0]["ts"] == ts_jan15
        assert result[0]["bat"] == 3850.0

    def test_filters_by_role(self, initialized_db, configured_env):
        """Only returns rows for the specified role."""
        ts = int(datetime(2024, 1, 15, 12, 0, 0).timestamp())

        insert_metrics(ts, "repeater", {"bat": 3800.0})
        insert_metrics(ts, "companion", {"battery_mv": 3850.0})

        repeater_result = get_rows_for_date("repeater", BASE_DATE)
        companion_result = get_rows_for_date("companion", BASE_DATE)

        assert len(repeater_result) == 1
        assert "bat" in repeater_result[0]
        assert "battery_mv" not in repeater_result[0]
        assert len(companion_result) == 1
        assert "battery_mv" in companion_result[0]
        assert "bat" not in companion_result[0]

    def test_returns_empty_for_no_data(self, initialized_db, configured_env):
        """Returns empty list when no data for date."""
        result = get_rows_for_date("repeater", BASE_DATE)
        assert result == []


class TestAggregateDaily:
    """Tests for aggregate_daily function."""

    def test_returns_daily_aggregate(self, initialized_db, configured_env):
        """Returns a DailyAggregate."""
        result = aggregate_daily("repeater", BASE_DATE)
        assert isinstance(result, DailyAggregate)

    def test_calculates_gauge_stats(self, initialized_db, configured_env):
        """Calculates stats for gauge metrics."""
        # Insert several values
        for i, value in enumerate([3700.0, 3800.0, 3900.0, 4000.0]):
            insert_metrics(BASE_TS + i * 3600, "repeater", {"bat": value})

        result = aggregate_daily("repeater", BASE_DATE)

        assert "bat" in result.metrics
        bat_stats = result.metrics["bat"]
        assert bat_stats.count == 4
        assert bat_stats.min_value == 3700.0
        assert bat_stats.max_value == 4000.0
        assert bat_stats.mean == pytest.approx(3850.0)
        assert bat_stats.min_time == datetime.fromtimestamp(BASE_TS)
        assert bat_stats.max_time == datetime.fromtimestamp(BASE_TS + 3 * 3600)

    def test_calculates_counter_total(self, initialized_db, configured_env):
        """Calculates total for counter metrics."""
        # Insert increasing counter values
        for i in range(5):
            insert_metrics(BASE_TS + i * 900, "repeater", {"nb_recv": float(i * 100)})

        result = aggregate_daily("repeater", BASE_DATE)

        assert "nb_recv" in result.metrics
        counter_stats = result.metrics["nb_recv"]
        assert counter_stats.count == 5
        assert counter_stats.reboot_count == 0
        assert counter_stats.total == 400

    def test_returns_empty_for_no_data(self, initialized_db, configured_env):
        """Returns aggregate with empty metrics when no data."""
        result = aggregate_daily("repeater", BASE_DATE)

        assert isinstance(result, DailyAggregate)
        assert result.snapshot_count == 0
        assert result.metrics == {}


class TestAggregateMonthly:
    """Tests for aggregate_monthly function."""

    def test_returns_monthly_aggregate(self, initialized_db, configured_env):
        """Returns a MonthlyAggregate."""
        from meshmon.reports import MonthlyAggregate

        result = aggregate_monthly("repeater", 2024, 1)
        assert isinstance(result, MonthlyAggregate)

    def test_aggregates_all_days(self, initialized_db, configured_env):
        """Aggregates data from all days in month."""
        # Insert data for multiple days
        for day in [1, 5, 15, 20, 31]:
            ts = int(datetime(2024, 1, day, 12, 0, 0).timestamp())
            insert_metrics(ts, "repeater", {"bat": 3800.0 + day * 10})

        result = aggregate_monthly("repeater", 2024, 1)

        # Should have daily data
        assert result.year == 2024
        assert result.month == 1
        assert len(result.daily) == 5
        assert all(d.snapshot_count == 1 for d in result.daily)
        summary = result.summary["bat"]
        assert summary.count == 5
        assert summary.min_value == 3810.0
        assert summary.max_value == 4110.0
        assert summary.mean == pytest.approx(3944.0)
        assert summary.min_time.day == 1
        assert summary.max_time.day == 31

    def test_handles_partial_month(self, initialized_db, configured_env):
        """Handles months with partial data."""
        # Insert data for only a few days
        for day in [10, 11, 12]:
            ts = int(datetime(2024, 1, day, 12, 0, 0).timestamp())
            insert_metrics(ts, "repeater", {"bat": 3800.0})

        result = aggregate_monthly("repeater", 2024, 1)

        assert result.year == 2024
        assert result.month == 1
        assert len(result.daily) == 3
        summary = result.summary["bat"]
        assert summary.count == 3
        assert summary.mean == pytest.approx(3800.0)


class TestAggregateYearly:
    """Tests for aggregate_yearly function."""

    def test_returns_yearly_aggregate(self, initialized_db, configured_env):
        """Returns a YearlyAggregate."""
        from meshmon.reports import YearlyAggregate

        result = aggregate_yearly("repeater", 2024)
        assert isinstance(result, YearlyAggregate)

    def test_aggregates_all_months(self, initialized_db, configured_env):
        """Aggregates data from all months in year."""
        # Insert data for multiple months
        for month in [1, 3, 6, 12]:
            ts = int(datetime(2024, month, 15, 12, 0, 0).timestamp())
            insert_metrics(ts, "repeater", {"bat": 3800.0 + month * 10})

        result = aggregate_yearly("repeater", 2024)

        assert result.year == 2024
        # Should have monthly aggregates
        assert len(result.monthly) == 4
        summary = result.summary["bat"]
        assert summary.count == 4
        assert summary.min_value == 3810.0
        assert summary.max_value == 3920.0
        assert summary.mean == pytest.approx(3855.0)
        assert summary.min_time.month == 1
        assert summary.max_time.month == 12

    def test_returns_empty_for_no_data(self, initialized_db, configured_env):
        """Returns aggregate with empty monthly when no data."""
        result = aggregate_yearly("repeater", 2024)

        assert result.year == 2024
        # Empty year may have no monthly data
        assert result.monthly == []

    def test_handles_leap_year(self, initialized_db, configured_env):
        """Correctly handles leap years."""
        # Insert data for Feb 29 (2024 is a leap year)
        ts = int(datetime(2024, 2, 29, 12, 0, 0).timestamp())
        insert_metrics(ts, "repeater", {"bat": 3800.0})

        result = aggregate_yearly("repeater", 2024)

        assert result.year == 2024
        months = [monthly.month for monthly in result.monthly]
        assert 2 in months
        assert result.summary["bat"].count == 1
