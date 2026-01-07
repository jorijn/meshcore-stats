"""Tests for chart helper functions in charts.py."""

import json
import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from meshmon.charts import (
    _hex_to_rgba,
    _aggregate_bins,
    _configure_x_axis,
    _inject_data_attributes,
    DataPoint,
    TimeSeries,
    ChartStatistics,
    calculate_statistics,
    ChartTheme,
    CHART_THEMES,
    PERIOD_CONFIG,
)


class TestHexToRgba:
    """Test _hex_to_rgba function."""

    def test_6_char_hex(self):
        """6-character hex (RGB) converts with alpha 1.0."""
        r, g, b, a = _hex_to_rgba("ff0000")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(1.0)

    def test_8_char_hex(self):
        """8-character hex (RGBA) converts with proper alpha."""
        r, g, b, a = _hex_to_rgba("ff000080")  # Red with 50% alpha
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(128 / 255)

    def test_white(self):
        """White color converts correctly."""
        r, g, b, a = _hex_to_rgba("ffffff")
        assert r == pytest.approx(1.0)
        assert g == pytest.approx(1.0)
        assert b == pytest.approx(1.0)
        assert a == pytest.approx(1.0)

    def test_black(self):
        """Black color converts correctly."""
        r, g, b, a = _hex_to_rgba("000000")
        assert r == pytest.approx(0.0)
        assert g == pytest.approx(0.0)
        assert b == pytest.approx(0.0)
        assert a == pytest.approx(1.0)

    def test_transparent(self):
        """Fully transparent converts correctly."""
        r, g, b, a = _hex_to_rgba("00000000")
        assert a == pytest.approx(0.0)

    def test_theme_area_color(self):
        """Theme area colors with alpha parse correctly."""
        # Light theme area: "b4530926" (15% opacity)
        r, g, b, a = _hex_to_rgba("b4530926")
        assert a == pytest.approx(0x26 / 255)  # 0x26 = 38

        # Dark theme area: "f59e0b33" (20% opacity)
        r, g, b, a = _hex_to_rgba("f59e0b33")
        assert a == pytest.approx(0x33 / 255)  # 0x33 = 51


class TestAggregateBins:
    """Test _aggregate_bins function."""

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = _aggregate_bins([], 3600)
        assert result == []

    def test_single_point(self):
        """Single point returns single aggregated point."""
        ts = datetime(2024, 1, 1, 12, 30, 0)
        points = [(ts, 100.0)]
        result = _aggregate_bins(points, 3600)  # 1-hour bins
        assert len(result) == 1
        assert result[0][1] == 100.0

    def test_points_same_bin(self):
        """Points in same bin are averaged."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        points = [
            (ts + timedelta(minutes=10), 100.0),
            (ts + timedelta(minutes=20), 200.0),
            (ts + timedelta(minutes=30), 300.0),
        ]
        result = _aggregate_bins(points, 3600)  # 1-hour bins
        assert len(result) == 1
        assert result[0][1] == pytest.approx(200.0)  # Mean of 100, 200, 300

    def test_points_different_bins(self):
        """Points in different bins stay separate."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        points = [
            (ts, 100.0),  # Hour 12 bin
            (ts + timedelta(hours=1), 200.0),  # Hour 13 bin
            (ts + timedelta(hours=2), 300.0),  # Hour 14 bin
        ]
        result = _aggregate_bins(points, 3600)  # 1-hour bins
        assert len(result) == 3
        assert result[0][1] == 100.0
        assert result[1][1] == 200.0
        assert result[2][1] == 300.0

    def test_bin_center_timestamp(self):
        """Result timestamps are at bin center."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        points = [(ts, 100.0)]
        result = _aggregate_bins(points, 3600)  # 1-hour bins
        # Bin starts at 12:00, center should be at 12:30
        assert result[0][0].minute == 30

    def test_30_minute_bins(self):
        """30-minute bins aggregate correctly."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        points = [
            (ts + timedelta(minutes=5), 100.0),  # First 30-min bin
            (ts + timedelta(minutes=10), 110.0),
            (ts + timedelta(minutes=35), 200.0),  # Second 30-min bin
            (ts + timedelta(minutes=40), 210.0),
        ]
        result = _aggregate_bins(points, 1800)  # 30-minute bins
        assert len(result) == 2
        assert result[0][1] == pytest.approx(105.0)  # Mean of 100, 110
        assert result[1][1] == pytest.approx(205.0)  # Mean of 200, 210

    def test_sorted_output(self):
        """Output is sorted by timestamp."""
        ts = datetime(2024, 1, 1, 12, 0, 0)
        # Input in reverse order
        points = [
            (ts + timedelta(hours=2), 300.0),
            (ts, 100.0),
            (ts + timedelta(hours=1), 200.0),
        ]
        result = _aggregate_bins(points, 3600)
        timestamps = [r[0] for r in result]
        assert timestamps == sorted(timestamps)


class TestConfigureXAxis:
    """Test _configure_x_axis function."""

    def test_day_period_format(self):
        """Day period uses HH:MM format with 4-hour intervals."""
        fig, ax = self._create_mock_ax()
        _configure_x_axis(ax, "day")
        ax.xaxis.set_major_formatter.assert_called_once()
        ax.xaxis.set_major_locator.assert_called_once()

    def test_week_period_format(self):
        """Week period uses weekday format with daily intervals."""
        fig, ax = self._create_mock_ax()
        _configure_x_axis(ax, "week")
        ax.xaxis.set_major_formatter.assert_called_once()
        ax.xaxis.set_major_locator.assert_called_once()

    def test_month_period_format(self):
        """Month period uses day-of-month format with 5-day intervals."""
        fig, ax = self._create_mock_ax()
        _configure_x_axis(ax, "month")
        ax.xaxis.set_major_formatter.assert_called_once()
        ax.xaxis.set_major_locator.assert_called_once()

    def test_year_period_format(self):
        """Year period uses month abbreviation format."""
        fig, ax = self._create_mock_ax()
        _configure_x_axis(ax, "year")
        ax.xaxis.set_major_formatter.assert_called_once()
        ax.xaxis.set_major_locator.assert_called_once()

    def test_unknown_period_defaults_to_year(self):
        """Unknown period defaults to year format."""
        fig, ax = self._create_mock_ax()
        _configure_x_axis(ax, "unknown")
        ax.xaxis.set_major_formatter.assert_called_once()

    def _create_mock_ax(self):
        """Create a mock axes object."""
        ax = MagicMock()
        ax.xaxis = MagicMock()
        ax.xaxis.get_majorticklabels.return_value = []
        return None, ax


class TestInjectDataAttributes:
    """Test _inject_data_attributes function."""

    def test_adds_root_svg_attributes(self):
        """Adds data attributes to root SVG element."""
        ts = self._create_sample_timeseries()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 280">'

        result = _inject_data_attributes(svg, ts, "light")

        assert 'data-metric="bat"' in result
        assert 'data-period="day"' in result
        assert 'data-theme="light"' in result
        assert 'data-x-start="' in result
        assert 'data-x-end="' in result
        assert 'data-y-min="' in result
        assert 'data-y-max="' in result
        assert 'data-points="' in result

    def test_data_points_json_format(self):
        """Data points are JSON-encoded in attribute."""
        ts = self._create_sample_timeseries()
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 280">'

        result = _inject_data_attributes(svg, ts, "light")

        # Extract data-points value and decode
        import re
        match = re.search(r'data-points="([^"]+)"', result)
        assert match is not None
        points_json = match.group(1).replace('&quot;', '"')
        points = json.loads(points_json)

        assert len(points) == 3
        assert all("ts" in p and "v" in p for p in points)

    def test_uses_provided_x_range(self):
        """Uses provided x_start and x_end for axis range."""
        ts = self._create_sample_timeseries()
        svg = '<svg xmlns="http://www.w3.org/2000/svg">'
        x_start = datetime(2024, 1, 1, 0, 0, 0)
        x_end = datetime(2024, 1, 2, 0, 0, 0)

        result = _inject_data_attributes(
            svg, ts, "light", x_start=x_start, x_end=x_end
        )

        assert f'data-x-start="{int(x_start.timestamp())}"' in result
        assert f'data-x-end="{int(x_end.timestamp())}"' in result

    def test_uses_provided_y_range(self):
        """Uses provided y_min and y_max for axis range."""
        ts = self._create_sample_timeseries()
        svg = '<svg xmlns="http://www.w3.org/2000/svg">'

        result = _inject_data_attributes(svg, ts, "light", y_min=0.0, y_max=100.0)

        assert 'data-y-min="0.0"' in result
        assert 'data-y-max="100.0"' in result

    def test_escapes_quotes_in_json(self):
        """JSON quotes are properly escaped as &quot;"""
        ts = self._create_sample_timeseries()
        svg = '<svg xmlns="http://www.w3.org/2000/svg">'

        result = _inject_data_attributes(svg, ts, "light")

        # Ensure raw JSON double quotes are escaped
        assert '"ts":' not in result  # Should be &quot;ts&quot;:
        assert '&quot;ts&quot;:' in result

    def _create_sample_timeseries(self) -> TimeSeries:
        """Create sample time series for testing."""
        now = datetime.now()
        return TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[
                DataPoint(timestamp=now - timedelta(hours=2), value=3.8),
                DataPoint(timestamp=now - timedelta(hours=1), value=3.9),
                DataPoint(timestamp=now, value=4.0),
            ],
        )


class TestChartStatistics:
    """Test ChartStatistics dataclass."""

    def test_to_dict_empty(self):
        """Empty statistics convert to dict with None values."""
        stats = ChartStatistics()
        result = stats.to_dict()
        assert result == {"min": None, "avg": None, "max": None, "current": None}

    def test_to_dict_with_values(self):
        """Statistics with values convert correctly."""
        stats = ChartStatistics(
            min_value=1.0, avg_value=2.0, max_value=3.0, current_value=2.5
        )
        result = stats.to_dict()
        assert result == {"min": 1.0, "avg": 2.0, "max": 3.0, "current": 2.5}


class TestCalculateStatistics:
    """Test calculate_statistics function."""

    def test_empty_timeseries(self):
        """Empty time series returns empty statistics."""
        ts = TimeSeries(metric="bat", role="repeater", period="day", points=[])
        stats = calculate_statistics(ts)
        assert stats.min_value is None
        assert stats.avg_value is None
        assert stats.max_value is None
        assert stats.current_value is None

    def test_single_point(self):
        """Single point has min=max=avg=current."""
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[DataPoint(timestamp=datetime.now(), value=3.8)],
        )
        stats = calculate_statistics(ts)
        assert stats.min_value == 3.8
        assert stats.avg_value == 3.8
        assert stats.max_value == 3.8
        assert stats.current_value == 3.8

    def test_multiple_points(self):
        """Multiple points calculate correct statistics."""
        now = datetime.now()
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[
                DataPoint(timestamp=now - timedelta(hours=2), value=3.0),
                DataPoint(timestamp=now - timedelta(hours=1), value=4.0),
                DataPoint(timestamp=now, value=5.0),
            ],
        )
        stats = calculate_statistics(ts)
        assert stats.min_value == 3.0
        assert stats.max_value == 5.0
        assert stats.avg_value == pytest.approx(4.0)
        assert stats.current_value == 5.0  # Last point

    def test_current_is_last_point(self):
        """Current value is the most recent (last) point."""
        now = datetime.now()
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[
                DataPoint(timestamp=now - timedelta(hours=2), value=100.0),
                DataPoint(timestamp=now - timedelta(hours=1), value=50.0),
                DataPoint(timestamp=now, value=75.0),
            ],
        )
        stats = calculate_statistics(ts)
        assert stats.current_value == 75.0


class TestTimeSeries:
    """Test TimeSeries dataclass."""

    def test_timestamps_property(self):
        """timestamps property returns list of timestamps."""
        now = datetime.now()
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[
                DataPoint(timestamp=now - timedelta(hours=1), value=3.8),
                DataPoint(timestamp=now, value=3.9),
            ],
        )
        timestamps = ts.timestamps
        assert len(timestamps) == 2
        assert all(isinstance(t, datetime) for t in timestamps)

    def test_values_property(self):
        """values property returns list of values."""
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[
                DataPoint(timestamp=datetime.now(), value=3.8),
                DataPoint(timestamp=datetime.now(), value=3.9),
            ],
        )
        values = ts.values
        assert values == [3.8, 3.9]

    def test_is_empty_true(self):
        """is_empty returns True for empty points."""
        ts = TimeSeries(metric="bat", role="repeater", period="day", points=[])
        assert ts.is_empty is True

    def test_is_empty_false(self):
        """is_empty returns False for non-empty points."""
        ts = TimeSeries(
            metric="bat",
            role="repeater",
            period="day",
            points=[DataPoint(timestamp=datetime.now(), value=3.8)],
        )
        assert ts.is_empty is False


class TestChartTheme:
    """Test ChartTheme dataclass and constants."""

    def test_light_theme_exists(self):
        """Light theme is defined."""
        assert "light" in CHART_THEMES
        light = CHART_THEMES["light"]
        assert light.name == "light"
        assert light.background
        assert light.line

    def test_dark_theme_exists(self):
        """Dark theme is defined."""
        assert "dark" in CHART_THEMES
        dark = CHART_THEMES["dark"]
        assert dark.name == "dark"
        assert dark.background
        assert dark.line

    def test_themes_have_different_colors(self):
        """Light and dark themes have different colors."""
        light = CHART_THEMES["light"]
        dark = CHART_THEMES["dark"]
        assert light.background != dark.background
        assert light.line != dark.line


class TestPeriodConfig:
    """Test PERIOD_CONFIG constants."""

    def test_all_periods_defined(self):
        """All expected periods are defined."""
        assert "day" in PERIOD_CONFIG
        assert "week" in PERIOD_CONFIG
        assert "month" in PERIOD_CONFIG
        assert "year" in PERIOD_CONFIG

    def test_day_has_no_binning(self):
        """Day period has no time binning."""
        assert PERIOD_CONFIG["day"]["bin_seconds"] is None

    def test_week_has_30_min_bins(self):
        """Week period has 30-minute bins."""
        assert PERIOD_CONFIG["week"]["bin_seconds"] == 1800

    def test_month_has_2_hour_bins(self):
        """Month period has 2-hour bins."""
        assert PERIOD_CONFIG["month"]["bin_seconds"] == 7200

    def test_year_has_1_day_bins(self):
        """Year period has 1-day bins."""
        assert PERIOD_CONFIG["year"]["bin_seconds"] == 86400

    def test_all_periods_have_lookback(self):
        """All periods have lookback duration defined."""
        for period, cfg in PERIOD_CONFIG.items():
            assert "lookback" in cfg
            assert isinstance(cfg["lookback"], timedelta)
