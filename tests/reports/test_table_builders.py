"""Tests for report table building functions."""

from datetime import date

import pytest

from meshmon.html import (
    build_monthly_table_data,
    build_yearly_table_data,
)
from meshmon.reports import (
    DailyAggregate,
    MetricStats,
    MonthlyAggregate,
    YearlyAggregate,
)


class TestBuildMonthlyTableData:
    """Tests for build_monthly_table_data function."""

    @pytest.fixture
    def sample_monthly_aggregate(self):
        """Create sample MonthlyAggregate for testing."""
        daily_data = [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "bat": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
                    "last_rssi": MetricStats(min_value=-95, max_value=-80, mean=-87, count=24),
                    "nb_recv": MetricStats(total=720, count=24),
                },
            ),
            DailyAggregate(
                date=date(2024, 1, 2),
                metrics={
                    "bat": MetricStats(min_value=3600, max_value=3850, mean=3750, count=24),
                    "last_rssi": MetricStats(min_value=-93, max_value=-78, mean=-85, count=24),
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
                "bat": MetricStats(min_value=3600, max_value=3900, mean=3775, count=48),
                "last_rssi": MetricStats(min_value=-95, max_value=-78, mean=-86, count=48),
                "nb_recv": MetricStats(total=1560, count=48),
            },
        )

    def test_returns_tuple_of_three_lists(self, sample_monthly_aggregate):
        """Returns tuple of (column_groups, headers, rows)."""
        result = build_monthly_table_data(sample_monthly_aggregate, "repeater")

        assert isinstance(result, tuple)
        assert len(result) == 3

        column_groups, headers, rows = result
        assert isinstance(column_groups, list)
        assert isinstance(headers, list)
        assert isinstance(rows, list)

    def test_rows_match_daily_count(self, sample_monthly_aggregate):
        """Number of rows matches number of daily aggregates (plus summary)."""
        _, _, rows = build_monthly_table_data(sample_monthly_aggregate, "repeater")

        # Should have 2 data rows + 1 summary row = 3 total
        data_rows = [r for r in rows if not r.get("is_summary", False)]
        assert len(data_rows) == 2
        assert len(rows) == 3
        assert rows[-1]["is_summary"] is True

    def test_headers_have_labels(self, sample_monthly_aggregate):
        """Headers include label information."""
        _, headers, _ = build_monthly_table_data(sample_monthly_aggregate, "repeater")

        expected_labels = [
            "Day",
            "Avg V",
            "Avg %",
            "Min V",
            "Max V",
            "RSSI",
            "SNR",
            "Noise",
            "RX",
            "TX",
            "Secs",
        ]
        assert [header["label"] for header in headers] == expected_labels

    def test_rows_have_date(self, sample_monthly_aggregate):
        """Each data row includes date information via cells."""
        _, _, rows = build_monthly_table_data(sample_monthly_aggregate, "repeater")

        data_rows = [r for r in rows if not r.get("is_summary", False)]
        for row in data_rows:
            assert isinstance(row, dict)
            # Row has cells with date value
            assert "cells" in row
            # First cell should be the day
            assert len(row["cells"]) > 0
        assert [row["cells"][0]["value"] for row in data_rows] == ["01", "02"]

    def test_daily_row_values(self, sample_monthly_aggregate):
        """Daily rows include formatted values and placeholders."""
        _, _, rows = build_monthly_table_data(sample_monthly_aggregate, "repeater")
        first_row = next(r for r in rows if not r.get("is_summary", False))
        cells = first_row["cells"]

        assert cells[0]["value"] == "01"
        assert cells[1]["value"] == "3.80"
        assert cells[2]["value"] == "-"
        assert cells[5]["value"] == "-87"
        assert cells[6]["value"] == "-"
        assert cells[8]["value"] == "720"

    def test_handles_empty_aggregate(self):
        """Handles aggregate with no daily data."""
        agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[],
            summary={},
        )

        result = build_monthly_table_data(agg, "repeater")

        column_groups, headers, rows = result
        assert isinstance(rows, list)
        # Empty aggregate should have only summary row or no data rows
        data_rows = [r for r in rows if not r.get("is_summary", False)]
        assert len(data_rows) == 0


class TestBuildYearlyTableData:
    """Tests for build_yearly_table_data function."""

    @pytest.fixture
    def sample_yearly_aggregate(self):
        """Create sample YearlyAggregate for testing."""
        monthly_data = [
            MonthlyAggregate(
                year=2024,
                month=1,
                role="repeater",
                daily=[],
                summary={"bat": MetricStats(min_value=3600, max_value=3900, mean=3750, count=720)},
            ),
            MonthlyAggregate(
                year=2024,
                month=2,
                role="repeater",
                daily=[],
                summary={"bat": MetricStats(min_value=3500, max_value=3850, mean=3700, count=672)},
            ),
        ]

        return YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=monthly_data,
            summary={"bat": MetricStats(min_value=3500, max_value=3900, mean=3725, count=1392)},
        )

    def test_returns_tuple_of_three_lists(self, sample_yearly_aggregate):
        """Returns tuple of (column_groups, headers, rows)."""
        result = build_yearly_table_data(sample_yearly_aggregate, "repeater")

        assert isinstance(result, tuple)
        assert len(result) == 3

        column_groups, headers, rows = result
        assert isinstance(column_groups, list)
        assert isinstance(headers, list)
        assert isinstance(rows, list)

    def test_rows_match_monthly_count(self, sample_yearly_aggregate):
        """Number of rows matches number of monthly data (plus summary)."""
        _, _, rows = build_yearly_table_data(sample_yearly_aggregate, "repeater")

        # Should have 2 data rows + 1 summary row
        data_rows = [r for r in rows if not r.get("is_summary", False)]
        assert len(data_rows) == 2
        assert len(rows) == 3
        assert rows[-1]["is_summary"] is True

    def test_headers_have_labels(self, sample_yearly_aggregate):
        """Headers include label information."""
        _, headers, _ = build_yearly_table_data(sample_yearly_aggregate, "repeater")

        expected_labels = [
            "Year",
            "Mo",
            "Volt",
            "%",
            "High",
            "Low",
            "RSSI",
            "SNR",
            "RX",
            "TX",
        ]
        assert [header["label"] for header in headers] == expected_labels

    def test_rows_have_month(self, sample_yearly_aggregate):
        """Each row includes month information."""
        _, _, rows = build_yearly_table_data(sample_yearly_aggregate, "repeater")

        data_rows = [r for r in rows if not r.get("is_summary", False)]
        months = [row["cells"][1]["value"] for row in data_rows]
        assert months == ["01", "02"]

    def test_yearly_row_values(self, sample_yearly_aggregate):
        """Yearly rows include formatted values and placeholders."""
        _, _, rows = build_yearly_table_data(sample_yearly_aggregate, "repeater")
        first_row = next(r for r in rows if not r.get("is_summary", False))
        cells = first_row["cells"]

        assert cells[0]["value"] == "2024"
        assert cells[1]["value"] == "01"
        assert cells[2]["value"] == "3.75"
        assert cells[3]["value"] == "-"

    def test_handles_empty_aggregate(self):
        """Handles aggregate with no monthly data."""
        agg = YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=[],
            summary={},
        )

        result = build_yearly_table_data(agg, "repeater")

        column_groups, headers, rows = result
        assert isinstance(rows, list)
        # Empty aggregate should have only summary row or no data rows
        data_rows = [r for r in rows if not r.get("is_summary", False)]
        assert len(data_rows) == 0


class TestTableColumnGroups:
    """Tests for column grouping in tables."""

    @pytest.fixture
    def monthly_aggregate_with_data(self):
        """Aggregate with data for column group testing."""
        daily = DailyAggregate(
            date=date(2024, 1, 1),
            metrics={
                "bat": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
                "last_rssi": MetricStats(min_value=-95, max_value=-80, mean=-87, count=24),
                "nb_recv": MetricStats(total=720, count=24),
            },
        )

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[daily],
            summary={},
        )

    def test_column_groups_structure(self, monthly_aggregate_with_data):
        """Column groups have expected structure."""
        column_groups, _, _ = build_monthly_table_data(monthly_aggregate_with_data, "repeater")

        assert column_groups == [
            {"label": "", "colspan": 1},
            {"label": "Battery", "colspan": 4},
            {"label": "Signal", "colspan": 3},
            {"label": "Packets", "colspan": 2},
            {"label": "Air", "colspan": 1},
        ]

    def test_column_groups_span_matches_headers(self, monthly_aggregate_with_data):
        """Column group spans should add up to header count."""
        column_groups, headers, _ = build_monthly_table_data(monthly_aggregate_with_data, "repeater")

        total_span = sum(
            g.get("span", g.get("colspan", len(g.get("columns", []))))
            for g in column_groups
        )

        assert total_span == len(headers)


class TestTableRolesHandling:
    """Tests for different role handling in tables."""

    @pytest.fixture
    def companion_aggregate(self):
        """Aggregate for companion role."""
        daily = DailyAggregate(
            date=date(2024, 1, 1),
            metrics={
                "battery_mv": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
                "contacts": MetricStats(min_value=5, max_value=10, mean=7, count=24),
                "recv": MetricStats(total=720, count=24),
            },
        )

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="companion",
            daily=[daily],
            summary={},
        )

    def test_companion_role_works(self, companion_aggregate):
        """Table building works for companion role."""
        result = build_monthly_table_data(companion_aggregate, "companion")

        column_groups, headers, rows = result
        assert isinstance(rows, list)
        # 1 data row + summary row
        data_rows = [r for r in rows if not r.get("is_summary", False)]
        assert len(data_rows) == 1
        assert [header["label"] for header in headers] == [
            "Day",
            "Avg V",
            "Avg %",
            "Min V",
            "Max V",
            "Contacts",
            "RX",
            "TX",
        ]

    def test_different_roles_different_columns(self, companion_aggregate):
        """Different roles may have different column structures."""
        # Create a repeater aggregate
        repeater_daily = DailyAggregate(
            date=date(2024, 1, 1),
            metrics={
                "bat": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
            },
        )

        repeater_agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[repeater_daily],
            summary={},
        )

        companion_result = build_monthly_table_data(companion_aggregate, "companion")
        repeater_result = build_monthly_table_data(repeater_agg, "repeater")

        # Both should return valid data
        assert len(companion_result) == 3
        assert len(repeater_result) == 3
        assert [h["label"] for h in companion_result[1]] != [h["label"] for h in repeater_result[1]]
