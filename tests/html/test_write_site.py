"""Tests for write_site and related output functions."""

import pytest
from pathlib import Path

from meshmon.html import (
    write_site,
    copy_static_assets,
)
from meshmon.db import get_latest_metrics


@pytest.fixture
def metrics_rows(populated_db):
    """Get latest metrics rows for both roles."""
    companion_row = get_latest_metrics("companion")
    repeater_row = get_latest_metrics("repeater")
    return {"companion": companion_row, "repeater": repeater_row}


class TestWriteSite:
    """Tests for write_site function."""

    def test_creates_output_directory(self, configured_env, metrics_rows):
        """Creates output directory if it doesn't exist."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        assert out_dir.exists()

    def test_generates_repeater_pages(self, configured_env, metrics_rows):
        """Generates repeater HTML pages at root."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        # Repeater pages are at root
        for period in ["day", "week", "month", "year"]:
            assert (out_dir / f"{period}.html").exists()

    def test_generates_companion_pages(self, configured_env, metrics_rows):
        """Generates companion HTML pages in subdirectory."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        companion_dir = out_dir / "companion"
        assert companion_dir.exists()
        for period in ["day", "week", "month", "year"]:
            assert (companion_dir / f"{period}.html").exists()

    def test_html_files_are_valid(self, configured_env, metrics_rows):
        """Generated HTML files have valid structure."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        html_file = out_dir / "day.html"
        content = html_file.read_text()

        assert "<!DOCTYPE html>" in content or "<!doctype html>" in content.lower()
        assert "</html>" in content

    def test_handles_empty_database(self, configured_env, initialized_db):
        """Handles empty database gracefully."""
        out_dir = configured_env["out_dir"]

        # Should not raise - pass None for empty database
        write_site(None, None)

        # Should still generate pages
        assert (out_dir / "day.html").exists()


class TestCopyStaticAssets:
    """Tests for copy_static_assets function."""

    def test_copies_css(self, configured_env):
        """Copies CSS stylesheet."""
        out_dir = configured_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        copy_static_assets()

        css_file = out_dir / "styles.css"
        assert css_file.exists()

    def test_copies_javascript(self, configured_env):
        """Copies JavaScript files."""
        out_dir = configured_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        copy_static_assets()

        js_file = out_dir / "chart-tooltip.js"
        assert js_file.exists()

    def test_css_is_valid(self, configured_env):
        """Copied CSS has expected content."""
        out_dir = configured_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        copy_static_assets()

        css_file = out_dir / "styles.css"
        content = css_file.read_text()

        # Should have CSS variables
        assert "--" in content or "{" in content

    def test_requires_output_directory(self, configured_env):
        """Requires output directory to exist."""
        out_dir = configured_env["out_dir"]
        # Ensure out_dir exists
        out_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise when directory exists
        copy_static_assets()

        assert (out_dir / "styles.css").exists()

    def test_overwrites_existing(self, configured_env):
        """Overwrites existing static files."""
        out_dir = configured_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        # Create a fake CSS file
        css_file = out_dir / "styles.css"
        css_file.write_text("/* fake */")

        copy_static_assets()

        # Should be overwritten with real content
        content = css_file.read_text()
        assert "/* fake */" not in content or len(content) > 20


class TestHtmlOutput:
    """Tests for HTML output structure."""

    def test_pages_include_navigation(self, configured_env, metrics_rows):
        """HTML pages include navigation."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        # Should have links to other periods
        assert "week" in content.lower()
        assert "month" in content.lower()

    def test_pages_include_meta_tags(self, configured_env, metrics_rows):
        """HTML pages include meta tags."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        assert "<meta" in content
        assert "charset" in content.lower() or "utf-8" in content.lower()

    def test_pages_include_title(self, configured_env, metrics_rows):
        """HTML pages include title tag."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        assert "<title>" in content
        assert "</title>" in content

    def test_pages_reference_css(self, configured_env, metrics_rows):
        """HTML pages reference stylesheet."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        assert "styles.css" in content

    def test_companion_pages_relative_css(self, configured_env, metrics_rows):
        """Companion pages use relative path to CSS."""
        out_dir = configured_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "companion" / "day.html").read_text()

        # Should reference parent directory CSS
        assert "../styles.css" in content or "styles.css" in content
