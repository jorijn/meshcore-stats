"""Integration tests for report generation pipeline."""

import calendar
import json
from datetime import datetime

import pytest

BASE_TS = 1704067200


@pytest.mark.integration
class TestReportGenerationPipeline:
    """Test report generation end-to-end."""

    def test_generates_monthly_reports(self, populated_db_with_history, reports_env):
        """Should generate monthly reports for available data."""
        from meshmon.html import render_report_page
        from meshmon.reports import aggregate_monthly, format_monthly_txt, get_available_periods

        # Get available periods
        periods = get_available_periods("repeater")
        assert periods

        # Get the current month (should have data)
        year, month = periods[-1]
        month_name = calendar.month_name[month]

        # Aggregate monthly data
        agg = aggregate_monthly("repeater", year, month)

        assert agg is not None
        assert agg.year == year
        assert agg.month == month
        assert agg.role == "repeater"
        assert agg.daily
        assert agg.summary["bat"].count > 0
        assert agg.summary["bat"].min_value is not None
        assert agg.summary["nb_recv"].total is not None
        assert agg.summary["nb_recv"].count > 0

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
        assert f"MONTHLY MESHCORE REPORT for {month_name} {year}" in txt_report
        assert "NODE: Test Repeater" in txt_report
        assert "NAME: Test Location" in txt_report

        # Generate HTML report
        html_report = render_report_page(agg, "Test Repeater", "monthly")

        assert html_report is not None
        assert "<html" in html_report.lower()
        assert f"{month_name} {year}" in html_report
        assert "Test Repeater" in html_report

    def test_generates_yearly_reports(self, populated_db_with_history, reports_env):
        """Should generate yearly reports for available data."""
        from meshmon.html import render_report_page
        from meshmon.reports import aggregate_yearly, format_yearly_txt, get_available_periods

        # Get available periods
        periods = get_available_periods("repeater")
        assert len(periods) > 0

        # Get the current year
        year = periods[-1][0]

        # Aggregate yearly data
        agg = aggregate_yearly("repeater", year)

        assert agg is not None
        assert agg.year == year
        assert agg.role == "repeater"
        assert agg.monthly
        assert agg.summary["bat"].count > 0
        assert agg.summary["nb_recv"].total is not None

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
        assert f"YEARLY MESHCORE REPORT for {year}" in txt_report
        assert "NODE: Test Repeater" in txt_report

        # Generate HTML report
        html_report = render_report_page(agg, "Test Repeater", "yearly")

        assert html_report is not None
        assert "<html" in html_report.lower()
        assert "Yearly report for Test Repeater" in html_report

    def test_generates_json_reports(self, populated_db_with_history, reports_env):
        """Should generate valid JSON reports."""
        from meshmon.reports import (
            aggregate_monthly,
            aggregate_yearly,
            get_available_periods,
            monthly_to_json,
            yearly_to_json,
        )

        periods = get_available_periods("repeater")
        year, month = periods[-1]

        # Monthly JSON
        monthly_agg = aggregate_monthly("repeater", year, month)
        monthly_json = monthly_to_json(monthly_agg)

        assert monthly_json is not None
        assert monthly_json["report_type"] == "monthly"
        assert "year" in monthly_json
        assert "month" in monthly_json
        assert monthly_json["role"] == "repeater"
        assert monthly_json["days_with_data"] == len(monthly_agg.daily)
        assert "daily" in monthly_json
        assert "bat" in monthly_json["summary"]

        # Verify it's valid JSON
        json_str = json.dumps(monthly_json)
        parsed = json.loads(json_str)
        assert parsed == monthly_json

        # Yearly JSON
        yearly_agg = aggregate_yearly("repeater", year)
        yearly_json = yearly_to_json(yearly_agg)

        assert yearly_json is not None
        assert yearly_json["report_type"] == "yearly"
        assert "year" in yearly_json
        assert yearly_json["role"] == "repeater"
        assert yearly_json["months_with_data"] == len(yearly_agg.monthly)
        assert "monthly" in yearly_json
        assert "bat" in yearly_json["summary"]

    def test_report_files_created(self, populated_db_with_history, reports_env):
        """Should create report files in correct directory structure."""
        from meshmon.html import render_report_page
        from meshmon.reports import (
            LocationInfo,
            aggregate_monthly,
            format_monthly_txt,
            get_available_periods,
            monthly_to_json,
        )

        out_dir = reports_env["out_dir"]

        periods = get_available_periods("repeater")
        year, month = periods[-1]
        month_name = calendar.month_name[month]

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

        (report_dir / "index.html").write_text(html, encoding="utf-8")
        (report_dir / "report.txt").write_text(txt, encoding="utf-8")
        (report_dir / "report.json").write_text(json.dumps(json_data), encoding="utf-8")

        # Verify files exist
        assert (report_dir / "index.html").exists()
        assert (report_dir / "report.txt").exists()
        assert (report_dir / "report.json").exists()

        # Verify content is not empty
        assert len((report_dir / "index.html").read_text()) > 0
        assert len((report_dir / "report.txt").read_text()) > 0
        assert len((report_dir / "report.json").read_text()) > 0
        assert f"{month_name} {year}" in (report_dir / "index.html").read_text()
        assert "NODE: Test Repeater" in (report_dir / "report.txt").read_text()

        parsed_json = json.loads((report_dir / "report.json").read_text())
        assert parsed_json["report_type"] == "monthly"
        assert parsed_json["year"] == year
        assert parsed_json["month"] == month


@pytest.mark.integration
class TestReportsIndex:
    """Test reports index page generation."""

    def test_generates_reports_index(self, populated_db_with_history, reports_env):
        """Should generate reports index with all available periods."""
        from meshmon.html import render_reports_index
        from meshmon.reports import get_available_periods

        out_dir = reports_env["out_dir"]

        # Build sections data (mimicking render_reports.py)
        sections = []
        latest_periods: dict[str, tuple[int, int]] = {}
        for role in ["repeater", "companion"]:
            periods = get_available_periods(role)

            if not periods:
                sections.append({"role": role, "years": []})
                continue
            latest_periods[role] = periods[-1]

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
        assert "reports archive" in html.lower()

        for role, (year, month) in latest_periods.items():
            assert f"../reports/{role}/{year}/" in html
            assert f"../reports/{role}/{year}/{month:02d}/" in html

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
        from meshmon.reports import aggregate_daily

        init_db()

        # Insert data with a simulated reboot
        day_start = BASE_TS - (BASE_TS % 86400)

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
        assert agg.snapshot_count == 16
        stats = agg.metrics["nb_recv"]
        assert stats.count == 16
        assert stats.reboot_count == 1
        assert stats.total == 170

    def test_gauge_aggregation_computes_stats(self, full_integration_env):
        """Gauge metrics should compute min/max/avg correctly."""
        from meshmon.db import init_db, insert_metrics
        from meshmon.reports import aggregate_daily

        init_db()

        day_start = BASE_TS - (BASE_TS % 86400)

        # Insert battery readings with known pattern
        values = [3.7, 3.8, 3.9, 4.0, 3.85]  # min=3.7, max_value=4.0, avg≈3.85
        for i, val in enumerate(values):
            ts = day_start + i * 3600
            insert_metrics(ts, "repeater", {"bat": val * 1000})  # Store in mV

        dt = datetime.fromtimestamp(day_start)
        agg = aggregate_daily("repeater", dt.date())

        assert agg is not None
        assert agg.snapshot_count == len(values)
        stats = agg.metrics["bat"]
        assert stats.count == len(values)
        assert stats.min_value == 3700.0
        assert stats.max_value == 4000.0
        assert stats.mean == pytest.approx(3850.0)
        assert stats.min_time == datetime.fromtimestamp(day_start)
        assert stats.max_time == datetime.fromtimestamp(day_start + 3 * 3600)


@pytest.mark.integration
class TestReportConsistency:
    """Test consistency across different report formats."""

    def test_txt_json_html_contain_same_data(
        self, populated_db_with_history, reports_env
    ):
        """TXT, JSON, and HTML reports should contain consistent data."""
        from meshmon.html import render_report_page
        from meshmon.reports import (
            LocationInfo,
            aggregate_monthly,
            format_monthly_txt,
            get_available_periods,
            monthly_to_json,
        )

        periods = get_available_periods("repeater")
        year, month = periods[-1]

        agg = aggregate_monthly("repeater", year, month)
        location = LocationInfo(name="Test", lat=52.0, lon=4.0, elev=10.0)

        txt = format_monthly_txt(agg, "Test Repeater", location)
        json_data = monthly_to_json(agg)
        html = render_report_page(agg, "Test Repeater", "monthly")

        # All should reference the same year/month
        month_name = calendar.month_name[month]
        assert str(year) in txt
        assert json_data["year"] == year
        assert json_data["month"] == month
        assert json_data["role"] == "repeater"
        assert json_data["report_type"] == "monthly"
        assert str(year) in html
        assert f"{month_name} {year}" in html

        # All should have the same number of days
        num_days = len(agg.daily)
        assert len(json_data["daily"]) == num_days
        assert json_data["days_with_data"] == num_days
