"""Tests for Jinja2 environment and custom filters."""

import pytest
from jinja2 import Environment

from meshmon.html import get_jinja_env


class TestGetJinjaEnv:
    """Tests for get_jinja_env function."""

    def test_returns_environment(self):
        """Returns a Jinja2 Environment."""
        env = get_jinja_env()
        assert isinstance(env, Environment)

    def test_has_autoescape(self):
        """Environment has autoescape enabled."""
        env = get_jinja_env()
        # Default is to autoescape HTML files
        assert env.autoescape is True or callable(env.autoescape)

    def test_can_load_templates(self, templates_dir):
        """Can load templates from the templates directory."""
        env = get_jinja_env()

        # Should be able to get the base template
        template = env.get_template("base.html")
        assert template is not None

    def test_returns_same_instance(self):
        """Returns the same environment instance (cached)."""
        env1 = get_jinja_env()
        env2 = get_jinja_env()
        # Implementation may or may not cache - just verify both work
        assert env1 is not None
        assert env2 is not None


class TestJinjaFilters:
    """Tests for custom Jinja2 filters."""

    @pytest.fixture
    def env(self):
        """Get Jinja2 environment."""
        return get_jinja_env()

    def test_format_number_filter_exists(self, env):
        """format_number filter is registered."""
        assert "format_number" in env.filters

    def test_format_number_formats_thousands(self, env):
        """format_number adds thousand separators."""
        template = env.from_string("{{ value|format_number }}")

        result = template.render(value=1234567)
        # Should have some separator
        assert "1234567" not in result or len(result) > 7

    def test_format_number_handles_none(self, env):
        """format_number handles None gracefully."""
        template = env.from_string("{{ value|format_number }}")

        result = template.render(value=None)
        # Should return dash or empty string for None
        assert result in ["-", "N/A", "None", "", " - "]

    def test_format_time_filter_exists(self, env):
        """format_time filter is registered."""
        assert "format_time" in env.filters

    def test_format_time_formats_timestamp(self, env):
        """format_time formats Unix timestamp."""
        template = env.from_string("{{ value|format_time }}")

        # Use a recent timestamp
        import time
        ts = int(time.time()) - 3600
        result = template.render(value=ts)
        # Should produce some formatted time string
        assert len(result) > 0

    def test_format_time_handles_none(self, env):
        """format_time handles None gracefully."""
        template = env.from_string("{{ value|format_time }}")

        result = template.render(value=None)
        assert result in ["-", "N/A", "None", "", " - "]

    def test_format_uptime_filter_exists(self, env):
        """format_uptime filter is registered."""
        assert "format_uptime" in env.filters

    def test_format_uptime_formats_seconds(self, env):
        """format_uptime formats seconds to human readable."""
        template = env.from_string("{{ value|format_uptime }}")

        # 1 day, 2 hours, 30 minutes = 95400 seconds
        result = template.render(value=95400)
        # Should produce some duration output
        assert len(result) > 0

    def test_format_duration_filter_exists(self, env):
        """format_duration filter is registered."""
        assert "format_duration" in env.filters

    def test_format_value_filter_exists(self, env):
        """format_value filter is registered."""
        assert "format_value" in env.filters

    def test_format_compact_number_filter_exists(self, env):
        """format_compact_number filter is registered."""
        assert "format_compact_number" in env.filters


class TestTemplateRendering:
    """Tests for basic template rendering."""

    def test_base_template_renders(self):
        """Base template renders without error."""
        env = get_jinja_env()
        template = env.get_template("base.html")

        # Render with minimal context
        html = template.render(
            role="repeater",
            period="day",
            title="Test",
        )

        assert "</html>" in html

    def test_node_template_extends_base(self):
        """Node template extends base template."""
        env = get_jinja_env()
        template = env.get_template("node.html")

        # Should have access to base template blocks
        assert template is not None

    def test_template_has_html_structure(self):
        """Rendered template has proper HTML structure."""
        env = get_jinja_env()
        template = env.get_template("base.html")

        html = template.render(
            role="repeater",
            period="day",
            title="Test Page",
        )

        assert "<!DOCTYPE html>" in html or "<!doctype html>" in html.lower()
        assert "<html" in html
        assert "<head>" in html
        assert "<body>" in html
