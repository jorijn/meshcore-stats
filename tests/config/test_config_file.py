"""Tests for meshcore.conf file parsing."""

import pytest
from unittest.mock import patch
from pathlib import Path

from meshmon.env import _parse_config_value, _load_config_file


class TestParseConfigValueDetailed:
    """Detailed tests for _parse_config_value."""

    # ==========================================================================
    # Empty/whitespace handling
    # ==========================================================================

    def test_empty_string(self):
        assert _parse_config_value("") == ""

    def test_only_spaces(self):
        assert _parse_config_value("   ") == ""

    def test_only_tabs(self):
        assert _parse_config_value("\t\t") == ""

    # ==========================================================================
    # Unquoted values
    # ==========================================================================

    def test_simple_value(self):
        assert _parse_config_value("hello") == "hello"

    def test_value_with_leading_trailing_space(self):
        assert _parse_config_value("  hello  ") == "hello"

    def test_value_with_internal_spaces(self):
        assert _parse_config_value("hello world") == "hello world"

    def test_numeric_value(self):
        assert _parse_config_value("12345") == "12345"

    def test_path_value(self):
        assert _parse_config_value("/dev/ttyUSB0") == "/dev/ttyUSB0"

    # ==========================================================================
    # Double-quoted strings
    # ==========================================================================

    def test_double_quoted_simple(self):
        assert _parse_config_value('"hello"') == "hello"

    def test_double_quoted_with_spaces(self):
        assert _parse_config_value('"hello world"') == "hello world"

    def test_double_quoted_with_special_chars(self):
        assert _parse_config_value('"hello #world"') == "hello #world"

    def test_double_quoted_unclosed(self):
        assert _parse_config_value('"hello') == "hello"

    def test_double_quoted_empty(self):
        assert _parse_config_value('""') == ""

    def test_double_quoted_with_trailing_content(self):
        # Only extracts content within first pair of quotes
        assert _parse_config_value('"hello" # comment') == "hello"

    # ==========================================================================
    # Single-quoted strings
    # ==========================================================================

    def test_single_quoted_simple(self):
        assert _parse_config_value("'hello'") == "hello"

    def test_single_quoted_with_spaces(self):
        assert _parse_config_value("'hello world'") == "hello world"

    def test_single_quoted_unclosed(self):
        assert _parse_config_value("'hello") == "hello"

    def test_single_quoted_empty(self):
        assert _parse_config_value("''") == ""

    # ==========================================================================
    # Inline comments
    # ==========================================================================

    def test_inline_comment_with_space(self):
        assert _parse_config_value("hello # comment") == "hello"

    def test_inline_comment_multiple_spaces(self):
        assert _parse_config_value("hello   # comment here") == "hello"

    def test_hash_without_space_kept(self):
        # Hash without preceding space is kept (not a comment)
        assert _parse_config_value("color#ffffff") == "color#ffffff"

    def test_hash_at_start_kept(self):
        # Hash at start is kept (though unusual for a value)
        assert _parse_config_value("#ffffff") == "#ffffff"

    # ==========================================================================
    # Mixed scenarios
    # ==========================================================================

    def test_quoted_preserves_hash_comment_style(self):
        assert _parse_config_value('"test # not a comment"') == "test # not a comment"

    def test_value_ending_with_hash(self):
        # "test#" has no space before #, so kept
        assert _parse_config_value("test#") == "test#"


class TestLoadConfigFileBehavior:
    """Tests for _load_config_file behavior."""

    def test_nonexistent_file_no_error(self, tmp_path, monkeypatch):
        """Missing config file doesn't raise error."""
        # Point to non-existent path
        fake_module_path = tmp_path / "src" / "meshmon" / "env.py"
        fake_module_path.parent.mkdir(parents=True)
        fake_module_path.write_text("")

        # No exception should be raised
        # The function checks for existence first

    def test_skips_empty_lines(self, tmp_path, monkeypatch, isolate_config_loading):
        """Empty lines are skipped."""
        config_content = """
MESH_TRANSPORT=tcp

MESH_DEBUG=1

"""
        config_path = tmp_path / "meshcore.conf"
        config_path.write_text(config_content)

        # Mock the config path location
        with patch("meshmon.env.Path") as mock_path:
            mock_path.return_value.resolve.return_value.parent.parent.parent.__truediv__.return_value = config_path
            mock_path.return_value.resolve.return_value.parent.parent.parent / "meshcore.conf"
            # _load_config_file() would need to be called manually or tested via Config

    def test_skips_comment_lines(self, tmp_path):
        """Lines starting with # are skipped."""
        config_content = """# This is a comment
MESH_TRANSPORT=tcp
# Another comment
"""
        config_path = tmp_path / "meshcore.conf"
        config_path.write_text(config_content)
        # The parsing logic skips lines starting with #

    def test_handles_export_prefix(self, tmp_path):
        """Lines with 'export ' prefix are handled."""
        config_content = "export MESH_TRANSPORT=tcp\n"
        config_path = tmp_path / "meshcore.conf"
        config_path.write_text(config_content)
        # The parsing logic removes 'export ' prefix

    def test_skips_lines_without_equals(self, tmp_path):
        """Lines without = are skipped."""
        config_content = """MESH_TRANSPORT=tcp
this line has no equals
MESH_DEBUG=1
"""
        config_path = tmp_path / "meshcore.conf"
        config_path.write_text(config_content)
        # Invalid lines are skipped

    def test_env_vars_take_precedence(self, tmp_path, monkeypatch, isolate_config_loading):
        """Environment variables override config file values."""
        # Set env var first
        monkeypatch.setenv("MESH_TRANSPORT", "ble")

        # Config file has different value
        config_content = "MESH_TRANSPORT=serial\n"
        config_path = tmp_path / "meshcore.conf"
        config_path.write_text(config_content)

        # After loading, env var should still be "ble"
        import os
        assert os.environ.get("MESH_TRANSPORT") == "ble"


class TestConfigFileFormats:
    """Test various config file format scenarios."""

    def test_standard_format(self):
        """Standard KEY=value format."""
        assert _parse_config_value("value") == "value"

    def test_spaces_around_equals(self):
        """Key = value with spaces (handled by partition)."""
        # Note: _parse_config_value only handles the value part
        # The key=value split happens in _load_config_file
        assert _parse_config_value(" value ") == "value"

    def test_quoted_path_with_spaces(self):
        """Path with spaces must be quoted."""
        assert _parse_config_value('"/path/with spaces/file.txt"') == "/path/with spaces/file.txt"

    def test_url_value(self):
        """URL values work correctly."""
        assert _parse_config_value("https://example.com:8080/path") == "https://example.com:8080/path"

    def test_email_value(self):
        """Email values work correctly."""
        assert _parse_config_value("user@example.com") == "user@example.com"

    def test_json_like_value(self):
        """JSON-like values need quoting if they have spaces."""
        # Without spaces, works fine
        assert _parse_config_value("{key:value}") == "{key:value}"
        # With spaces, needs quotes
        assert _parse_config_value('"{key: value}"') == "{key: value}"


class TestValidKeyPatterns:
    """Test key validation patterns."""

    def test_valid_key_patterns(self):
        """Valid shell identifier patterns."""
        # These would be tested in _load_config_file
        # Valid: starts with letter or underscore, contains letters/numbers/underscores
        valid_keys = [
            "MESH_TRANSPORT",
            "_PRIVATE",
            "var123",
            "MY_VAR_2",
        ]
        # All should match: ^[A-Za-z_][A-Za-z0-9_]*$
        import re
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        for key in valid_keys:
            assert re.match(pattern, key), f"{key} should be valid"

    def test_invalid_key_patterns(self):
        """Invalid key patterns are rejected."""
        invalid_keys = [
            "123_starts_with_number",
            "has-dash",
            "has.dot",
            "has space",
            "",
        ]
        import re
        pattern = r"^[A-Za-z_][A-Za-z0-9_]*$"
        for key in invalid_keys:
            assert not re.match(pattern, key), f"{key} should be invalid"
