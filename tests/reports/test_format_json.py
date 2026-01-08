"""Tests for JSON report formatting."""

import json
from datetime import date, datetime

import pytest

from meshmon.reports import (
    DailyAggregate,
    MetricStats,
    MonthlyAggregate,
    YearlyAggregate,
    monthly_to_json,
    yearly_to_json,
)


class TestMonthlyToJson:
    """Tests for monthly_to_json function."""

    @pytest.fixture
    def sample_monthly_aggregate(self):
        """Create sample MonthlyAggregate for testing."""
        daily_data = [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "bat": MetricStats(min_value=3.7, max_value=3.9, mean=3.8, count=24),
                    "nb_recv": MetricStats(total=720, count=24),
                },
            ),
            DailyAggregate(
                date=date(2024, 1, 2),
                metrics={
                    "bat": MetricStats(min_value=3.6, max_value=3.85, mean=3.75, count=24),
                    "nb_recv": MetricStats(total=840, count=24),
                },
            ),
        ]

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=daily_data,
            summary={
                "bat": MetricStats(
                    min_value=3.6,
                    min_time=datetime(2024, 1, 2, 1, 0),
                    max_value=3.9,
                    max_time=datetime(2024, 1, 1, 23, 0),
                    mean=3.775,
                    count=48,
                ),
                "nb_recv": MetricStats(total=1560, count=48, reboot_count=1),
            },
        )

    def test_returns_dict(self, sample_monthly_aggregate):
        """Returns a dictionary."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert isinstance(result, dict)

    def test_includes_report_type(self, sample_monthly_aggregate):
        """Includes report_type field."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert result["report_type"] == "monthly"

    def test_includes_year_and_month(self, sample_monthly_aggregate):
        """Includes year and month."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert result["year"] == 2024
        assert result["month"] == 1

    def test_includes_role(self, sample_monthly_aggregate):
        """Includes role identifier."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert result["role"] == "repeater"

    def test_includes_daily_data(self, sample_monthly_aggregate):
        """Includes daily breakdown."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert "daily" in result
        assert len(result["daily"]) == 2
        assert result["days_with_data"] == 2

    def test_daily_data_has_date(self, sample_monthly_aggregate):
        """Daily data includes date."""
        result = monthly_to_json(sample_monthly_aggregate)
        first_day = result["daily"][0]
        assert "date" in first_day
        assert first_day["date"] == "2024-01-01"

    def test_daily_metrics_include_units_and_values(self, sample_monthly_aggregate):
        """Daily metrics include units and expected values."""
        result = monthly_to_json(sample_monthly_aggregate)
        first_day = result["daily"][0]

        bat_stats = first_day["metrics"]["bat"]
        assert bat_stats["unit"] == "mV"
        assert bat_stats["min"] == 3.7
        assert bat_stats["max"] == 3.9
        assert bat_stats["mean"] == 3.8
        assert bat_stats["count"] == 24

        rx_stats = first_day["metrics"]["nb_recv"]
        assert rx_stats["unit"] == "packets"
        assert rx_stats["total"] == 720
        assert rx_stats["count"] == 24

    def test_is_json_serializable(self, sample_monthly_aggregate):
        """Result is JSON serializable."""
        result = monthly_to_json(sample_monthly_aggregate)
        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_summary_includes_times_and_reboots(self, sample_monthly_aggregate):
        """Summary includes time fields and reboot counts when provided."""
        result = monthly_to_json(sample_monthly_aggregate)
        summary = result["summary"]

        assert summary["bat"]["min_time"] == "2024-01-02T01:00:00"
        assert summary["bat"]["max_time"] == "2024-01-01T23:00:00"
        assert summary["nb_recv"]["total"] == 1560
        assert summary["nb_recv"]["reboot_count"] == 1

    def test_handles_empty_daily(self):
        """Handles aggregate with no daily data."""
        agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[],
            summary={},
        )

        result = monthly_to_json(agg)
        assert result["daily"] == []
        assert result["days_with_data"] == 0
        assert result["summary"] == {}


class TestYearlyToJson:
    """Tests for yearly_to_json function."""

    @pytest.fixture
    def sample_yearly_aggregate(self):
        """Create sample YearlyAggregate for testing."""
        monthly_data = [
            MonthlyAggregate(
                year=2024,
                month=1,
                role="repeater",
                daily=[],
                summary={"bat": MetricStats(min_value=3.6, max_value=3.9, mean=3.75, count=720)},
            ),
            MonthlyAggregate(
                year=2024,
                month=2,
                role="repeater",
                daily=[],
                summary={"bat": MetricStats(min_value=3.5, max_value=3.85, mean=3.7, count=672)},
            ),
        ]

        return YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=monthly_data,
            summary={"bat": MetricStats(min_value=3.5, max_value=3.9, mean=3.725, count=1392)},
        )

    def test_returns_dict(self, sample_yearly_aggregate):
        """Returns a dictionary."""
        result = yearly_to_json(sample_yearly_aggregate)
        assert isinstance(result, dict)

    def test_includes_report_type(self, sample_yearly_aggregate):
        """Includes report_type field."""
        result = yearly_to_json(sample_yearly_aggregate)
        assert result["report_type"] == "yearly"

    def test_includes_year(self, sample_yearly_aggregate):
        """Includes year."""
        result = yearly_to_json(sample_yearly_aggregate)
        assert result["year"] == 2024

    def test_includes_role(self, sample_yearly_aggregate):
        """Includes role identifier."""
        result = yearly_to_json(sample_yearly_aggregate)
        assert result["role"] == "repeater"

    def test_includes_monthly_data(self, sample_yearly_aggregate):
        """Includes monthly breakdown."""
        result = yearly_to_json(sample_yearly_aggregate)
        assert "monthly" in result
        assert len(result["monthly"]) == 2
        assert result["months_with_data"] == 2

    def test_is_json_serializable(self, sample_yearly_aggregate):
        """Result is JSON serializable."""
        result = yearly_to_json(sample_yearly_aggregate)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_summary_and_monthly_entries(self, sample_yearly_aggregate):
        """Summary and monthly entries include expected fields."""
        result = yearly_to_json(sample_yearly_aggregate)

        assert result["summary"]["bat"]["count"] == 1392
        assert result["summary"]["bat"]["unit"] == "mV"

        first_month = result["monthly"][0]
        assert first_month["year"] == 2024
        assert first_month["month"] == 1
        assert first_month["days_with_data"] == 0
        assert first_month["summary"]["bat"]["mean"] == 3.75

    def test_handles_empty_monthly(self):
        """Handles aggregate with no monthly data."""
        agg = YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=[],
            summary={},
        )

        result = yearly_to_json(agg)
        assert result["monthly"] == []
        assert result["months_with_data"] == 0
        assert result["summary"] == {}


class TestJsonStructure:
    """Tests for JSON output structure."""

    def test_metric_stats_converted(self):
        """MetricStats are properly converted to dicts."""
        agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[],
            summary={"bat": MetricStats(min_value=3.5, max_value=4.0, mean=3.75, count=100)},
        )

        result = monthly_to_json(agg)

        # Summary should contain stats
        assert isinstance(result["summary"], dict)
        assert result["summary"]["bat"]["min"] == 3.5
        assert result["summary"]["bat"]["max"] == 4.0
        assert result["summary"]["bat"]["mean"] == 3.75
        assert result["summary"]["bat"]["unit"] == "mV"

    def test_nested_structure_serializes(self):
        """Nested structures serialize correctly."""
        daily = DailyAggregate(
            date=date(2024, 1, 1),
            metrics={"bat": MetricStats(min_value=3.7, max_value=3.9, mean=3.8, count=24)},
        )

        agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="companion",
            daily=[daily],
            summary={},
        )

        result = monthly_to_json(agg)
        json_str = json.dumps(result, indent=2)

        # Should be valid JSON with proper structure
        reparsed = json.loads(json_str)
        assert reparsed == result


class TestJsonRoundTrip:
    """Tests for JSON data round-trip integrity."""

    def test_parse_and_serialize_identical(self):
        """Parsing and re-serializing produces same structure."""
        agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[],
            summary={"bat": MetricStats(min_value=3.5, max_value=4.0, mean=3.75, count=100)},
        )

        result = monthly_to_json(agg)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        reserialized = json.dumps(parsed)
        reparsed = json.loads(reserialized)

        assert parsed == reparsed

    def test_numeric_values_preserved(self):
        """Numeric values are preserved through round-trip."""
        agg = MonthlyAggregate(
            year=2024,
            month=6,
            role="repeater",
            daily=[],
            summary={},
        )

        result = monthly_to_json(agg)
        json_str = json.dumps(result)
        parsed = json.loads(json_str)

        assert parsed["year"] == 2024
        assert parsed["month"] == 6
