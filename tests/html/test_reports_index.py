"""Tests for reports index page generation."""


import pytest

from meshmon.html import render_reports_index


class TestRenderReportsIndex:
    """Tests for render_reports_index function."""

    @pytest.fixture
    def sample_report_sections(self):
        """Sample report sections for testing."""
        return [
            {
                "role": "repeater",
                "years": [
                    {
                        "year": 2024,
                        "months": [
                            {"month": 1, "name": "January"},
                            {"month": 2, "name": "February"},
                        ]
                    }
                ]
            },
            {
                "role": "companion",
                "years": [
                    {
                        "year": 2024,
                        "months": [
                            {"month": 1, "name": "January"},
                        ]
                    }
                ]
            },
        ]

    def test_returns_html_string(self, configured_env, sample_report_sections):
        """Returns an HTML string."""
        html = render_reports_index(sample_report_sections)

        assert isinstance(html, str)
        assert len(html) > 0

    def test_html_structure(self, configured_env, sample_report_sections):
        """Generated HTML has proper structure."""
        html = render_reports_index(sample_report_sections)

        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()
        assert "</html>" in html

    def test_includes_title(self, configured_env, sample_report_sections):
        """Index page includes title."""
        html = render_reports_index(sample_report_sections)

        assert "Reports Archive" in html

    def test_includes_year(self, configured_env, sample_report_sections):
        """Lists available years."""
        html = render_reports_index(sample_report_sections)

        assert "/reports/repeater/2024/" in html

    def test_handles_empty_sections(self, configured_env):
        """Handles empty report sections."""
        html = render_reports_index([])

        assert isinstance(html, str)
        assert "</html>" in html

    def test_includes_role_names(self, configured_env, sample_report_sections):
        """Includes role names in output."""
        html = render_reports_index(sample_report_sections)

        assert "Repeater" in html
        assert "Companion" in html

    def test_includes_descriptions(self, configured_env, sample_report_sections, monkeypatch):
        """Includes role descriptions from config."""
        monkeypatch.setenv("REPEATER_DISPLAY_NAME", "Alpha Repeater")
        monkeypatch.setenv("COMPANION_DISPLAY_NAME", "Beta Node")
        monkeypatch.setenv("REPORT_LOCATION_SHORT", "Test Ridge")
        import meshmon.env
        meshmon.env._config = None

        html = render_reports_index(sample_report_sections)

        assert "Alpha Repeater — Remote node in Test Ridge" in html
        assert "Beta Node — Local USB-connected node" in html

    def test_includes_css_reference(self, configured_env, sample_report_sections):
        """Includes reference to stylesheet."""
        html = render_reports_index(sample_report_sections)

        assert "styles.css" in html

    def test_handles_sections_without_years(self, configured_env):
        """Handles sections with no years."""
        sections = [
            {"role": "repeater", "years": []},
            {"role": "companion", "years": []},
        ]

        html = render_reports_index(sections)

        assert isinstance(html, str)
        assert "No reports available yet." in html
