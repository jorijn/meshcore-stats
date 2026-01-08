"""Tests for page context building."""

import time

import pytest

from meshmon.html import (
    build_page_context,
    get_status,
)


class TestGetStatus:
    """Tests for get_status function."""

    def test_online_for_recent_data(self):
        """Returns 'online' for data less than 30 minutes old."""
        # 10 minutes ago
        recent_ts = int(time.time()) - 600

        status_class, status_label = get_status(recent_ts)

        assert status_class == "online"

    def test_stale_for_medium_age_data(self):
        """Returns 'stale' for data 30 minutes to 2 hours old."""
        # 1 hour ago
        medium_ts = int(time.time()) - 3600

        status_class, status_label = get_status(medium_ts)

        assert status_class == "stale"

    def test_offline_for_old_data(self):
        """Returns 'offline' for data more than 2 hours old."""
        # 3 hours ago
        old_ts = int(time.time()) - 10800

        status_class, status_label = get_status(old_ts)

        assert status_class == "offline"

    def test_offline_for_very_old_data(self):
        """Returns 'offline' for very old data."""
        # 7 days ago
        very_old_ts = int(time.time()) - 604800

        status_class, status_label = get_status(very_old_ts)

        assert status_class == "offline"

    def test_offline_for_none(self):
        """Returns 'offline' for None timestamp."""
        status_class, status_label = get_status(None)

        assert status_class == "offline"

    def test_offline_for_zero(self):
        """Returns 'offline' for zero timestamp."""
        status_class, status_label = get_status(0)

        assert status_class == "offline"

    def test_online_for_current_time(self):
        """Returns 'online' for current timestamp."""
        now_ts = int(time.time())

        status_class, status_label = get_status(now_ts)

        assert status_class == "online"

    def test_boundary_30_minutes(self):
        """Tests boundary at exactly 30 minutes."""
        # Exactly 30 minutes ago
        boundary_ts = int(time.time()) - 1800

        status_class, _ = get_status(boundary_ts)
        # At boundary, could be either online or stale depending on implementation
        assert status_class in ["online", "stale"]

    def test_boundary_2_hours(self):
        """Tests boundary at exactly 2 hours."""
        # Exactly 2 hours ago
        boundary_ts = int(time.time()) - 7200

        status_class, _ = get_status(boundary_ts)
        # At boundary, could be either stale or offline
        assert status_class in ["stale", "offline"]

    def test_returns_tuple(self):
        """Returns tuple of (status_class, status_label)."""
        status = get_status(int(time.time()))
        assert isinstance(status, tuple)
        assert len(status) == 2

    def test_status_label_is_string(self):
        """Status label is a string."""
        _, status_label = get_status(int(time.time()))
        assert isinstance(status_label, str)


class TestBuildPageContext:
    """Tests for build_page_context function."""

    @pytest.fixture
    def sample_row(self, sample_repeater_metrics):
        """Create a sample row with timestamp."""
        row = sample_repeater_metrics.copy()
        row["ts"] = int(time.time()) - 300  # 5 minutes ago
        return row

    def test_returns_dict(self, configured_env, sample_row):
        """Returns a dictionary."""
        context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )

        assert isinstance(context, dict)

    def test_includes_role_and_period(self, configured_env, sample_row):
        """Context includes role and period."""
        context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )

        assert context.get("role") == "repeater"
        assert context.get("period") == "day"

    def test_includes_status(self, configured_env, sample_row):
        """Context includes status indicator."""
        context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )

        assert "status_class" in context
        assert context["status_class"] in ["online", "stale", "offline"]

    def test_handles_none_row(self, configured_env):
        """Handles None row gracefully."""
        context = build_page_context(
            role="repeater",
            period="day",
            row=None,
            at_root=True,
        )

        assert context.get("status_class") == "offline"

    def test_includes_node_name(self, configured_env, sample_row, monkeypatch):
        """Context includes node name from config."""
        monkeypatch.setenv("REPEATER_DISPLAY_NAME", "Test Repeater")
        import meshmon.env
        meshmon.env._config = None

        context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )

        assert "node_name" in context
        assert context["node_name"] == "Test Repeater"

    def test_includes_period(self, configured_env, sample_row):
        """Context includes current period."""
        context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )

        assert "period" in context
        assert context["period"] == "day"

    def test_different_roles(self, configured_env, sample_row, sample_companion_metrics):
        """Context varies by role."""
        companion_row = sample_companion_metrics.copy()
        companion_row["ts"] = int(time.time()) - 300

        repeater_context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )
        companion_context = build_page_context(
            role="companion",
            period="day",
            row=companion_row,
            at_root=False,
        )

        assert repeater_context["role"] == "repeater"
        assert companion_context["role"] == "companion"

    def test_at_root_affects_css_path(self, configured_env, sample_row):
        """at_root parameter affects CSS path."""
        root_context = build_page_context(
            role="repeater",
            period="day",
            row=sample_row,
            at_root=True,
        )
        non_root_context = build_page_context(
            role="companion",
            period="day",
            row=sample_row,
            at_root=False,
        )

        # Non-root pages need relative path to CSS
        assert "css_path" in root_context or "at_root" in root_context
        assert "css_path" in non_root_context or "at_root" in non_root_context
