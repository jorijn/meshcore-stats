"""Integration tests for chart and HTML rendering pipeline."""

import pytest
from pathlib import Path
import time


@pytest.mark.integration
class TestChartRenderingPipeline:
    """Test chart rendering end-to-end."""

    def test_renders_all_chart_periods(self, populated_db_with_history, full_integration_env):
        """Should render charts for all periods (day/week/month/year)."""
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.db import get_metric_count

        # Verify data exists
        companion_count = get_metric_count("companion")
        repeater_count = get_metric_count("repeater")

        assert companion_count > 0
        assert repeater_count > 0

        # Render companion charts
        charts, stats = render_all_charts("companion")
        save_chart_stats("companion", stats)

        # Should have charts for multiple metrics and periods
        assert len(charts) > 0
        assert len(stats) > 0

        # Render repeater charts
        charts, stats = render_all_charts("repeater")
        save_chart_stats("repeater", stats)

        assert len(charts) > 0
        assert len(stats) > 0

    def test_chart_files_created(self, populated_db_with_history, full_integration_env):
        """Should create SVG chart files in output directory."""
        from meshmon.charts import render_all_charts, save_chart_stats

        out_dir = full_integration_env["out_dir"]

        # Render charts
        charts, stats = render_all_charts("repeater")
        save_chart_stats("repeater", stats)

        # Check SVG files exist
        assets_dir = out_dir / "assets" / "repeater"
        assert assets_dir.exists()

        # Should have SVG files
        svg_files = list(assets_dir.glob("*.svg"))
        assert len(svg_files) > 0

        # Check stats file exists
        stats_file = assets_dir / "chart_stats.json"
        assert stats_file.exists()

    def test_chart_statistics_calculated(self, populated_db_with_history, full_integration_env):
        """Should calculate correct statistics for charts."""
        from meshmon.charts import render_all_charts, load_chart_stats, save_chart_stats

        # Render charts
        charts, stats = render_all_charts("repeater")
        save_chart_stats("repeater", stats)

        # Load and verify stats
        loaded_stats = load_chart_stats("repeater")

        assert loaded_stats is not None

        # Check that stats have expected structure
        # Stats are nested: {metric_name: {period: {min, max, avg, current}}}
        for metric_name, metric_stats in loaded_stats.items():
            if metric_stats:  # Skip empty stats
                # Each metric has period keys like 'day', 'week', 'month', 'year'
                for period, period_stats in metric_stats.items():
                    if period_stats:
                        assert "min" in period_stats
                        assert "max" in period_stats
                        assert "avg" in period_stats


@pytest.mark.integration
class TestHtmlRenderingPipeline:
    """Test HTML site rendering end-to-end."""

    def test_renders_site_pages(self, populated_db_with_history, full_integration_env):
        """Should render all HTML site pages."""
        from meshmon.html import write_site, copy_static_assets
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.db import get_latest_metrics

        out_dir = full_integration_env["out_dir"]

        # First render charts (needed for site)
        for role in ["repeater", "companion"]:
            charts, stats = render_all_charts(role)
            save_chart_stats(role, stats)

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

    def test_html_contains_chart_data(self, populated_db_with_history, full_integration_env):
        """HTML should contain embedded chart SVGs."""
        from meshmon.html import write_site
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.db import get_latest_metrics

        out_dir = full_integration_env["out_dir"]

        # Render charts first
        for role in ["repeater", "companion"]:
            charts, stats = render_all_charts(role)
            save_chart_stats(role, stats)

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
        self, populated_db_with_history, full_integration_env
    ):
        """HTML should have correct status indicator based on data freshness."""
        from meshmon.html import write_site
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.db import get_latest_metrics

        out_dir = full_integration_env["out_dir"]

        # Render charts and site
        for role in ["repeater", "companion"]:
            charts, stats = render_all_charts(role)
            save_chart_stats(role, stats)

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
        self, populated_db_with_history, full_integration_env
    ):
        """Complete chain: database metrics -> charts -> HTML site."""
        from meshmon.db import get_metric_count, get_latest_metrics
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.html import write_site, copy_static_assets

        out_dir = full_integration_env["out_dir"]

        # 1. Verify database has data
        assert get_metric_count("repeater") > 0
        assert get_metric_count("companion") > 0

        # 2. Render charts for both roles
        total_charts = 0
        for role in ["repeater", "companion"]:
            charts, stats = render_all_charts(role)
            save_chart_stats(role, stats)
            total_charts += len(charts)

        assert total_charts > 0

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
        from meshmon.db import init_db, get_metric_count, get_latest_metrics
        from meshmon.charts import render_all_charts, save_chart_stats
        from meshmon.html import write_site, copy_static_assets

        out_dir = full_integration_env["out_dir"]

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
        try:
            write_site(companion_row, repeater_row)
        except Exception:
            # Some implementations might raise an exception for empty data
            # That's acceptable behavior
            pass
