"""Tests for HTML formatting functions in html.py."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from meshmon.html import (
    STATUS_ONLINE_THRESHOLD,
    STATUS_STALE_THRESHOLD,
    _fmt_val_day,
    _fmt_val_month,
    _fmt_val_plain,
    _fmt_val_time,
    _format_stat_value,
    _load_svg_content,
    get_status,
)

BASE_NOW = datetime(2024, 1, 2, 12, 0, 0)


@pytest.fixture
def fixed_now(monkeypatch):
    """Freeze meshmon.html datetime.now() for deterministic status tests."""
    import meshmon.html

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return BASE_NOW if tz is None else BASE_NOW.astimezone(tz)

    monkeypatch.setattr(meshmon.html, "datetime", FixedDatetime)
    return BASE_NOW

class TestFormatStatValue:
    """Test _format_stat_value function."""

    def test_none_returns_dash(self):
        """None value returns dash."""
        assert _format_stat_value(None, "bat") == "-"
        assert _format_stat_value(None, "last_rssi") == "-"

    def test_battery_voltage(self):
        """Battery voltage metrics format as V with 2 decimals."""
        assert _format_stat_value(3.85, "bat") == "3.85 V"
        assert _format_stat_value(4.20, "battery_mv") == "4.20 V"

    def test_battery_percentage(self):
        """Battery percentage formats as % with no decimals."""
        assert _format_stat_value(85.5, "bat_pct") == "86%"
        assert _format_stat_value(100.0, "bat_pct") == "100%"

    def test_rssi(self):
        """RSSI formats as dBm with no decimals."""
        assert _format_stat_value(-85.3, "last_rssi") == "-85 dBm"

    def test_noise_floor(self):
        """Noise floor formats as dBm with no decimals."""
        assert _format_stat_value(-115.7, "noise_floor") == "-116 dBm"

    def test_snr(self):
        """SNR formats as dB with 1 decimal."""
        assert _format_stat_value(7.53, "last_snr") == "7.5 dB"

    def test_contacts(self):
        """Contacts format as integer."""
        assert _format_stat_value(5.0, "contacts") == "5"

    def test_tx_queue(self):
        """TX queue formats as integer."""
        assert _format_stat_value(3.0, "tx_queue_len") == "3"

    def test_uptime(self):
        """Uptime formats as days with 1 decimal."""
        assert _format_stat_value(7.5, "uptime") == "7.5 d"
        assert _format_stat_value(2.3, "uptime_secs") == "2.3 d"

    def test_packet_counters(self):
        """Packet counters format as per-minute rate."""
        assert _format_stat_value(12.5, "recv") == "12.5/min"
        assert _format_stat_value(8.3, "sent") == "8.3/min"
        assert _format_stat_value(100.0, "nb_recv") == "100.0/min"
        assert _format_stat_value(50.2, "nb_sent") == "50.2/min"

    def test_flood_counters(self):
        """Flood packet counters format as per-minute rate."""
        assert _format_stat_value(5.0, "recv_flood") == "5.0/min"
        assert _format_stat_value(3.2, "sent_flood") == "3.2/min"

    def test_direct_counters(self):
        """Direct packet counters format as per-minute rate."""
        assert _format_stat_value(2.1, "recv_direct") == "2.1/min"
        assert _format_stat_value(1.8, "sent_direct") == "1.8/min"

    def test_dups_counters(self):
        """Duplicate counters format as per-minute rate."""
        assert _format_stat_value(0.5, "flood_dups") == "0.5/min"
        assert _format_stat_value(0.1, "direct_dups") == "0.1/min"

    def test_airtime(self):
        """Airtime formats as seconds per minute."""
        assert _format_stat_value(2.5, "airtime") == "2.5 s/min"
        assert _format_stat_value(5.0, "rx_airtime") == "5.0 s/min"

    def test_unknown_metric(self):
        """Unknown metrics format with 2 decimals."""
        assert _format_stat_value(123.456, "unknown_metric") == "123.46"

    def test_telemetry_metric_units_and_decimals_metric(self, monkeypatch):
        """Telemetry metrics use metric units when DISPLAY_UNIT_SYSTEM=metric."""
        monkeypatch.setenv("DISPLAY_UNIT_SYSTEM", "metric")
        import meshmon.env
        meshmon.env._config = None

        assert _format_stat_value(20.0, "telemetry.temperature.1") == "20.0 °C"
        assert _format_stat_value(85.0, "telemetry.humidity.1") == "85.0 %"
        assert _format_stat_value(1008.1, "telemetry.barometer.1") == "1008.1 hPa"
        assert _format_stat_value(42.0, "telemetry.altitude.1") == "42.0 m"

    def test_telemetry_metric_units_and_decimals_imperial(self, monkeypatch):
        """Telemetry metrics format imperial display values with imperial units."""
        monkeypatch.setenv("DISPLAY_UNIT_SYSTEM", "imperial")
        import meshmon.env
        meshmon.env._config = None

        # Chart stats are already converted in charts.py; formatter should not convert again.
        assert _format_stat_value(68.0, "telemetry.temperature.1") == "68.0 °F"
        assert _format_stat_value(29.77, "telemetry.barometer.1") == "29.77 inHg"
        assert _format_stat_value(137.8, "telemetry.altitude.1") == "137.8 ft"
        assert _format_stat_value(85.0, "telemetry.humidity.1") == "85.0 %"


class TestLoadSvgContent:
    """Test _load_svg_content function."""

    def test_nonexistent_file_returns_none(self, tmp_path):
        """Non-existent file returns None."""
        result = _load_svg_content(tmp_path / "nonexistent.svg")
        assert result is None

    def test_loads_svg_content(self, tmp_path):
        """Existing file content is loaded."""
        svg_file = tmp_path / "test.svg"
        svg_content = '<svg xmlns="http://www.w3.org/2000/svg"><rect/></svg>'
        svg_file.write_text(svg_content)

        result = _load_svg_content(svg_file)
        assert result == svg_content

    def test_read_error_returns_none(self, tmp_path):
        """Read errors return None (logged)."""
        svg_file = tmp_path / "test.svg"
        svg_file.write_text("content")

        # Make file unreadable by mocking
        with patch.object(Path, "read_text", side_effect=PermissionError("denied")):
            result = _load_svg_content(svg_file)
            assert result is None


class TestFmtValTime:
    """Test _fmt_val_time function."""

    def test_none_returns_dash(self):
        """None value returns dash."""
        assert _fmt_val_time(None, BASE_NOW) == "-"

    def test_formats_value_with_time(self):
        """Formats value with time in small tag."""
        dt = datetime(2024, 6, 15, 14, 30, 45)
        result = _fmt_val_time(3.85, dt)
        assert "3.85" in result
        assert "<small>14:30</small>" in result

    def test_custom_format(self):
        """Custom value format works."""
        dt = datetime(2024, 6, 15, 14, 30)
        result = _fmt_val_time(3.8567, dt, fmt=".3f")
        assert "3.857" in result

    def test_custom_time_format(self):
        """Custom time format works."""
        dt = datetime(2024, 6, 15, 14, 30)
        result = _fmt_val_time(3.85, dt, time_fmt="%H:%M:%S")
        assert "14:30:00" in result

    def test_none_time_obj(self):
        """None time object returns value without time."""
        result = _fmt_val_time(3.85, None)
        assert result == "3.85"


class TestFmtValDay:
    """Test _fmt_val_day function."""

    def test_none_returns_dash(self):
        """None value returns dash."""
        assert _fmt_val_day(None, BASE_NOW) == "-"

    def test_formats_value_with_day(self):
        """Formats value with day number in small tag."""
        dt = datetime(2024, 6, 15)
        result = _fmt_val_day(3.85, dt)
        assert "3.85" in result
        assert "<small>15</small>" in result

    def test_day_zero_padded(self):
        """Day number is zero-padded."""
        dt = datetime(2024, 6, 5)
        result = _fmt_val_day(3.85, dt)
        assert "<small>05</small>" in result

    def test_custom_format(self):
        """Custom value format works."""
        dt = datetime(2024, 6, 15)
        result = _fmt_val_day(3.8567, dt, fmt=".1f")
        assert "3.9" in result

    def test_none_time_obj(self):
        """None time object returns value without day."""
        result = _fmt_val_day(3.85, None)
        assert result == "3.85"


class TestFmtValMonth:
    """Test _fmt_val_month function."""

    def test_none_returns_dash(self):
        """None value returns dash."""
        assert _fmt_val_month(None, BASE_NOW) == "-"

    def test_formats_value_with_month(self):
        """Formats value with month abbreviation in small tag."""
        dt = datetime(2024, 6, 15)
        result = _fmt_val_month(3.85, dt)
        assert "3.85" in result
        assert "<small>Jun</small>" in result

    def test_january(self):
        """January formats correctly."""
        dt = datetime(2024, 1, 15)
        result = _fmt_val_month(3.85, dt)
        assert "<small>Jan</small>" in result

    def test_december(self):
        """December formats correctly."""
        dt = datetime(2024, 12, 15)
        result = _fmt_val_month(3.85, dt)
        assert "<small>Dec</small>" in result

    def test_none_time_obj(self):
        """None time object returns value without month."""
        result = _fmt_val_month(3.85, None)
        assert result == "3.85"


class TestFmtValPlain:
    """Test _fmt_val_plain function."""

    def test_none_returns_dash(self):
        """None value returns dash."""
        assert _fmt_val_plain(None) == "-"

    def test_default_two_decimals(self):
        """Default format is 2 decimal places."""
        assert _fmt_val_plain(3.8567) == "3.86"

    def test_custom_format(self):
        """Custom format works."""
        assert _fmt_val_plain(3.8567, fmt=".1f") == "3.9"
        assert _fmt_val_plain(3.8567, fmt=".0f") == "4"
        assert _fmt_val_plain(3.8567, fmt=".4f") == "3.8567"


class TestGetStatus:
    """Test get_status function."""

    def test_none_timestamp(self):
        """None timestamp returns offline."""
        status_class, status_text = get_status(None)
        assert status_class == "offline"
        assert status_text == "No data"

    def test_zero_timestamp(self):
        """Zero timestamp (falsy) returns offline."""
        status_class, status_text = get_status(0)
        assert status_class == "offline"
        assert status_text == "No data"

    def test_recent_timestamp_online(self, fixed_now):
        """Recent timestamp (< 30 min) returns online."""
        recent_ts = int(fixed_now.timestamp()) - 60  # 1 minute ago
        status_class, status_text = get_status(recent_ts)
        assert status_class == "online"
        assert status_text == "Online"

    def test_stale_timestamp(self, fixed_now):
        """Stale timestamp (30 min - 2 hours) returns stale."""
        stale_ts = int(fixed_now.timestamp()) - (STATUS_ONLINE_THRESHOLD + 60)
        status_class, status_text = get_status(stale_ts)
        assert status_class == "stale"
        assert status_text == "Stale"

    def test_old_timestamp_offline(self, fixed_now):
        """Old timestamp (> 2 hours) returns offline."""
        old_ts = int(fixed_now.timestamp()) - (STATUS_STALE_THRESHOLD + 60)
        status_class, status_text = get_status(old_ts)
        assert status_class == "offline"
        assert status_text == "Offline"

    def test_exactly_at_threshold(self, fixed_now):
        """Timestamps exactly at thresholds."""
        now = int(fixed_now.timestamp())

        # Just under online threshold - still online
        ts_just_online = now - STATUS_ONLINE_THRESHOLD + 1
        status, _ = get_status(ts_just_online)
        assert status == "online"

        # Just under stale threshold - still stale
        ts_just_stale = now - STATUS_STALE_THRESHOLD + 1
        status, _ = get_status(ts_just_stale)
        assert status == "stale"
