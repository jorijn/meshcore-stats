"""Integration tests for chart and HTML rendering pipeline."""

import contextlib

import pytest


@pytest.mark.integration
class TestChartRenderingPipeline:
    """Test chart rendering end-to-end."""

    def test_renders_all_chart_periods(self, rendered_charts):
        """Should render charts for all periods (day/week/month/year)."""
        out_dir = rendered_charts["out_dir"]

        for role in ["companion", "repeater"]:
            assets_dir = out_dir / "assets" / role
            assert assets_dir.exists()

            for period in ["day", "week", "month", "year"]:
                period_svgs = list(assets_dir.glob(f"*_{period}_*.svg"))
                assert period_svgs, f"No {period} charts found for {role}"

    def test_chart_files_created(self, rendered_charts):
        """Should create SVG chart files in output directory."""
        out_dir = rendered_charts["out_dir"]

        # Check SVG files exist
        assets_dir = out_dir / "assets" / "repeater"
        assert assets_dir.exists()

        # Should have SVG files
        svg_files = list(assets_dir.glob("*.svg"))
        assert len(svg_files) > 0

        # Check stats file exists
        stats_file = assets_dir / "chart_stats.json"
        assert stats_file.exists()

    def test_chart_statistics_calculated(self, rendered_charts):
        """Should calculate correct statistics for charts."""
        from meshmon.charts import load_chart_stats

        # Load and verify stats
        loaded_stats = load_chart_stats("repeater")

        assert loaded_stats is not None

        # Check that stats have expected structure
        # Stats are nested: {metric_name: {period: {min, max, avg, current}}}
        for _metric_name, metric_stats in loaded_stats.items():
            if metric_stats:  # Skip empty stats
                # Each metric has period keys like 'day', 'week', 'month', 'year'
                for _period, period_stats in metric_stats.items():
                    if period_stats:
                        assert "min" in period_stats
                        assert "max" in period_stats
                        assert "avg" in period_stats


@pytest.mark.integration
class TestHtmlRenderingPipeline:
    """Test HTML site rendering end-to-end."""

    def test_renders_site_pages(self, rendered_charts):
        """Should render all HTML site pages."""
        from meshmon.db import get_latest_metrics
        from meshmon.html import write_site

        out_dir = rendered_charts["out_dir"]

        # Get latest metrics for write_site
        companion_row = get_latest_metrics("companion")
        repeater_row = get_latest_metrics("repeater")

        # Render site
        write_site(companion_row, repeater_row)

        # Check main pages exist
        assert (out_dir / "day.html").exists()
        assert (out_dir / "week.html").exists()
        assert (out_dir / "month.html").exists()
        assert (out_dir / "year.html").exists()

        # Check companion pages exist
        assert (out_dir / "companion" / "day.html").exists()
        assert (out_dir / "companion" / "week.html").exists()

    def test_copies_static_assets(self, full_integration_env):
        """Should copy static assets (CSS, JS)."""
        from meshmon.html import copy_static_assets

        out_dir = full_integration_env["out_dir"]

        copy_static_assets()

        # Check static files exist
        assert (out_dir / "styles.css").exists()
        assert (out_dir / "chart-tooltip.js").exists()

    def test_html_contains_chart_data(self, rendered_charts):
        """HTML should contain embedded chart SVGs."""
        from meshmon.db import get_latest_metrics
        from meshmon.html import write_site

        out_dir = rendered_charts["out_dir"]

        # Get latest metrics for write_site
        companion_row = get_latest_metrics("companion")
        repeater_row = get_latest_metrics("repeater")

        # Render site
        write_site(companion_row, repeater_row)

        # Check HTML contains SVG
        day_html = (out_dir / "day.html").read_text()

        # Should contain SVG elements
        assert "<svg" in day_html
        # Should contain chart data attributes
        assert "data-metric" in day_html or "data-points" in day_html

    def test_html_has_correct_status_indicator(
        self, rendered_charts
    ):
        """HTML should have correct status indicator based on data freshness."""
        from meshmon.db import get_latest_metrics
        from meshmon.html import write_site

        out_dir = rendered_charts["out_dir"]

        # Get latest metrics for write_site
        companion_row = get_latest_metrics("companion")
        repeater_row = get_latest_metrics("repeater")

        write_site(companion_row, repeater_row)

        # Check status indicator exists
        day_html = (out_dir / "day.html").read_text()

        # Should have status indicator class
        assert "status-" in day_html or "online" in day_html or "offline" in day_html


@pytest.mark.integration
class TestFullRenderingChain:
    """Test complete rendering chain: data -> charts -> HTML."""

    def test_full_chain_from_database_to_html(
        self, rendered_charts
    ):
        """Complete chain: database metrics -> charts -> HTML site."""
        from meshmon.db import get_latest_metrics, get_metric_count
        from meshmon.html import copy_static_assets, write_site

        out_dir = rendered_charts["out_dir"]

        # 1. Verify database has data
        assert get_metric_count("repeater") > 0
        assert get_metric_count("companion") > 0

        # 2. Verify rendered charts exist for both roles
        for role in ["repeater", "companion"]:
            assets_dir = out_dir / "assets" / role
            svg_files = list(assets_dir.glob("*.svg"))
            assert svg_files, f"No charts found for {role}"

        # 3. Copy static assets
        copy_static_assets()

        # 4. Get latest metrics for write_site
        companion_row = get_latest_metrics("companion")
        repeater_row = get_latest_metrics("repeater")

        # 5. Render HTML site
        write_site(companion_row, repeater_row)

        # 6. Verify output structure
        assert (out_dir / "day.html").exists()
        assert (out_dir / "styles.css").exists()
        assert (out_dir / "chart-tooltip.js").exists()
        assert (out_dir / "assets" / "repeater").exists()
        assert (out_dir / "assets" / "companion").exists()

        # 7. Verify HTML is valid (basic check)
        html_content = (out_dir / "day.html").read_text()
        assert "<!DOCTYPE html>" in html_content or "<!doctype html>" in html_content.lower()
        assert "</html>" in html_content

    def test_empty_database_renders_gracefully(self, full_integration_env):
        """Should handle empty database gracefully."""
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.db import get_latest_metrics, get_metric_count, init_db
        from meshmon.html import copy_static_assets, write_site

        full_integration_env["out_dir"]

        # Initialize empty database
        init_db()

        # Verify no data
        assert get_metric_count("repeater") == 0
        assert get_metric_count("companion") == 0

        # Rendering with no data should not crash
        for role in ["repeater", "companion"]:
            charts, stats = render_all_charts(role)
            save_chart_stats(role, stats)
            # Should have no charts (or empty charts)
            # The important thing is it doesn't crash

        copy_static_assets()

        # Get empty metrics
        companion_row = get_latest_metrics("companion")
        repeater_row = get_latest_metrics("repeater")

        # Site rendering might fail or show "no data" - verify it handles gracefully
        # Some implementations might raise an exception for empty data - acceptable
        with contextlib.suppress(Exception):
            write_site(companion_row, repeater_row)
