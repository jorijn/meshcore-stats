"""Tests for write_site and related output functions."""

import pytest

from meshmon.db import get_latest_metrics
from meshmon.html import (
    copy_static_assets,
    write_site,
)

BASE_TS = 1704067200


def _sample_companion_metrics() -> dict[str, float]:
    return {
        "battery_mv": 3850.0,
        "uptime_secs": 86400.0,
        "contacts": 5.0,
        "recv": 1234.0,
        "sent": 567.0,
        "errors": 0.0,
    }


def _sample_repeater_metrics() -> dict[str, float]:
    return {
        "bat": 3920.0,
        "uptime": 172800.0,
        "last_rssi": -85.0,
        "last_snr": 7.5,
        "noise_floor": -115.0,
        "tx_queue_len": 0.0,
        "nb_recv": 5678.0,
        "nb_sent": 2345.0,
        "airtime": 3600.0,
        "rx_airtime": 7200.0,
        "flood_dups": 12.0,
        "direct_dups": 5.0,
        "sent_flood": 100.0,
        "recv_flood": 200.0,
        "sent_direct": 50.0,
        "recv_direct": 75.0,
    }


@pytest.fixture(scope="module")
def html_db_cache(tmp_path_factory):
    """Create and populate a shared DB once for HTML write_site tests."""
    from meshmon.db import init_db, insert_metrics

    root_dir = tmp_path_factory.mktemp("html-db")
    state_dir = root_dir / "state"
    state_dir.mkdir()

    db_path = state_dir / "metrics.db"
    init_db(db_path=db_path)

    now = BASE_TS
    day_seconds = 86400

    sample_companion_metrics = _sample_companion_metrics()
    sample_repeater_metrics = _sample_repeater_metrics()

    # Insert 7 days of companion data (every hour)
    for day in range(7):
        for hour in range(24):
            ts = now - (day * day_seconds) - (hour * 3600)
            metrics = sample_companion_metrics.copy()
            metrics["battery_mv"] = 3700 + (hour * 10) + (day * 5)
            metrics["recv"] = 100 * (day + 1) + hour
            metrics["sent"] = 50 * (day + 1) + hour
            insert_metrics(ts, "companion", metrics, db_path=db_path)

    # Insert 7 days of repeater data (every 15 minutes)
    for day in range(7):
        for interval in range(96):  # 24 * 4
            ts = now - (day * day_seconds) - (interval * 900)
            metrics = sample_repeater_metrics.copy()
            metrics["bat"] = 3700 + (interval * 2) + (day * 5)
            metrics["nb_recv"] = 1000 * (day + 1) + interval * 10
            metrics["nb_sent"] = 500 * (day + 1) + interval * 5
            insert_metrics(ts, "repeater", metrics, db_path=db_path)

    return {"state_dir": state_dir, "db_path": db_path}


@pytest.fixture
def html_env(html_db_cache, tmp_out_dir, monkeypatch):
    """Env with shared DB and per-test output directory."""
    monkeypatch.setenv("STATE_DIR", str(html_db_cache["state_dir"]))
    monkeypatch.setenv("OUT_DIR", str(tmp_out_dir))

    import meshmon.env
    meshmon.env._config = None

    return {"state_dir": html_db_cache["state_dir"], "out_dir": tmp_out_dir}


@pytest.fixture
def metrics_rows(html_env):
    """Get latest metrics rows for both roles."""
    companion_row = get_latest_metrics("companion")
    repeater_row = get_latest_metrics("repeater")
    return {"companion": companion_row, "repeater": repeater_row}


class TestWriteSite:
    """Tests for write_site function."""

    def test_creates_output_directory(self, html_env, metrics_rows):
        """Creates output directory if it doesn't exist."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        assert out_dir.exists()

    def test_generates_repeater_pages(self, html_env, metrics_rows):
        """Generates repeater HTML pages at root."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        # Repeater pages are at root
        for period in ["day", "week", "month", "year"]:
            assert (out_dir / f"{period}.html").exists()

    def test_generates_companion_pages(self, html_env, metrics_rows):
        """Generates companion HTML pages in subdirectory."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        companion_dir = out_dir / "companion"
        assert companion_dir.exists()
        for period in ["day", "week", "month", "year"]:
            assert (companion_dir / f"{period}.html").exists()

    def test_html_files_are_valid(self, html_env, metrics_rows):
        """Generated HTML files have valid structure."""
        out_dir = html_env["out_dir"]

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

    def test_copies_css(self, html_env):
        """Copies CSS stylesheet."""
        out_dir = html_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        copy_static_assets()

        css_file = out_dir / "styles.css"
        assert css_file.exists()

    def test_copies_javascript(self, html_env):
        """Copies JavaScript files."""
        out_dir = html_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        copy_static_assets()

        js_file = out_dir / "chart-tooltip.js"
        assert js_file.exists()

    def test_css_is_valid(self, html_env):
        """Copied CSS has expected content."""
        out_dir = html_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        copy_static_assets()

        css_file = out_dir / "styles.css"
        content = css_file.read_text()

        assert "--bg-primary" in content

    def test_requires_output_directory(self, html_env):
        """Requires output directory to exist."""
        out_dir = html_env["out_dir"]
        # Ensure out_dir exists
        out_dir.mkdir(parents=True, exist_ok=True)

        # Should not raise when directory exists
        copy_static_assets()

        assert (out_dir / "styles.css").exists()

    def test_overwrites_existing(self, html_env):
        """Overwrites existing static files."""
        out_dir = html_env["out_dir"]
        out_dir.mkdir(parents=True, exist_ok=True)

        # Create a fake CSS file
        css_file = out_dir / "styles.css"
        css_file.write_text("/* fake */")

        copy_static_assets()

        # Should be overwritten with real content
        content = css_file.read_text()
        assert content != "/* fake */"
 

class TestHtmlOutput:
    """Tests for HTML output structure."""

    def test_pages_include_navigation(self, html_env, metrics_rows):
        """HTML pages include navigation."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        # Should have links to other periods
        assert "week" in content.lower()
        assert "month" in content.lower()

    def test_pages_include_meta_tags(self, html_env, metrics_rows):
        """HTML pages include meta tags."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        assert "<meta" in content
        assert "charset" in content.lower() or "utf-8" in content.lower()

    def test_pages_include_title(self, html_env, metrics_rows):
        """HTML pages include title tag."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        assert "<title>" in content
        assert "</title>" in content

    def test_pages_reference_css(self, html_env, metrics_rows):
        """HTML pages reference stylesheet."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "day.html").read_text()

        assert "styles.css" in content

    def test_companion_pages_relative_css(self, html_env, metrics_rows):
        """Companion pages use relative path to CSS."""
        out_dir = html_env["out_dir"]

        write_site(metrics_rows["companion"], metrics_rows["repeater"])

        content = (out_dir / "companion" / "day.html").read_text()

        # Should reference parent directory CSS
        assert "../styles.css" in content or "styles.css" in content
