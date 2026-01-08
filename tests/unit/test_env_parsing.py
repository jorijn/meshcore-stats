"""Tests for environment variable parsing functions."""

from pathlib import Path

import pytest

from meshmon.env import (
    Config,
    _parse_config_value,
    get_bool,
    get_config,
    get_float,
    get_int,
    get_path,
    get_str,
)


class TestParseConfigValue:
    """Test _parse_config_value function."""

    def test_empty_string(self):
        """Empty string returns empty."""
        assert _parse_config_value("") == ""
        assert _parse_config_value("   ") == ""

    def test_unquoted_value(self):
        """Unquoted values are returned trimmed."""
        assert _parse_config_value("hello") == "hello"
        assert _parse_config_value("  hello  ") == "hello"
        assert _parse_config_value("hello world") == "hello world"

    def test_double_quoted_value(self):
        """Double quoted values extract content."""
        assert _parse_config_value('"hello"') == "hello"
        assert _parse_config_value('"hello world"') == "hello world"
        assert _parse_config_value('"value with spaces"') == "value with spaces"

    def test_single_quoted_value(self):
        """Single quoted values extract content."""
        assert _parse_config_value("'hello'") == "hello"
        assert _parse_config_value("'hello world'") == "hello world"

    def test_unclosed_quotes(self):
        """Unclosed quotes return content after quote."""
        assert _parse_config_value('"hello') == "hello"
        assert _parse_config_value("'hello") == "hello"

    def test_inline_comments_stripped(self):
        """Inline comments (# preceded by space) are stripped."""
        assert _parse_config_value("hello # comment") == "hello"
        assert _parse_config_value("value  # another comment") == "value"

    def test_hash_without_space_kept(self):
        """Hash without preceding space is kept (e.g., color codes)."""
        assert _parse_config_value("#ffffff") == "#ffffff"
        assert _parse_config_value("test#value") == "test#value"

    def test_quoted_values_preserve_comments(self):
        """Quoted values preserve comment-like content."""
        assert _parse_config_value('"hello # not a comment"') == "hello # not a comment"
        assert _parse_config_value("'value # preserved'") == "value # preserved"

    def test_empty_quoted_string(self):
        """Empty quoted string returns empty."""
        assert _parse_config_value('""') == ""
        assert _parse_config_value("''") == ""


class TestGetStr:
    """Test get_str function."""

    def test_returns_value_when_set(self, monkeypatch):
        """Returns env var value when set."""
        monkeypatch.setenv("TEST_VAR", "hello")
        assert get_str("TEST_VAR") == "hello"

    def test_returns_none_when_not_set(self):
        """Returns None when env var not set and no default."""
        assert get_str("NONEXISTENT_VAR_12345") is None

    def test_returns_default_when_not_set(self):
        """Returns default when env var not set."""
        assert get_str("NONEXISTENT_VAR_12345", "default") == "default"

    def test_empty_string_is_valid(self, monkeypatch):
        """Empty string is a valid value, not replaced by default."""
        monkeypatch.setenv("TEST_VAR", "")
        assert get_str("TEST_VAR", "default") == ""


class TestGetInt:
    """Test get_int function."""

    def test_returns_value_when_set(self, monkeypatch):
        """Returns parsed int when set."""
        monkeypatch.setenv("TEST_INT", "42")
        assert get_int("TEST_INT", 0) == 42

    def test_returns_default_when_not_set(self):
        """Returns default when not set."""
        assert get_int("NONEXISTENT_VAR_12345", 99) == 99

    def test_returns_default_on_invalid(self, monkeypatch):
        """Returns default when value is not a valid integer."""
        monkeypatch.setenv("TEST_INT", "not_a_number")
        assert get_int("TEST_INT", 99) == 99

    def test_negative_integers(self, monkeypatch):
        """Handles negative integers."""
        monkeypatch.setenv("TEST_INT", "-42")
        assert get_int("TEST_INT", 0) == -42

    def test_zero(self, monkeypatch):
        """Zero is a valid value."""
        monkeypatch.setenv("TEST_INT", "0")
        assert get_int("TEST_INT", 99) == 0

    def test_float_string_returns_default(self, monkeypatch):
        """Float string is not a valid integer."""
        monkeypatch.setenv("TEST_INT", "3.14")
        assert get_int("TEST_INT", 99) == 99


class TestGetBool:
    """Test get_bool function."""

    def test_returns_default_when_not_set(self):
        """Returns default when not set."""
        assert get_bool("NONEXISTENT_VAR_12345", False) is False
        assert get_bool("NONEXISTENT_VAR_12345", True) is True

    @pytest.mark.parametrize("value", ["1", "true", "True", "TRUE", "yes", "Yes", "on", "ON"])
    def test_truthy_values(self, value, monkeypatch):
        """Various truthy values return True."""
        monkeypatch.setenv("TEST_BOOL", value)
        assert get_bool("TEST_BOOL") is True

    @pytest.mark.parametrize("value", ["0", "false", "False", "no", "No", "off", "anything"])
    def test_falsy_values(self, value, monkeypatch):
        """Non-truthy values return False."""
        monkeypatch.setenv("TEST_BOOL", value)
        assert get_bool("TEST_BOOL") is False

    def test_empty_string_returns_default(self, monkeypatch):
        """Empty string returns default."""
        monkeypatch.setenv("TEST_BOOL", "")
        assert get_bool("TEST_BOOL", True) is True
        assert get_bool("TEST_BOOL", False) is False


class TestGetFloat:
    """Test get_float function."""

    def test_returns_value_when_set(self, monkeypatch):
        """Returns parsed float when set."""
        monkeypatch.setenv("TEST_FLOAT", "3.14")
        assert get_float("TEST_FLOAT", 0.0) == pytest.approx(3.14)

    def test_returns_default_when_not_set(self):
        """Returns default when not set."""
        assert get_float("NONEXISTENT_VAR_12345", 99.9) == 99.9

    def test_returns_default_on_invalid(self, monkeypatch):
        """Returns default when value is not a valid float."""
        monkeypatch.setenv("TEST_FLOAT", "not_a_number")
        assert get_float("TEST_FLOAT", 99.9) == 99.9

    def test_integer_string_valid(self, monkeypatch):
        """Integer string is valid as float."""
        monkeypatch.setenv("TEST_FLOAT", "42")
        assert get_float("TEST_FLOAT", 0.0) == 42.0

    def test_negative_floats(self, monkeypatch):
        """Handles negative floats."""
        monkeypatch.setenv("TEST_FLOAT", "-3.14")
        assert get_float("TEST_FLOAT", 0.0) == pytest.approx(-3.14)

    def test_scientific_notation(self, monkeypatch):
        """Handles scientific notation."""
        monkeypatch.setenv("TEST_FLOAT", "1e-3")
        assert get_float("TEST_FLOAT", 0.0) == pytest.approx(0.001)


class TestGetPath:
    """Test get_path function."""

    def test_returns_path_from_env(self, monkeypatch, tmp_path):
        """Returns Path from env var value."""
        monkeypatch.setenv("TEST_PATH", str(tmp_path))
        result = get_path("TEST_PATH", "/default")
        assert result == tmp_path

    def test_returns_default_when_not_set(self):
        """Returns Path from default when not set."""
        result = get_path("NONEXISTENT_VAR_12345", "/some/path")
        assert result == Path("/some/path")

    def test_expands_user(self, monkeypatch):
        """Expands ~ to user home directory."""
        monkeypatch.setenv("TEST_PATH", "~/subdir")
        result = get_path("TEST_PATH", "/default")
        assert "~" not in str(result)
        assert result.is_absolute()

    def test_resolves_to_absolute(self, monkeypatch):
        """Relative paths are resolved to absolute."""
        monkeypatch.setenv("TEST_PATH", "relative/path")
        result = get_path("TEST_PATH", "/default")
        assert result.is_absolute()


class TestConfig:
    """Test Config class."""

    def test_default_values(self, clean_env):
        """Config uses defaults when env vars not set."""
        config = Config()

        # Connection defaults
        assert config.mesh_transport == "serial"
        assert config.mesh_serial_port is None
        assert config.mesh_serial_baud == 115200
        assert config.mesh_debug is False

        # Timing defaults
        assert config.companion_step == 60
        assert config.repeater_step == 900
        assert config.remote_timeout_s == 10
        assert config.remote_retry_attempts == 2
        assert config.remote_cb_fails == 6
        assert config.remote_cb_cooldown_s == 3600

        # Telemetry defaults
        assert config.telemetry_enabled is False
        assert config.telemetry_timeout_s == 10

        # Display defaults
        assert config.repeater_display_name == "Repeater Node"
        assert config.companion_display_name == "Companion Node"

    def test_reads_env_vars(self, monkeypatch, clean_env):
        """Config reads values from environment."""
        monkeypatch.setenv("MESH_TRANSPORT", "tcp")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyUSB0")
        monkeypatch.setenv("MESH_DEBUG", "1")
        monkeypatch.setenv("COMPANION_STEP", "120")
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        monkeypatch.setenv("TELEMETRY_ENABLED", "true")
        monkeypatch.setenv("REPORT_LAT", "51.5074")

        config = Config()

        assert config.mesh_transport == "tcp"
        assert config.mesh_serial_port == "/dev/ttyUSB0"
        assert config.mesh_debug is True
        assert config.companion_step == 120
        assert config.repeater_name == "TestRepeater"
        assert config.telemetry_enabled is True
        assert config.report_lat == pytest.approx(51.5074)

    def test_paths_are_path_objects(self, monkeypatch, clean_env, tmp_path):
        """Path configs are Path objects."""
        state_dir = tmp_path / "state"
        out_dir = tmp_path / "out"
        monkeypatch.setenv("STATE_DIR", str(state_dir))
        monkeypatch.setenv("OUT_DIR", str(out_dir))

        config = Config()

        assert isinstance(config.state_dir, Path)
        assert isinstance(config.out_dir, Path)


class TestGetConfig:
    """Test get_config singleton function."""

    def test_returns_config_instance(self, clean_env):
        """Returns a Config instance."""
        config = get_config()
        assert isinstance(config, Config)

    def test_returns_same_instance(self, clean_env):
        """Returns the same instance on subsequent calls."""
        config1 = get_config()
        config2 = get_config()
        assert config1 is config2

    def test_reset_creates_new_instance(self, clean_env):
        """After reset, creates new instance."""
        import meshmon.env

        config1 = get_config()

        # Reset singleton
        meshmon.env._config = None

        config2 = get_config()
        assert config1 is not config2
