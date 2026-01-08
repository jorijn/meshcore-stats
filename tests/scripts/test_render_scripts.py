"""Tests for render script entry points.

These tests verify the render_charts.py, render_site.py, and render_reports.py
scripts can be imported and their main() functions work correctly.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tests.scripts.conftest import load_script_module


def load_script(script_name: str):
    """Load a script as a module."""
    return load_script_module(script_name)


class TestRenderChartsImport:
    """Verify render_charts.py imports correctly."""

    def test_imports_successfully(self, configured_env):
        """Script should import without errors."""
        module = load_script("render_charts.py")

        assert hasattr(module, "main")
        assert callable(module.main)

    def test_main_calls_init_db(self, configured_env):
        """main() should initialize database."""
        module = load_script("render_charts.py")

        with patch.object(module, "init_db") as mock_init:
            with patch.object(module, "get_metric_count", return_value=0):
                module.main()

                mock_init.assert_called_once()

    def test_main_checks_metric_counts(self, configured_env):
        """main() should check for data before rendering."""
        module = load_script("render_charts.py")

        with patch.object(module, "init_db"):
            with patch.object(module, "get_metric_count") as mock_count:
                mock_count.return_value = 0

                module.main()

                # Should check both companion and repeater
                assert mock_count.call_count == 2

    def test_main_renders_when_data_exists(self, configured_env):
        """main() should render charts when data exists."""
        module = load_script("render_charts.py")

        with patch.object(module, "init_db"):
            with patch.object(module, "get_metric_count", return_value=100):
                with patch.object(module, "render_all_charts") as mock_render:
                    mock_render.return_value = (["chart1.svg"], {"bat": {}})
                    with patch.object(module, "save_chart_stats"):
                        module.main()

                        # Should render for both roles
                        assert mock_render.call_count == 2


class TestRenderSiteImport:
    """Verify render_site.py imports correctly."""

    def test_imports_successfully(self, configured_env):
        """Script should import without errors."""
        module = load_script("render_site.py")

        assert hasattr(module, "main")
        assert callable(module.main)

    def test_main_calls_init_db(self, configured_env):
        """main() should initialize database."""
        module = load_script("render_site.py")

        with patch.object(module, "init_db") as mock_init:
            with patch.object(module, "get_latest_metrics", return_value=None):
                with patch.object(module, "write_site", return_value=[]):
                    module.main()

                    mock_init.assert_called_once()

    def test_main_loads_latest_metrics(self, configured_env):
        """main() should load latest metrics for both roles."""
        module = load_script("render_site.py")

        with patch.object(module, "init_db"):
            with patch.object(module, "get_latest_metrics") as mock_get:
                mock_get.return_value = {"battery_mv": 3850}
                with patch.object(module, "write_site", return_value=[]):
                    module.main()

                    # Should get metrics for both companion and repeater
                    assert mock_get.call_count == 2

    def test_main_calls_write_site(self, configured_env):
        """main() should call write_site with metrics."""
        module = load_script("render_site.py")

        companion_metrics = {"battery_mv": 3850, "ts": 12345}
        repeater_metrics = {"bat": 3900, "ts": 12346}

        with patch.object(module, "init_db"):
            with patch.object(module, "get_latest_metrics") as mock_get:
                mock_get.side_effect = [companion_metrics, repeater_metrics]
                with patch.object(module, "write_site") as mock_write:
                    mock_write.return_value = ["day.html", "week.html"]

                    module.main()

                    mock_write.assert_called_once_with(companion_metrics, repeater_metrics)

    def test_creates_html_files_for_all_periods(self, configured_env, initialized_db, tmp_path):
        """Should create HTML files for day/week/month/year periods."""
        module = load_script("render_site.py")
        out_dir = configured_env["out_dir"]

        # Use real write_site but mock the templates to avoid complex setup
        with patch.object(module, "init_db"):
            with patch.object(module, "get_latest_metrics") as mock_get:
                mock_get.return_value = {"battery_mv": 3850, "ts": 12345}
                # Let write_site run - it will create the files
                module.main()

        # Verify HTML files exist and have content
        for period in ["day", "week", "month", "year"]:
            html_file = out_dir / f"{period}.html"
            assert html_file.exists(), f"{period}.html should exist"
            content = html_file.read_text()
            assert len(content) > 0, f"{period}.html should have content"
            assert "<!DOCTYPE html>" in content or "<html" in content, f"{period}.html should be valid HTML"


class TestRenderReportsImport:
    """Verify render_reports.py imports correctly."""

    def test_imports_successfully(self, configured_env):
        """Script should import without errors."""
        module = load_script("render_reports.py")

        assert hasattr(module, "main")
        assert hasattr(module, "safe_write")
        assert hasattr(module, "get_node_name")
        assert hasattr(module, "get_location")
        assert hasattr(module, "render_monthly_report")
        assert hasattr(module, "render_yearly_report")
        assert hasattr(module, "build_reports_index_data")
        assert callable(module.main)

    def test_main_calls_init_db(self, configured_env):
        """main() should initialize database."""
        module = load_script("render_reports.py")

        with patch.object(module, "init_db") as mock_init:
            with patch.object(module, "get_available_periods", return_value=[]):
                with patch.object(module, "build_reports_index_data", return_value=[]):
                    with patch.object(module, "render_reports_index", return_value="<html>"):
                        with patch.object(module, "safe_write", return_value=True):
                            module.main()

                            mock_init.assert_called_once()

    def test_main_processes_both_roles(self, configured_env):
        """main() should process both repeater and companion."""
        module = load_script("render_reports.py")

        with patch.object(module, "init_db"):
            with patch.object(module, "get_available_periods") as mock_periods:
                mock_periods.return_value = []
                with patch.object(module, "build_reports_index_data", return_value=[]):
                    with patch.object(module, "render_reports_index", return_value="<html>"):
                        with patch.object(module, "safe_write", return_value=True):
                            module.main()

                            # Should check periods for both roles
                            assert mock_periods.call_count == 2


class TestRenderReportsHelpers:
    """Test helper functions in render_reports.py."""

    def test_safe_write_success(self, configured_env, tmp_path):
        """safe_write should return True on success."""
        module = load_script("render_reports.py")

        test_file = tmp_path / "test.txt"
        result = module.safe_write(test_file, "test content")

        assert result is True
        assert test_file.read_text() == "test content"

    def test_safe_write_fails_for_missing_parent_directories(self, configured_env, tmp_path):
        """safe_write should fail when parent directories don't exist (it doesn't create them)."""
        module = load_script("render_reports.py")

        # Parent directory doesn't exist
        test_file = tmp_path / "nested" / "dir" / "test.txt"
        result = module.safe_write(test_file, "nested content")

        # safe_write doesn't create parent dirs - it fails
        assert result is False
        assert not test_file.exists()

    def test_safe_write_works_with_existing_parent_directories(self, configured_env, tmp_path):
        """safe_write should work when parent directories exist."""
        module = load_script("render_reports.py")

        # Create parent directory first
        nested_dir = tmp_path / "existing" / "dir"
        nested_dir.mkdir(parents=True)
        test_file = nested_dir / "test.txt"
        result = module.safe_write(test_file, "nested content")

        assert result is True
        assert test_file.exists()
        assert test_file.read_text() == "nested content"

    def test_safe_write_failure(self, configured_env):
        """safe_write should return False on failure."""
        module = load_script("render_reports.py")

        # Try to write to non-existent directory that can't be created
        bad_path = Path("/nonexistent/dir/file.txt")
        result = module.safe_write(bad_path, "test content")

        assert result is False

    def test_get_node_name_repeater(self, configured_env, monkeypatch):
        """get_node_name should return display name for repeater."""
        monkeypatch.setenv("REPEATER_DISPLAY_NAME", "My Repeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        name = module.get_node_name("repeater")
        assert name == "My Repeater"

    def test_get_node_name_companion(self, configured_env, monkeypatch):
        """get_node_name should return display name for companion."""
        monkeypatch.setenv("COMPANION_DISPLAY_NAME", "My Companion")
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        name = module.get_node_name("companion")
        assert name == "My Companion"

    def test_get_node_name_unknown(self, configured_env):
        """get_node_name should capitalize unknown roles."""
        module = load_script("render_reports.py")

        name = module.get_node_name("unknown")
        assert name == "Unknown"

    def test_get_location(self, configured_env, monkeypatch):
        """get_location should return LocationInfo from config."""
        monkeypatch.setenv("REPORT_LOCATION_NAME", "Test Location")
        monkeypatch.setenv("REPORT_LAT", "52.37")
        monkeypatch.setenv("REPORT_LON", "4.89")
        monkeypatch.setenv("REPORT_ELEV", "10")
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        location = module.get_location()

        assert location.name == "Test Location"
        assert location.lat == 52.37
        assert location.lon == 4.89
        assert location.elev == 10

    def test_build_reports_index_data_empty(self, configured_env):
        """build_reports_index_data should return empty years for no data."""
        module = load_script("render_reports.py")

        with patch.object(module, "get_available_periods", return_value=[]):
            sections = module.build_reports_index_data()

            assert len(sections) == 2  # repeater and companion
            assert sections[0]["role"] == "repeater"
            assert sections[0]["years"] == []
            assert sections[1]["role"] == "companion"
            assert sections[1]["years"] == []

    def test_build_reports_index_data_with_periods(self, configured_env):
        """build_reports_index_data should organize periods by year."""
        module = load_script("render_reports.py")

        def mock_periods(role):
            if role == "repeater":
                return [(2024, 11), (2024, 12), (2025, 1)]
            return []

        with patch.object(module, "get_available_periods", side_effect=mock_periods):
            sections = module.build_reports_index_data()

            repeater_section = sections[0]
            assert repeater_section["role"] == "repeater"
            assert len(repeater_section["years"]) == 2  # 2024 and 2025

            # Years should be sorted descending
            assert repeater_section["years"][0]["year"] == 2025
            assert repeater_section["years"][1]["year"] == 2024


class TestRenderMonthlyReport:
    """Test render_monthly_report function."""

    def test_skips_empty_aggregation(self, configured_env):
        """Should skip when no data for the period."""
        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.daily = []  # No data

        with patch.object(module, "aggregate_monthly", return_value=mock_agg):
            with patch.object(module, "safe_write") as mock_write:
                module.render_monthly_report("repeater", 2024, 12)

                # Should not write any files
                mock_write.assert_not_called()

    def test_writes_all_formats(self, configured_env, tmp_path, monkeypatch):
        """Should write HTML, TXT, and JSON formats."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.daily = [{"day": 1}]  # Has data

        with patch.object(module, "aggregate_monthly", return_value=mock_agg):
            with patch.object(module, "render_report_page", return_value="<html>"):
                with patch.object(module, "format_monthly_txt", return_value="TXT"):
                    with patch.object(module, "monthly_to_json", return_value={}):
                        module.render_monthly_report("repeater", 2024, 12)

        # Check files were created
        report_dir = tmp_path / "reports" / "repeater" / "2024" / "12"
        assert (report_dir / "index.html").exists()
        assert (report_dir / "report.txt").exists()
        assert (report_dir / "report.json").exists()

    def test_writes_valid_json(self, configured_env, tmp_path, monkeypatch):
        """JSON output should be valid JSON."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.daily = [{"day": 1}]

        json_data = {"period": "2024-12", "metrics": {"bat": {"avg": 3850}}}

        with patch.object(module, "aggregate_monthly", return_value=mock_agg):
            with patch.object(module, "render_report_page", return_value="<html>"):
                with patch.object(module, "format_monthly_txt", return_value="TXT"):
                    with patch.object(module, "monthly_to_json", return_value=json_data):
                        module.render_monthly_report("repeater", 2024, 12)

        json_file = tmp_path / "reports" / "repeater" / "2024" / "12" / "report.json"
        content = json_file.read_text()
        parsed = json.loads(content)  # Should not raise
        assert parsed["period"] == "2024-12"


class TestRenderYearlyReport:
    """Test render_yearly_report function."""

    def test_skips_empty_aggregation(self, configured_env):
        """Should skip when no data for the year."""
        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.monthly = []  # No data

        with patch.object(module, "aggregate_yearly", return_value=mock_agg):
            with patch.object(module, "safe_write") as mock_write:
                module.render_yearly_report("repeater", 2024)

                # Should not write any files
                mock_write.assert_not_called()

    def test_writes_all_formats(self, configured_env, tmp_path, monkeypatch):
        """Should write HTML, TXT, and JSON formats."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.monthly = [{"month": 1}]  # Has data

        with patch.object(module, "aggregate_yearly", return_value=mock_agg):
            with patch.object(module, "render_report_page", return_value="<html>"):
                with patch.object(module, "format_yearly_txt", return_value="TXT"):
                    with patch.object(module, "yearly_to_json", return_value={}):
                        module.render_yearly_report("repeater", 2024)

        # Check files were created
        report_dir = tmp_path / "reports" / "repeater" / "2024"
        assert (report_dir / "index.html").exists()
        assert (report_dir / "report.txt").exists()
        assert (report_dir / "report.json").exists()

    def test_writes_valid_html(self, configured_env, tmp_path, monkeypatch):
        """HTML output should contain valid HTML structure."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.monthly = [{"month": 1}]

        html_content = "<!DOCTYPE html><html><head><title>Report</title></head><body>Content</body></html>"

        with patch.object(module, "aggregate_yearly", return_value=mock_agg):
            with patch.object(module, "render_report_page", return_value=html_content):
                with patch.object(module, "format_yearly_txt", return_value="TXT"):
                    with patch.object(module, "yearly_to_json", return_value={}):
                        module.render_yearly_report("repeater", 2024)

        html_file = tmp_path / "reports" / "repeater" / "2024" / "index.html"
        content = html_file.read_text()
        assert "<!DOCTYPE html>" in content
        assert "<html>" in content
        assert "</html>" in content


class TestReportNavigation:
    """Test prev/next navigation in reports."""

    def test_monthly_report_with_prev_next(self, configured_env, tmp_path, monkeypatch):
        """Monthly report should build prev/next navigation links."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.daily = [{"day": 1}]

        prev_report_data = None
        next_report_data = None

        def capture_render(agg, node_name, report_type, prev_report, next_report):
            nonlocal prev_report_data, next_report_data
            prev_report_data = prev_report
            next_report_data = next_report
            return "<html>"

        with patch.object(module, "aggregate_monthly", return_value=mock_agg):
            with patch.object(module, "render_report_page", side_effect=capture_render):
                with patch.object(module, "format_monthly_txt", return_value="TXT"):
                    with patch.object(module, "monthly_to_json", return_value={}):
                        # Call with prev and next periods
                        module.render_monthly_report(
                            "repeater", 2024, 6, prev_period=(2024, 5), next_period=(2024, 7)
                        )

        assert prev_report_data is not None
        assert prev_report_data["url"] == "/reports/repeater/2024/05/"
        assert prev_report_data["label"] == "May 2024"
        assert next_report_data is not None
        assert next_report_data["url"] == "/reports/repeater/2024/07/"
        assert next_report_data["label"] == "Jul 2024"

    def test_yearly_report_with_prev_next(self, configured_env, tmp_path, monkeypatch):
        """Yearly report should build prev/next navigation links."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        mock_agg = MagicMock()
        mock_agg.monthly = [{"month": 1}]

        prev_report_data = None
        next_report_data = None

        def capture_render(agg, node_name, report_type, prev_report, next_report):
            nonlocal prev_report_data, next_report_data
            prev_report_data = prev_report
            next_report_data = next_report
            return "<html>"

        with patch.object(module, "aggregate_yearly", return_value=mock_agg):
            with patch.object(module, "render_report_page", side_effect=capture_render):
                with patch.object(module, "format_yearly_txt", return_value="TXT"):
                    with patch.object(module, "yearly_to_json", return_value={}):
                        # Call with prev and next years
                        module.render_yearly_report("repeater", 2024, prev_year=2023, next_year=2025)

        assert prev_report_data is not None
        assert prev_report_data["url"] == "/reports/repeater/2023/"
        assert prev_report_data["label"] == "2023"
        assert next_report_data is not None
        assert next_report_data["url"] == "/reports/repeater/2025/"
        assert next_report_data["label"] == "2025"


class TestMainWithData:
    """Test main() function with actual data periods."""

    def test_main_renders_reports_when_data_exists(self, configured_env, tmp_path, monkeypatch):
        """main() should render monthly and yearly reports when data exists."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        def mock_periods(role):
            if role == "repeater":
                return [(2024, 11), (2024, 12)]
            return []

        mock_monthly_agg = MagicMock()
        mock_monthly_agg.daily = [{"day": 1}]

        mock_yearly_agg = MagicMock()
        mock_yearly_agg.monthly = [{"month": 11}]

        with patch.object(module, "init_db"):
            with patch.object(module, "get_available_periods", side_effect=mock_periods):
                with patch.object(module, "aggregate_monthly", return_value=mock_monthly_agg):
                    with patch.object(module, "aggregate_yearly", return_value=mock_yearly_agg):
                        with patch.object(module, "render_report_page", return_value="<html>"):
                            with patch.object(module, "format_monthly_txt", return_value="TXT"):
                                with patch.object(module, "format_yearly_txt", return_value="TXT"):
                                    with patch.object(module, "monthly_to_json", return_value={}):
                                        with patch.object(module, "yearly_to_json", return_value={}):
                                            with patch.object(
                                                module, "render_reports_index", return_value="<html>"
                                            ):
                                                module.main()

        # Verify reports were created
        repeater_dir = tmp_path / "reports" / "repeater"
        assert (repeater_dir / "2024" / "11" / "index.html").exists()
        assert (repeater_dir / "2024" / "12" / "index.html").exists()
        assert (repeater_dir / "2024" / "index.html").exists()

    def test_main_creates_index_with_content(self, configured_env, tmp_path, monkeypatch):
        """main() should create reports index with valid content."""
        monkeypatch.setenv("OUT_DIR", str(tmp_path))
        import meshmon.env

        meshmon.env._config = None

        module = load_script("render_reports.py")

        index_html = """<!DOCTYPE html>
<html>
<head><title>Reports Index</title></head>
<body><h1>Reports</h1></body>
</html>"""

        with patch.object(module, "init_db"):
            with patch.object(module, "get_available_periods", return_value=[]):
                with patch.object(module, "build_reports_index_data", return_value=[]):
                    with patch.object(module, "render_reports_index", return_value=index_html):
                        module.main()

        index_file = tmp_path / "reports" / "index.html"
        assert index_file.exists()
        content = index_file.read_text()
        assert "<!DOCTYPE html>" in content
        assert "Reports" in content
