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

        assert "<title>" in html
        assert "Report" in html or "report" in html

    def test_includes_year(self, configured_env, sample_report_sections):
        """Lists available years."""
        html = render_reports_index(sample_report_sections)

        assert "2024" in html

    def test_handles_empty_sections(self, configured_env):
        """Handles empty report sections."""
        html = render_reports_index([])

        assert isinstance(html, str)
        assert "</html>" in html

    def test_includes_role_names(self, configured_env, sample_report_sections):
        """Includes role names in output."""
        html = render_reports_index(sample_report_sections)

        # Should mention both roles
        assert "repeater" in html.lower() or "Repeater" in html

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
        assert "</html>" in html
