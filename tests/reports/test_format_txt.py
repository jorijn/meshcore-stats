"""Tests for WeeWX-style ASCII text report formatting."""

from datetime import date

import pytest

from meshmon.reports import (
    Column,
    DailyAggregate,
    LocationInfo,
    MetricStats,
    MonthlyAggregate,
    YearlyAggregate,
    _format_row,
    _format_separator,
    format_monthly_txt,
    format_yearly_txt,
)


class TestColumn:
    """Tests for Column dataclass."""

    def test_format_with_value(self):
        """Formats value with specified width and alignment."""
        col = Column(width=6, align="right")

        result = col.format(42)

        assert result == "    42"

    def test_format_with_none(self):
        """Formats None as dash."""
        col = Column(width=10)

        result = col.format(None)

        assert result == "-".rjust(10)

    def test_left_alignment(self):
        """Left alignment pads on right."""
        col = Column(width=10, align="left")

        result = col.format("Hi")

        assert result == "Hi".ljust(10)

    def test_right_alignment(self):
        """Right alignment pads on left."""
        col = Column(width=10, align="right")

        result = col.format("Hi")

        assert result == "Hi".rjust(10)

    def test_center_alignment(self):
        """Center alignment pads on both sides."""
        col = Column(width=10, align="center")

        result = col.format("Hi")

        assert result == "Hi".center(10)

    def test_decimals_formatting(self):
        """Formats floats with specified decimals."""
        col = Column(width=10, decimals=2)

        result = col.format(3.14159)

        assert result == "3.14".rjust(10)

    def test_comma_separator(self):
        """Uses comma separator for large integers."""
        col = Column(width=15, comma_sep=True)

        result = col.format(1000000)

        assert result == "1,000,000".rjust(15)


class TestFormatRow:
    """Tests for _format_row function."""

    def test_joins_values_with_columns(self):
        """Joins formatted values using column specs."""
        columns = [
            Column(width=5),
            Column(width=5),
        ]

        row = _format_row(columns, [1, 2])

        assert row == "    1    2"

    def test_handles_fewer_values(self):
        """Handles fewer values than columns."""
        columns = [
            Column(width=5),
            Column(width=5),
            Column(width=5),
        ]

        # Should not raise - zip stops at shorter list
        row = _format_row(columns, ["X", "Y"])

        assert row is not None
        assert "X" in row
        assert "Y" in row
        assert len(row) == 10


class TestFormatSeparator:
    """Tests for _format_separator function."""

    def test_creates_separator_line(self):
        """Creates separator line matching column widths."""
        columns = [
            Column(width=10),
            Column(width=8),
        ]

        separator = _format_separator(columns)

        assert separator == "-" * 18

    def test_matches_total_width(self):
        """Separator width matches total column width."""
        columns = [
            Column(width=10),
            Column(width=10),
        ]

        separator = _format_separator(columns)

        assert len(separator) == 20
        assert set(separator) == {"-"}

    def test_custom_separator_char(self):
        """Uses custom separator character."""
        columns = [Column(width=10)]

        separator = _format_separator(columns, char="=")

        assert separator == "=" * 10


class TestFormatMonthlyTxt:
    """Tests for format_monthly_txt function."""

    @pytest.fixture
    def sample_monthly_aggregate(self):
        """Create sample MonthlyAggregate for testing."""
        daily_data = [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "bat": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
                    "nb_recv": MetricStats(total=720, count=24),
                },
            ),
            DailyAggregate(
                date=date(2024, 1, 2),
                metrics={
                    "bat": MetricStats(min_value=3600, max_value=3850, mean=3750, count=24),
                    "nb_recv": MetricStats(total=840, count=24),
                },
            ),
        ]

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=daily_data,
            summary={"bat": MetricStats(min_value=3600, max_value=3900, mean=3775, count=48)},
        )

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo for testing."""
        return LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )

    def test_returns_string(self, sample_monthly_aggregate, sample_location):
        """Returns a string."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)

        assert isinstance(result, str)

    def test_includes_header(self, sample_monthly_aggregate, sample_location):
        """Includes report header with month/year."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)

        assert "MONTHLY MESHCORE REPORT for January 2024" in result

    def test_includes_node_name(self, sample_monthly_aggregate, sample_location):
        """Includes node name."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)

        assert "Test Repeater" in result

    def test_has_table_structure(self, sample_monthly_aggregate, sample_location):
        """Has ASCII table structure with separators."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)

        assert "BATTERY (V)" in result
        assert result.count("-" * 95) == 2

    def test_daily_rows_rendered(self, sample_monthly_aggregate, sample_location):
        """Renders one row per day with battery values."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)
        lines = result.splitlines()
        daily_lines = [line for line in lines if line[:3].strip().isdigit()]

        assert [line[:3].strip() for line in daily_lines] == ["1", "2"]
        assert any("3.80" in line for line in daily_lines)
        assert any("3.75" in line for line in daily_lines)

    def test_handles_empty_daily(self, sample_location):
        """Handles aggregate with no daily data."""
        agg = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[],
            summary={},
        )

        result = format_monthly_txt(agg, "Test Repeater", sample_location)

        assert isinstance(result, str)
        lines = result.splitlines()
        daily_lines = [line for line in lines if line[:3].strip().isdigit()]
        assert daily_lines == []

    def test_includes_location_info(self, sample_monthly_aggregate, sample_location):
        """Includes location information."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)

        assert "NAME: Test Location" in result
        assert "COORDS:" in result
        assert "ELEV: 10 meters" in result


class TestFormatYearlyTxt:
    """Tests for format_yearly_txt function."""

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

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo for testing."""
        return LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )

    def test_returns_string(self, sample_yearly_aggregate, sample_location):
        """Returns a string."""
        result = format_yearly_txt(sample_yearly_aggregate, "Test Repeater", sample_location)

        assert isinstance(result, str)

    def test_includes_year(self, sample_yearly_aggregate, sample_location):
        """Includes year in header."""
        result = format_yearly_txt(sample_yearly_aggregate, "Test Repeater", sample_location)

        assert "YEARLY MESHCORE REPORT for 2024" in result
        assert "NODE: Test Repeater" in result
        assert "NAME: Test Location" in result

    def test_has_monthly_breakdown(self, sample_yearly_aggregate, sample_location):
        """Shows monthly breakdown."""
        result = format_yearly_txt(sample_yearly_aggregate, "Test Repeater", sample_location)

        lines = result.splitlines()
        monthly_lines = [line for line in lines if line.strip().startswith("2024")]
        months = [line[4:8].strip() for line in monthly_lines]
        assert months == ["01", "02"]

    def test_handles_empty_monthly(self, sample_location):
        """Handles aggregate with no monthly data."""
        agg = YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=[],
            summary={},
        )

        result = format_yearly_txt(agg, "Test Repeater", sample_location)

        assert isinstance(result, str)


class TestFormatYearlyCompanionTxt:
    """Tests for format_yearly_txt with companion role."""

    @pytest.fixture
    def sample_companion_yearly_aggregate(self):
        """Create sample YearlyAggregate for companion role testing."""
        from datetime import datetime as dt
        monthly_data = [
            MonthlyAggregate(
                year=2024,
                month=1,
                role="companion",
                daily=[],
                summary={
                    "battery_mv": MetricStats(
                        min_value=3600, min_time=dt(2024, 1, 15, 4, 0),
                        max_value=3900, max_time=dt(2024, 1, 20, 14, 0),
                        mean=3750, count=720
                    ),
                    "bat_pct": MetricStats(mean=75, count=720),
                    "contacts": MetricStats(mean=10, count=720),
                    "recv": MetricStats(total=5000, count=720),
                    "sent": MetricStats(total=3000, count=720),
                },
            ),
            MonthlyAggregate(
                year=2024,
                month=2,
                role="companion",
                daily=[],
                summary={
                    "battery_mv": MetricStats(
                        min_value=3500, min_time=dt(2024, 2, 10, 5, 0),
                        max_value=3850, max_time=dt(2024, 2, 25, 16, 0),
                        mean=3700, count=672
                    ),
                    "bat_pct": MetricStats(mean=70, count=672),
                    "contacts": MetricStats(mean=12, count=672),
                    "recv": MetricStats(total=4500, count=672),
                    "sent": MetricStats(total=2800, count=672),
                },
            ),
        ]

        return YearlyAggregate(
            year=2024,
            role="companion",
            monthly=monthly_data,
            summary={
                "battery_mv": MetricStats(
                    min_value=3500, min_time=dt(2024, 2, 10, 5, 0),
                    max_value=3900, max_time=dt(2024, 1, 20, 14, 0),
                    mean=3725, count=1392
                ),
                "bat_pct": MetricStats(mean=72.5, count=1392),
                "contacts": MetricStats(mean=11, count=1392),
                "recv": MetricStats(total=9500, count=1392),
                "sent": MetricStats(total=5800, count=1392),
            },
        )

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo for testing."""
        return LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )

    def test_returns_string(self, sample_companion_yearly_aggregate, sample_location):
        """Returns a string."""
        result = format_yearly_txt(sample_companion_yearly_aggregate, "Test Companion", sample_location)

        assert isinstance(result, str)

    def test_includes_year(self, sample_companion_yearly_aggregate, sample_location):
        """Includes year in header."""
        result = format_yearly_txt(sample_companion_yearly_aggregate, "Test Companion", sample_location)

        assert "YEARLY MESHCORE REPORT for 2024" in result
        assert "NODE: Test Companion" in result
        assert "NAME: Test Location" in result

    def test_includes_node_name(self, sample_companion_yearly_aggregate, sample_location):
        """Includes node name."""
        result = format_yearly_txt(sample_companion_yearly_aggregate, "Test Companion", sample_location)

        assert "Test Companion" in result

    def test_has_monthly_breakdown(self, sample_companion_yearly_aggregate, sample_location):
        """Shows monthly breakdown."""
        result = format_yearly_txt(sample_companion_yearly_aggregate, "Test Companion", sample_location)

        lines = result.splitlines()
        monthly_lines = [line for line in lines if line.strip().startswith("2024")]
        months = [line[4:8].strip() for line in monthly_lines]
        assert months == ["01", "02"]

    def test_has_battery_data(self, sample_companion_yearly_aggregate, sample_location):
        """Contains battery voltage data."""
        result = format_yearly_txt(sample_companion_yearly_aggregate, "Test Companion", sample_location)

        # Battery header or VOLT should be present
        assert "BATT" in result or "VOLT" in result

    def test_has_packet_counts(self, sample_companion_yearly_aggregate, sample_location):
        """Contains packet count data."""
        result = format_yearly_txt(sample_companion_yearly_aggregate, "Test Companion", sample_location)

        # RX and TX columns should be present
        assert "RX" in result
        assert "TX" in result

    def test_handles_empty_monthly(self, sample_location):
        """Handles aggregate with no monthly data."""
        agg = YearlyAggregate(
            year=2024,
            role="companion",
            monthly=[],
            summary={},
        )

        result = format_yearly_txt(agg, "Test Companion", sample_location)

        assert isinstance(result, str)


class TestFormatMonthlyCompanionTxt:
    """Tests for format_monthly_txt with companion role."""

    @pytest.fixture
    def sample_companion_monthly_aggregate(self):
        """Create sample MonthlyAggregate for companion role testing."""
        from datetime import datetime as dt
        daily_data = [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "battery_mv": MetricStats(
                        min_value=3700, min_time=dt(2024, 1, 1, 4, 0),
                        max_value=3900, max_time=dt(2024, 1, 1, 14, 0),
                        mean=3800, count=24
                    ),
                    "bat_pct": MetricStats(mean=75, count=24),
                    "contacts": MetricStats(mean=10, count=24),
                    "recv": MetricStats(total=500, count=24),
                    "sent": MetricStats(total=300, count=24),
                },
            ),
            DailyAggregate(
                date=date(2024, 1, 2),
                metrics={
                    "battery_mv": MetricStats(
                        min_value=3650, min_time=dt(2024, 1, 2, 5, 0),
                        max_value=3850, max_time=dt(2024, 1, 2, 12, 0),
                        mean=3750, count=24
                    ),
                    "bat_pct": MetricStats(mean=70, count=24),
                    "contacts": MetricStats(mean=11, count=24),
                    "recv": MetricStats(total=450, count=24),
                    "sent": MetricStats(total=280, count=24),
                },
            ),
        ]

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="companion",
            daily=daily_data,
            summary={
                "battery_mv": MetricStats(
                    min_value=3650, min_time=dt(2024, 1, 2, 5, 0),
                    max_value=3900, max_time=dt(2024, 1, 1, 14, 0),
                    mean=3775, count=48
                ),
                "bat_pct": MetricStats(mean=72.5, count=48),
                "contacts": MetricStats(mean=10.5, count=48),
                "recv": MetricStats(total=950, count=48),
                "sent": MetricStats(total=580, count=48),
            },
        )

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo for testing."""
        return LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )

    def test_returns_string(self, sample_companion_monthly_aggregate, sample_location):
        """Returns a string."""
        result = format_monthly_txt(sample_companion_monthly_aggregate, "Test Companion", sample_location)

        assert isinstance(result, str)

    def test_includes_month_year(self, sample_companion_monthly_aggregate, sample_location):
        """Includes month and year in header."""
        result = format_monthly_txt(sample_companion_monthly_aggregate, "Test Companion", sample_location)

        assert "MONTHLY MESHCORE REPORT for January 2024" in result
        assert "NODE: Test Companion" in result

    def test_has_daily_breakdown(self, sample_companion_monthly_aggregate, sample_location):
        """Shows daily breakdown."""
        result = format_monthly_txt(sample_companion_monthly_aggregate, "Test Companion", sample_location)

        lines = result.splitlines()
        daily_lines = [line for line in lines if line[:3].strip().isdigit()]
        assert [line[:3].strip() for line in daily_lines] == ["1", "2"]

    def test_has_packet_counts(self, sample_companion_monthly_aggregate, sample_location):
        """Contains packet count data."""
        result = format_monthly_txt(sample_companion_monthly_aggregate, "Test Companion", sample_location)

        # RX and TX columns should be present
        assert "RX" in result
        assert "TX" in result


class TestTextReportContent:
    """Tests for text report content quality."""

    @pytest.fixture
    def sample_monthly_aggregate(self):
        """Create sample MonthlyAggregate for testing."""
        daily_data = [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={"bat": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24)},
            ),
        ]

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=daily_data,
            summary={"bat": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24)},
        )

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo for testing."""
        return LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )

    def test_readable_numbers(self, sample_monthly_aggregate, sample_location):
        """Numbers are formatted readably."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)

        # Should contain numeric values
        assert any(c.isdigit() for c in result)

    def test_aligned_columns(self, sample_monthly_aggregate, sample_location):
        """Columns appear aligned."""
        result = format_monthly_txt(sample_monthly_aggregate, "Test Repeater", sample_location)
        lines = result.split("\n")

        # Find lines that start with day numbers (data rows)
        # These are the actual data rows that should be aligned
        data_lines = [line for line in lines if line.strip() and line.strip()[:2].isdigit()]
        if len(data_lines) >= 2:
            lengths = [len(line) for line in data_lines]
            # Data rows should be same length (well aligned)
            assert max(lengths) - min(lengths) < 10


class TestCompanionFormatting:
    """Tests for companion-specific formatting."""

    @pytest.fixture
    def companion_monthly_aggregate(self):
        """Create sample companion MonthlyAggregate."""
        daily_data = [
            DailyAggregate(
                date=date(2024, 1, 1),
                metrics={
                    "battery_mv": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
                    "contacts": MetricStats(min_value=5, max_value=10, mean=7, count=24),
                    "recv": MetricStats(total=720, count=24),
                },
            ),
        ]

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="companion",
            daily=daily_data,
            summary={
                "battery_mv": MetricStats(min_value=3700, max_value=3900, mean=3800, count=24),
            },
        )

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo."""
        return LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )

    def test_companion_monthly_format(self, companion_monthly_aggregate, sample_location):
        """Companion monthly report formats correctly."""
        result = format_monthly_txt(companion_monthly_aggregate, "Test Companion", sample_location)

        assert isinstance(result, str)
        assert "MONTHLY MESHCORE REPORT for January 2024" in result
        assert "NODE: Test Companion" in result
        assert "NAME: Test Location" in result
