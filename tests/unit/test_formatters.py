"""Tests for shared formatting functions."""

from datetime import datetime

from meshmon.formatters import (
    format_compact_number,
    format_duration,
    format_duration_compact,
    format_number,
    format_time,
    format_uptime,
    format_value,
    format_voltage_with_pct,
)


class TestFormatTime:
    """Test format_time function."""

    def test_none_returns_na(self):
        """None timestamp returns N/A."""
        assert format_time(None) == "N/A"

    def test_valid_timestamp(self):
        """Valid timestamp formats correctly."""
        ts = int(datetime(2024, 1, 2, 3, 4, 5).timestamp())
        result = format_time(ts)
        assert result == "2024-01-02 03:04:05"

    def test_zero_timestamp(self):
        """Zero timestamp (epoch) formats correctly."""
        result = format_time(0)
        assert "1970" in result

    def test_invalid_timestamp_returns_na(self):
        """Invalid timestamps return N/A."""
        # Extremely large value that causes OSError
        assert format_time(99999999999999) == "N/A"

    def test_negative_timestamp(self):
        """Negative timestamp (before epoch) should work or return N/A."""
        result = format_time(-86400)
        # Either formats pre-epoch time or returns N/A (platform-dependent)
        assert result == "N/A" or "1969" in result


class TestFormatValue:
    """Test format_value function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_value(None) == "N/A"

    def test_float_two_decimals(self):
        """Float values are formatted to 2 decimal places."""
        assert format_value(3.14159) == "3.14"
        assert format_value(0.0) == "0.00"
        assert format_value(100.999) == "101.00"

    def test_integer_unchanged(self):
        """Integer values are converted to string."""
        assert format_value(42) == "42"
        assert format_value(0) == "0"

    def test_string_unchanged(self):
        """String values pass through."""
        assert format_value("hello") == "hello"

    def test_negative_float(self):
        """Negative floats format correctly."""
        assert format_value(-12.345) == "-12.35"


class TestFormatNumber:
    """Test format_number function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_number(None) == "N/A"

    def test_small_numbers(self):
        """Small numbers without separators."""
        assert format_number(0) == "0"
        assert format_number(999) == "999"

    def test_thousands_separator(self):
        """Numbers >= 1000 get comma separators."""
        assert format_number(1000) == "1,000"
        assert format_number(1234567) == "1,234,567"

    def test_negative_numbers(self):
        """Negative numbers format correctly."""
        assert format_number(-1234) == "-1,234"


class TestFormatDuration:
    """Test format_duration function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_duration(None) == "N/A"

    def test_zero_seconds(self):
        """Zero seconds shows just 0s."""
        assert format_duration(0) == "0s"

    def test_seconds_only(self):
        """Less than a minute shows seconds only."""
        result = format_duration(45)
        assert result == "45s"

    def test_minutes_and_seconds(self):
        """Minutes and seconds format."""
        result = format_duration(125)  # 2m 5s
        assert result == "2m 5s"

    def test_hours_minutes_seconds(self):
        """Hours, minutes, and seconds format."""
        result = format_duration(3725)  # 1h 2m 5s
        assert result == "1h 2m 5s"

    def test_days_hours_minutes_seconds(self):
        """Full duration with days."""
        result = format_duration(90125)  # 1d 1h 2m 5s
        assert result == "1d 1h 2m 5s"

    def test_exact_day(self):
        """Exactly one day."""
        result = format_duration(86400)
        assert result == "1d 0h 0m 0s"

    def test_multiple_days(self):
        """Multiple days."""
        result = format_duration(172800)  # 2 days
        assert result == "2d 0h 0m 0s"


class TestFormatUptime:
    """Test format_uptime function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_uptime(None) == "N/A"

    def test_zero_seconds(self):
        """Zero seconds shows just 0m."""
        assert format_uptime(0) == "0m"

    def test_under_minute(self):
        """Less than a minute shows 0m."""
        assert format_uptime(45) == "0m"

    def test_minutes_only(self):
        """Minutes only (no hours/days)."""
        assert format_uptime(120) == "2m"

    def test_hours_and_minutes(self):
        """Hours and minutes format."""
        result = format_uptime(3720)  # 1h 2m
        assert result == "1h 2m"

    def test_days_hours_minutes(self):
        """Days, hours, and minutes format (no seconds in uptime)."""
        result = format_uptime(90120)  # 1d 1h 2m
        assert result == "1d 1h 2m"

    def test_exact_hour(self):
        """Exactly one hour shows 0m."""
        result = format_uptime(3600)
        assert result == "1h 0m"


class TestFormatVoltageWithPct:
    """Test format_voltage_with_pct function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_voltage_with_pct(None) == "N/A"

    def test_full_battery(self):
        """Full battery (4200mV = 4.20V = 100%)."""
        result = format_voltage_with_pct(4200)
        assert "4.20 V" in result
        assert "100%" in result

    def test_empty_battery(self):
        """Empty battery (3000mV = 3.00V = 0%)."""
        result = format_voltage_with_pct(3000)
        assert "3.00 V" in result
        assert "0%" in result

    def test_mid_range_battery(self):
        """Mid-range battery shows voltage and percentage."""
        result = format_voltage_with_pct(3820)  # 50%
        assert "3.82 V" in result
        assert "50%" in result

    def test_format_structure(self):
        """Output matches expected format: X.XX V (XX%)."""
        result = format_voltage_with_pct(3850)
        assert " V (" in result
        assert result.endswith("%)")


class TestFormatCompactNumber:
    """Test format_compact_number function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_compact_number(None) == "N/A"

    def test_small_numbers_raw(self):
        """Numbers < 1000 shown as raw integers."""
        assert format_compact_number(0) == "0"
        assert format_compact_number(847) == "847"
        assert format_compact_number(999) == "999"

    def test_thousands_with_comma(self):
        """1000-9999 shown with comma separator."""
        assert format_compact_number(1000) == "1,000"
        assert format_compact_number(4989) == "4,989"
        assert format_compact_number(9999) == "9,999"

    def test_tens_of_thousands_with_k(self):
        """10000-999999 shown with k suffix."""
        assert format_compact_number(10000) == "10.0k"
        assert format_compact_number(242100) == "242.1k"
        assert format_compact_number(999999) == "1000.0k"

    def test_millions_with_m(self):
        """>= 1000000 shown with M suffix."""
        assert format_compact_number(1000000) == "1.0M"
        assert format_compact_number(1500000) == "1.5M"
        assert format_compact_number(25000000) == "25.0M"

    def test_custom_precision(self):
        """Custom precision affects decimal places."""
        assert format_compact_number(242156, precision=2) == "242.16k"
        assert format_compact_number(1234567, precision=2) == "1.23M"
        assert format_compact_number(10500, precision=0) == "10k"

    def test_negative_numbers(self):
        """Negative numbers get minus prefix."""
        assert format_compact_number(-500) == "-500"
        assert format_compact_number(-5000) == "-5,000"
        assert format_compact_number(-50000) == "-50.0k"
        assert format_compact_number(-5000000) == "-5.0M"

    def test_float_input(self):
        """Float inputs work correctly."""
        assert format_compact_number(1234.5) == "1,234"
        assert format_compact_number(12345.6) == "12.3k"


class TestFormatDurationCompact:
    """Test format_duration_compact function."""

    def test_none_returns_na(self):
        """None value returns N/A."""
        assert format_duration_compact(None) == "N/A"

    def test_zero_returns_0s(self):
        """Zero seconds returns 0s."""
        assert format_duration_compact(0) == "0s"

    def test_seconds_only(self):
        """Less than 60 seconds shows seconds only."""
        assert format_duration_compact(1) == "1s"
        assert format_duration_compact(45) == "45s"
        assert format_duration_compact(59) == "59s"

    def test_minutes_and_seconds(self):
        """1 minute to < 1 hour shows minutes and seconds."""
        assert format_duration_compact(60) == "1m 0s"
        assert format_duration_compact(125) == "2m 5s"
        assert format_duration_compact(3599) == "59m 59s"

    def test_hours_and_minutes(self):
        """1 hour to < 1 day shows hours and minutes."""
        assert format_duration_compact(3600) == "1h 0m"
        assert format_duration_compact(7260) == "2h 1m"
        assert format_duration_compact(86399) == "23h 59m"

    def test_days_and_hours(self):
        """1 day or more shows days and hours."""
        assert format_duration_compact(86400) == "1d 0h"
        assert format_duration_compact(90000) == "1d 1h"
        assert format_duration_compact(172800) == "2d 0h"
        assert format_duration_compact(259200) == "3d 0h"

    def test_truncation_not_rounding(self):
        """Verifies truncation behavior (floor)."""
        # 1d 23h 59m 59s should show as 1d 23h (not 2d 0h)
        result = format_duration_compact(86400 + 23 * 3600 + 59 * 60 + 59)
        assert result == "1d 23h"

    def test_large_durations(self):
        """Very large durations work correctly."""
        # 365 days
        result = format_duration_compact(365 * 86400)
        assert result == "365d 0h"
