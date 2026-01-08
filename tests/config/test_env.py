"""Tests for environment variable parsing and Config class."""


import pytest

from meshmon.env import (
    Config,
    get_bool,
    get_config,
    get_int,
    get_str,
)


class TestGetStrEdgeCases:
    """Additional edge case tests for get_str."""

    def test_whitespace_value_preserved(self, monkeypatch):
        """Whitespace-only value is preserved."""
        monkeypatch.setenv("TEST_VAR", "   ")
        assert get_str("TEST_VAR") == "   "

    def test_special_characters(self, monkeypatch):
        """Special characters are preserved."""
        monkeypatch.setenv("TEST_VAR", "hello@world#123!")
        assert get_str("TEST_VAR") == "hello@world#123!"


class TestGetIntEdgeCases:
    """Additional edge case tests for get_int."""

    def test_leading_zeros(self, monkeypatch):
        """Leading zeros work (not octal)."""
        monkeypatch.setenv("TEST_INT", "042")
        assert get_int("TEST_INT", 0) == 42

    def test_whitespace_around_number(self, monkeypatch):
        """Whitespace around number is tolerated by int()."""
        monkeypatch.setenv("TEST_INT", " 42 ")
        # Python's int() handles whitespace
        assert get_int("TEST_INT", 0) == 42


class TestGetBoolEdgeCases:
    """Additional edge case tests for get_bool."""

    def test_mixed_case(self, monkeypatch):
        """Mixed case variants work."""
        monkeypatch.setenv("TEST_BOOL", "TrUe")
        assert get_bool("TEST_BOOL") is True

    def test_with_spaces(self, monkeypatch):
        """Whitespace causes a non-match since get_bool does not strip."""
        monkeypatch.setenv("TEST_BOOL", "  yes  ")
        # .lower() doesn't strip, so " yes " != "yes"
        # This will return False
        assert get_bool("TEST_BOOL") is False


class TestConfigComplete:
    """Complete Config class tests."""

    def test_all_connection_settings(self, clean_env, monkeypatch):
        """All connection settings are loaded."""
        monkeypatch.setenv("MESH_TRANSPORT", "tcp")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyUSB0")
        monkeypatch.setenv("MESH_SERIAL_BAUD", "9600")
        monkeypatch.setenv("MESH_TCP_HOST", "192.168.1.1")
        monkeypatch.setenv("MESH_TCP_PORT", "8080")
        monkeypatch.setenv("MESH_BLE_ADDR", "AA:BB:CC:DD:EE:FF")
        monkeypatch.setenv("MESH_BLE_PIN", "1234")
        monkeypatch.setenv("MESH_DEBUG", "true")

        config = Config()

        assert config.mesh_transport == "tcp"
        assert config.mesh_serial_port == "/dev/ttyUSB0"
        assert config.mesh_serial_baud == 9600
        assert config.mesh_tcp_host == "192.168.1.1"
        assert config.mesh_tcp_port == 8080
        assert config.mesh_ble_addr == "AA:BB:CC:DD:EE:FF"
        assert config.mesh_ble_pin == "1234"
        assert config.mesh_debug is True

    def test_all_repeater_settings(self, clean_env, monkeypatch):
        """All repeater identity settings are loaded."""
        monkeypatch.setenv("REPEATER_NAME", "HilltopRepeater")
        monkeypatch.setenv("REPEATER_KEY_PREFIX", "abc123")
        monkeypatch.setenv("REPEATER_PASSWORD", "secret")
        monkeypatch.setenv("REPEATER_DISPLAY_NAME", "Hilltop Relay")
        monkeypatch.setenv("REPEATER_PUBKEY_PREFIX", "!abc123")
        monkeypatch.setenv("REPEATER_HARDWARE", "RAK4631 with Solar")

        config = Config()

        assert config.repeater_name == "HilltopRepeater"
        assert config.repeater_key_prefix == "abc123"
        assert config.repeater_password == "secret"
        assert config.repeater_display_name == "Hilltop Relay"
        assert config.repeater_pubkey_prefix == "!abc123"
        assert config.repeater_hardware == "RAK4631 with Solar"

    def test_all_timeout_settings(self, clean_env, monkeypatch):
        """All timeout and retry settings are loaded."""
        monkeypatch.setenv("REMOTE_TIMEOUT_S", "30")
        monkeypatch.setenv("REMOTE_RETRY_ATTEMPTS", "5")
        monkeypatch.setenv("REMOTE_RETRY_BACKOFF_S", "10")
        monkeypatch.setenv("REMOTE_CB_FAILS", "10")
        monkeypatch.setenv("REMOTE_CB_COOLDOWN_S", "7200")

        config = Config()

        assert config.remote_timeout_s == 30
        assert config.remote_retry_attempts == 5
        assert config.remote_retry_backoff_s == 10
        assert config.remote_cb_fails == 10
        assert config.remote_cb_cooldown_s == 7200

    def test_all_telemetry_settings(self, clean_env, monkeypatch):
        """All telemetry settings are loaded."""
        monkeypatch.setenv("TELEMETRY_ENABLED", "yes")
        monkeypatch.setenv("TELEMETRY_TIMEOUT_S", "20")
        monkeypatch.setenv("TELEMETRY_RETRY_ATTEMPTS", "3")
        monkeypatch.setenv("TELEMETRY_RETRY_BACKOFF_S", "5")

        config = Config()

        assert config.telemetry_enabled is True
        assert config.telemetry_timeout_s == 20
        assert config.telemetry_retry_attempts == 3
        assert config.telemetry_retry_backoff_s == 5

    def test_all_location_settings(self, clean_env, monkeypatch):
        """All location/report settings are loaded."""
        monkeypatch.setenv("REPORT_LOCATION_NAME", "Mountain Peak Observatory")
        monkeypatch.setenv("REPORT_LOCATION_SHORT", "Mountain Peak")
        monkeypatch.setenv("REPORT_LAT", "46.8523")
        monkeypatch.setenv("REPORT_LON", "9.5369")
        monkeypatch.setenv("REPORT_ELEV", "2500")
        monkeypatch.setenv("REPORT_ELEV_UNIT", "ft")

        config = Config()

        assert config.report_location_name == "Mountain Peak Observatory"
        assert config.report_location_short == "Mountain Peak"
        assert config.report_lat == pytest.approx(46.8523)
        assert config.report_lon == pytest.approx(9.5369)
        assert config.report_elev == pytest.approx(2500)
        assert config.report_elev_unit == "ft"

    def test_all_radio_settings(self, clean_env, monkeypatch):
        """All radio configuration settings are loaded."""
        monkeypatch.setenv("RADIO_FREQUENCY", "915.000 MHz")
        monkeypatch.setenv("RADIO_BANDWIDTH", "125 kHz")
        monkeypatch.setenv("RADIO_SPREAD_FACTOR", "SF12")
        monkeypatch.setenv("RADIO_CODING_RATE", "CR5")

        config = Config()

        assert config.radio_frequency == "915.000 MHz"
        assert config.radio_bandwidth == "125 kHz"
        assert config.radio_spread_factor == "SF12"
        assert config.radio_coding_rate == "CR5"

    def test_companion_settings(self, clean_env, monkeypatch):
        """Companion display settings are loaded."""
        monkeypatch.setenv("COMPANION_DISPLAY_NAME", "Base Station")
        monkeypatch.setenv("COMPANION_PUBKEY_PREFIX", "!def456")
        monkeypatch.setenv("COMPANION_HARDWARE", "T-Beam Supreme")

        config = Config()

        assert config.companion_display_name == "Base Station"
        assert config.companion_pubkey_prefix == "!def456"
        assert config.companion_hardware == "T-Beam Supreme"


class TestGetConfigSingleton:
    """Tests for get_config singleton behavior."""

    def test_config_persists_across_calls(self, clean_env, monkeypatch):
        """Config values persist across multiple get_config calls."""
        monkeypatch.setenv("MESH_TRANSPORT", "tcp")

        config1 = get_config()
        assert config1.mesh_transport == "tcp"

        # Change env var - should NOT affect cached config
        monkeypatch.setenv("MESH_TRANSPORT", "ble")

        config2 = get_config()
        assert config2.mesh_transport == "tcp"  # Still tcp, cached
        assert config1 is config2

    def test_reset_allows_new_config(self, clean_env, monkeypatch):
        """Resetting singleton allows new config."""
        monkeypatch.setenv("MESH_TRANSPORT", "tcp")

        config1 = get_config()
        assert config1.mesh_transport == "tcp"

        # Reset singleton
        import meshmon.env
        meshmon.env._config = None

        # Change env var
        monkeypatch.setenv("MESH_TRANSPORT", "ble")

        config2 = get_config()
        assert config2.mesh_transport == "ble"
        assert config1 is not config2
