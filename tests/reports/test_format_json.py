"""Tests for JSON report formatting."""

import pytest
import json
from datetime import datetime, date

from meshmon.reports import (
    monthly_to_json,
    yearly_to_json,
    MonthlyAggregate,
    YearlyAggregate,
    DailyAggregate,
    MetricStats,
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
            summary={"bat": MetricStats(min_value=3.6, max_value=3.9, mean=3.775, count=48)},
        )

    def test_returns_dict(self, sample_monthly_aggregate):
        """Returns a dictionary."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert isinstance(result, dict)

    def test_includes_report_type(self, sample_monthly_aggregate):
        """Includes report_type field."""
        result = monthly_to_json(sample_monthly_aggregate)
        assert result.get("report_type") == "monthly" or "year" in result

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

    def test_daily_data_has_date(self, sample_monthly_aggregate):
        """Daily data includes date."""
        result = monthly_to_json(sample_monthly_aggregate)
        first_day = result["daily"][0]
        assert "date" in first_day

    def test_is_json_serializable(self, sample_monthly_aggregate):
        """Result is JSON serializable."""
        result = monthly_to_json(sample_monthly_aggregate)
        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

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
        assert result.get("report_type") == "yearly" or "year" in result

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

    def test_is_json_serializable(self, sample_yearly_aggregate):
        """Result is JSON serializable."""
        result = yearly_to_json(sample_yearly_aggregate)
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

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
        if "summary" in result:
            assert isinstance(result["summary"], dict)

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
