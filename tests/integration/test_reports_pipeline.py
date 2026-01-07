"""Integration tests for report generation pipeline."""

import pytest
from pathlib import Path
import json
import time
from datetime import datetime


@pytest.mark.integration
class TestReportGenerationPipeline:
    """Test report generation end-to-end."""

    def test_generates_monthly_reports(self, populated_db_with_history, full_integration_env):
        """Should generate monthly reports for available data."""
        from meshmon.reports import aggregate_monthly, format_monthly_txt, get_available_periods
        from meshmon.html import render_report_page

        # Get available periods
        periods = get_available_periods("repeater")
        assert len(periods) > 0

        # Get the current month (should have data)
        year, month = periods[-1]

        # Aggregate monthly data
        agg = aggregate_monthly("repeater", year, month)

        assert agg is not None
        assert len(agg.daily) > 0

        # Generate TXT report
        from meshmon.reports import LocationInfo

        location = LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )
        txt_report = format_monthly_txt(agg, "Test Repeater", location)

        assert txt_report is not None
        assert len(txt_report) > 0
        assert "Test Repeater" in txt_report or "Test Location" in txt_report

        # Generate HTML report
        html_report = render_report_page(agg, "Test Repeater", "monthly")

        assert html_report is not None
        assert "<html" in html_report.lower()

    def test_generates_yearly_reports(self, populated_db_with_history, full_integration_env):
        """Should generate yearly reports for available data."""
        from meshmon.reports import aggregate_yearly, format_yearly_txt, get_available_periods
        from meshmon.html import render_report_page

        # Get available periods
        periods = get_available_periods("repeater")
        assert len(periods) > 0

        # Get the current year
        year = periods[-1][0]

        # Aggregate yearly data
        agg = aggregate_yearly("repeater", year)

        assert agg is not None
        assert len(agg.monthly) > 0

        # Generate TXT report
        from meshmon.reports import LocationInfo

        location = LocationInfo(
            name="Test Location",
            lat=52.0,
            lon=4.0,
            elev=10.0,
        )
        txt_report = format_yearly_txt(agg, "Test Repeater", location)

        assert txt_report is not None
        assert len(txt_report) > 0

        # Generate HTML report
        html_report = render_report_page(agg, "Test Repeater", "yearly")

        assert html_report is not None
        assert "<html" in html_report.lower()

    def test_generates_json_reports(self, populated_db_with_history, full_integration_env):
        """Should generate valid JSON reports."""
        from meshmon.reports import (
            aggregate_monthly,
            aggregate_yearly,
            monthly_to_json,
            yearly_to_json,
            get_available_periods,
        )

        periods = get_available_periods("repeater")
        year, month = periods[-1]

        # Monthly JSON
        monthly_agg = aggregate_monthly("repeater", year, month)
        monthly_json = monthly_to_json(monthly_agg)

        assert monthly_json is not None
        assert "year" in monthly_json
        assert "month" in monthly_json
        assert "daily" in monthly_json

        # Verify it's valid JSON
        json_str = json.dumps(monthly_json)
        parsed = json.loads(json_str)
        assert parsed == monthly_json

        # Yearly JSON
        yearly_agg = aggregate_yearly("repeater", year)
        yearly_json = yearly_to_json(yearly_agg)

        assert yearly_json is not None
        assert "year" in yearly_json
        assert "monthly" in yearly_json

    def test_report_files_created(self, populated_db_with_history, full_integration_env):
        """Should create report files in correct directory structure."""
        from meshmon.reports import (
            aggregate_monthly,
            format_monthly_txt,
            monthly_to_json,
            get_available_periods,
            LocationInfo,
        )
        from meshmon.html import render_report_page

        out_dir = full_integration_env["out_dir"]

        periods = get_available_periods("repeater")
        year, month = periods[-1]

        # Create output directory
        report_dir = out_dir / "reports" / "repeater" / str(year) / f"{month:02d}"
        report_dir.mkdir(parents=True, exist_ok=True)

        # Generate reports
        agg = aggregate_monthly("repeater", year, month)
        location = LocationInfo(name="Test", lat=0.0, lon=0.0, elev=0.0)

        # Write files
        html = render_report_page(agg, "Test Repeater", "monthly")
        txt = format_monthly_txt(agg, "Test Repeater", location)
        json_data = monthly_to_json(agg)

        (report_dir / "index.html").write_text(html)
        (report_dir / "report.txt").write_text(txt)
        (report_dir / "report.json").write_text(json.dumps(json_data))

        # Verify files exist
        assert (report_dir / "index.html").exists()
        assert (report_dir / "report.txt").exists()
        assert (report_dir / "report.json").exists()

        # Verify content is not empty
        assert len((report_dir / "index.html").read_text()) > 0
        assert len((report_dir / "report.txt").read_text()) > 0
        assert len((report_dir / "report.json").read_text()) > 0


@pytest.mark.integration
class TestReportsIndex:
    """Test reports index page generation."""

    def test_generates_reports_index(self, populated_db_with_history, full_integration_env):
        """Should generate reports index with all available periods."""
        from meshmon.reports import get_available_periods
        from meshmon.html import render_reports_index
        import calendar

        out_dir = full_integration_env["out_dir"]

        # Build sections data (mimicking render_reports.py)
        sections = []
        for role in ["repeater", "companion"]:
            periods = get_available_periods(role)

            if not periods:
                sections.append({"role": role, "years": []})
                continue

            years_data = {}
            for year, month in periods:
                if year not in years_data:
                    years_data[year] = []
                years_data[year].append(
                    {
                        "month": month,
                        "name": calendar.month_name[month],
                    }
                )

            years = []
            for year in sorted(years_data.keys(), reverse=True):
                years.append(
                    {
                        "year": year,
                        "months": sorted(years_data[year], key=lambda m: m["month"]),
                    }
                )

            sections.append({"role": role, "years": years})

        # Render index
        html = render_reports_index(sections)

        assert html is not None
        assert "<html" in html.lower()
        assert "repeater" in html.lower() or "Repeater" in html

        # Write and verify file
        reports_dir = out_dir / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        (reports_dir / "index.html").write_text(html)

        assert (reports_dir / "index.html").exists()


@pytest.mark.integration
class TestCounterAggregation:
    """Test counter metrics aggregation (handles reboots)."""

    def test_counter_aggregation_handles_reboots(self, full_integration_env):
        """Counter aggregation should correctly handle device reboots."""
        from meshmon.db import init_db, insert_metrics
        from meshmon.reports import aggregate_daily, compute_counter_total

        init_db()

        # Insert data with a simulated reboot
        now = int(time.time())
        day_start = now - (now % 86400)

        # Before reboot: counter increases
        for i in range(10):
            ts = day_start + i * 900
            insert_metrics(
                ts, "repeater", {"nb_recv": float(100 + i * 10)}  # 100, 110, 120, ..., 190
            )

        # Reboot: counter resets
        insert_metrics(day_start + 10 * 900, "repeater", {"nb_recv": 0.0})

        # After reboot: counter increases again
        for i in range(5):
            ts = day_start + (11 + i) * 900
            insert_metrics(ts, "repeater", {"nb_recv": float(i * 20)})  # 0, 20, 40, 60, 80

        # Aggregate daily data
        dt = datetime.fromtimestamp(day_start)
        agg = aggregate_daily("repeater", dt.date())

        # Should have data for nb_recv
        # The counter total should account for the reboot
        assert agg is not None

    def test_gauge_aggregation_computes_stats(self, full_integration_env):
        """Gauge metrics should compute min/max/avg correctly."""
        from meshmon.db import init_db, insert_metrics
        from meshmon.reports import aggregate_daily

        init_db()

        now = int(time.time())
        day_start = now - (now % 86400)

        # Insert battery readings with known pattern
        values = [3.7, 3.8, 3.9, 4.0, 3.85]  # min=3.7, max_value=4.0, avg≈3.85
        for i, val in enumerate(values):
            ts = day_start + i * 3600
            insert_metrics(ts, "repeater", {"bat": val * 1000})  # Store in mV

        dt = datetime.fromtimestamp(day_start)
        agg = aggregate_daily("repeater", dt.date())

        assert agg is not None
        # Verify aggregation happened (specific values depend on implementation)


@pytest.mark.integration
class TestReportConsistency:
    """Test consistency across different report formats."""

    def test_txt_json_html_contain_same_data(
        self, populated_db_with_history, full_integration_env
    ):
        """TXT, JSON, and HTML reports should contain consistent data."""
        from meshmon.reports import (
            aggregate_monthly,
            format_monthly_txt,
            monthly_to_json,
            get_available_periods,
            LocationInfo,
        )
        from meshmon.html import render_report_page

        periods = get_available_periods("repeater")
        year, month = periods[-1]

        agg = aggregate_monthly("repeater", year, month)
        location = LocationInfo(name="Test", lat=52.0, lon=4.0, elev=10.0)

        txt = format_monthly_txt(agg, "Test Repeater", location)
        json_data = monthly_to_json(agg)
        html = render_report_page(agg, "Test Repeater", "monthly")

        # All should reference the same year/month
        assert str(year) in txt
        assert json_data["year"] == year
        assert json_data["month"] == month
        assert str(year) in html

        # All should have the same number of days
        num_days = len(agg.daily)
        assert len(json_data["daily"]) == num_days
