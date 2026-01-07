"""Tests for SVG chart rendering."""

import pytest
from datetime import datetime, timedelta

from meshmon.charts import (
    render_chart_svg,
    CHART_THEMES,
    DataPoint,
    TimeSeries,
)

from .conftest import extract_svg_data_attributes, normalize_svg_for_snapshot


class TestRenderChartSvg:
    """Tests for render_chart_svg function."""

    def test_returns_svg_string(self, sample_timeseries, light_theme):
        """Returns valid SVG string."""
        svg = render_chart_svg(sample_timeseries, light_theme)

        assert svg.startswith("<?xml") or svg.startswith("<svg")
        assert "</svg>" in svg

    def test_includes_svg_namespace(self, sample_timeseries, light_theme):
        """SVG includes xmlns namespace."""
        svg = render_chart_svg(sample_timeseries, light_theme)

        assert 'xmlns="http://www.w3.org/2000/svg"' in svg

    def test_respects_width_height(self, sample_timeseries, light_theme):
        """SVG respects specified dimensions."""
        svg = render_chart_svg(sample_timeseries, light_theme, width=600, height=200)

        # Check viewBox or dimensions in SVG attributes
        assert "600" in svg or "viewBox" in svg

    def test_uses_theme_colors(self, sample_timeseries, light_theme, dark_theme):
        """Different themes produce different colors."""
        light_svg = render_chart_svg(sample_timeseries, light_theme)
        dark_svg = render_chart_svg(sample_timeseries, dark_theme)

        # Check theme colors are present
        assert light_theme.line in light_svg or f"#{light_theme.line}" in light_svg
        assert dark_theme.line in dark_svg or f"#{dark_theme.line}" in dark_svg


class TestEmptyChartRendering:
    """Tests for rendering empty charts."""

    def test_empty_chart_renders(self, empty_timeseries, light_theme):
        """Empty time series renders without error."""
        svg = render_chart_svg(empty_timeseries, light_theme)

        assert "</svg>" in svg

    def test_empty_chart_shows_message(self, empty_timeseries, light_theme):
        """Empty chart shows 'No data available' message."""
        svg = render_chart_svg(empty_timeseries, light_theme)

        assert "No data available" in svg


class TestDataPointsInjection:
    """Tests for data-points attribute injection."""

    def test_includes_data_points(self, sample_timeseries, light_theme):
        """SVG includes data-points attribute."""
        svg = render_chart_svg(sample_timeseries, light_theme)

        assert "data-points=" in svg

    def test_data_points_valid_json(self, sample_timeseries, light_theme):
        """data-points contains valid JSON array."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        data = extract_svg_data_attributes(svg)

        assert "points" in data
        assert isinstance(data["points"], list)

    def test_data_points_count_matches(self, sample_timeseries, light_theme):
        """data-points count matches time series points."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        data = extract_svg_data_attributes(svg)

        assert len(data["points"]) == len(sample_timeseries.points)

    def test_data_points_structure(self, sample_timeseries, light_theme):
        """Each data point has ts and v keys."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        data = extract_svg_data_attributes(svg)

        for point in data["points"]:
            assert "ts" in point
            assert "v" in point

    def test_includes_metadata_attributes(self, sample_timeseries, light_theme):
        """SVG includes metric, period, theme attributes."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        data = extract_svg_data_attributes(svg)

        assert data.get("metric") == "bat"
        assert data.get("period") == "day"
        assert data.get("theme") == "light"

    def test_includes_axis_range_attributes(self, sample_timeseries, light_theme):
        """SVG includes x and y axis range attributes."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        data = extract_svg_data_attributes(svg)

        assert "x_start" in data
        assert "x_end" in data
        assert "y_min" in data
        assert "y_max" in data


class TestYAxisLimits:
    """Tests for Y-axis limit handling."""

    def test_fixed_y_limits(self, sample_timeseries, light_theme):
        """Fixed Y limits are applied."""
        svg = render_chart_svg(
            sample_timeseries, light_theme,
            y_min=3.0, y_max=4.5
        )
        data = extract_svg_data_attributes(svg)

        assert float(data["y_min"]) == 3.0
        assert float(data["y_max"]) == 4.5

    def test_auto_y_limits_with_padding(self, light_theme):
        """Auto Y limits add padding around data."""
        now = datetime.now()
        points = [
            DataPoint(timestamp=now, value=10.0),
            DataPoint(timestamp=now + timedelta(hours=1), value=20.0),
        ]
        ts = TimeSeries(metric="test", role="repeater", period="day", points=points)

        svg = render_chart_svg(ts, light_theme)
        data = extract_svg_data_attributes(svg)

        y_min = float(data["y_min"])
        y_max = float(data["y_max"])

        # Auto limits should extend beyond data range
        assert y_min < 10.0
        assert y_max > 20.0


class TestXAxisLimits:
    """Tests for X-axis limit handling."""

    def test_fixed_x_limits(self, sample_timeseries, light_theme):
        """Fixed X limits are applied."""
        x_start = datetime(2024, 1, 1, 0, 0, 0)
        x_end = datetime(2024, 1, 2, 0, 0, 0)

        svg = render_chart_svg(
            sample_timeseries, light_theme,
            x_start=x_start, x_end=x_end
        )
        data = extract_svg_data_attributes(svg)

        assert int(data["x_start"]) == int(x_start.timestamp())
        assert int(data["x_end"]) == int(x_end.timestamp())


class TestChartThemes:
    """Tests for chart theme constants."""

    def test_light_theme_exists(self):
        """Light theme is defined."""
        assert "light" in CHART_THEMES

    def test_dark_theme_exists(self):
        """Dark theme is defined."""
        assert "dark" in CHART_THEMES

    def test_themes_have_required_colors(self):
        """Themes have all required color attributes."""
        required = ["background", "canvas", "text", "axis", "grid", "line", "area"]

        for theme in CHART_THEMES.values():
            for attr in required:
                assert hasattr(theme, attr), f"Theme missing {attr}"
                assert getattr(theme, attr), f"Theme {attr} is empty"

    def test_theme_colors_are_valid_hex(self):
        """Theme colors are valid hex strings."""
        import re
        hex_pattern = re.compile(r'^[0-9a-fA-F]{6,8}$')

        for name, theme in CHART_THEMES.items():
            for attr in ["background", "canvas", "text", "axis", "grid", "line", "area"]:
                color = getattr(theme, attr)
                assert hex_pattern.match(color), f"{name}.{attr} = {color} is not valid hex"


class TestSvgNormalization:
    """Tests for SVG snapshot normalization helper."""

    def test_normalize_removes_matplotlib_ids(self, sample_timeseries, light_theme):
        """Normalization removes matplotlib-generated IDs."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        normalized = normalize_svg_for_snapshot(svg)

        # Should not have matplotlib's randomized IDs
        import re
        # Look for patterns like id="abc123-def456"
        random_ids = re.findall(r'id="[a-z0-9]+-[0-9a-f]{8,}"', normalized)
        assert len(random_ids) == 0

    def test_normalize_preserves_data_attributes(self, sample_timeseries, light_theme):
        """Normalization preserves data-* attributes."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        normalized = normalize_svg_for_snapshot(svg)

        assert "data-metric=" in normalized
        assert "data-points=" in normalized

    def test_normalize_removes_matplotlib_comment(self, sample_timeseries, light_theme):
        """Normalization removes matplotlib version comment."""
        svg = render_chart_svg(sample_timeseries, light_theme)
        normalized = normalize_svg_for_snapshot(svg)

        assert "Created with matplotlib" not in normalized
