"""Tests for reports formatting functions in reports.py."""

from datetime import datetime

import pytest

from meshmon.reports import (
    Column,
    LocationInfo,
    MetricStats,
    _compute_counter_stats,
    _compute_gauge_stats,
    _format_row,
    _format_separator,
    _get_bat_v,
    _validate_role,
    compute_counter_total,
    format_lat_lon,
    format_lat_lon_dms,
)


class TestFormatLatLon:
    """Test format_lat_lon function."""

    def test_north_east(self):
        """Positive lat/lon formats as N/E."""
        lat_str, lon_str = format_lat_lon(51.5074, 0.1278)
        assert lat_str == "51-30.44 N"
        assert lon_str == "000-07.67 E"

    def test_south_west(self):
        """Negative lat/lon formats as S/W."""
        lat_str, lon_str = format_lat_lon(-33.8688, -151.2093)
        assert lat_str == "33-52.13 S"
        assert lon_str == "151-12.56 W"

    def test_degrees_minutes_format(self):
        """Output is in DD-MM.MM format."""
        lat_str, lon_str = format_lat_lon(51.5074, -0.1278)
        assert lat_str == "51-30.44 N"
        assert lon_str == "000-07.67 W"

    def test_zero_coordinates(self):
        """Zero coordinates at equator/prime meridian."""
        lat_str, lon_str = format_lat_lon(0.0, 0.0)
        assert lat_str == "00-00.00 N"
        assert lon_str == "000-00.00 E"

    def test_latitude_format_width(self):
        """Latitude degrees is 2 digits."""
        lat_str, _ = format_lat_lon(5.5, 0.0)
        assert lat_str == "05-30.00 N"

    def test_longitude_format_width(self):
        """Longitude degrees is 3 digits."""
        _, lon_str = format_lat_lon(0.0, 5.5)
        assert lon_str == "005-30.00 E"


class TestFormatLatLonDms:
    """Test format_lat_lon_dms function."""

    def test_basic_format(self):
        """Returns combined DMS string."""
        result = format_lat_lon_dms(51.5074, -0.1278)
        assert result == "51°30'26\"N  000°07'40\"W"

    def test_north_east_directions(self):
        """Positive coordinates show N and E."""
        result = format_lat_lon_dms(51.5074, 0.1278)
        assert result == "51°30'26\"N  000°07'40\"E"

    def test_south_west_directions(self):
        """Negative coordinates show S and W."""
        result = format_lat_lon_dms(-33.8688, -151.2093)
        assert result == "33°52'07\"S  151°12'33\"W"

    def test_lat_two_digit_degrees(self):
        """Latitude has 2-digit degrees."""
        result = format_lat_lon_dms(5.0, 0.0)
        assert result == "05°00'00\"N  000°00'00\"E"

    def test_lon_three_digit_degrees(self):
        """Longitude has 3-digit degrees."""
        result = format_lat_lon_dms(0.0, 5.0)
        assert result == "00°00'00\"N  005°00'00\"E"


class TestLocationInfo:
    """Test LocationInfo dataclass."""

    def test_format_header(self):
        """format_header returns multi-line header."""
        loc = LocationInfo(
            name="Test Station",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )
        header = loc.format_header()

        assert (
            header
            == "NAME: Test Station\n"
            "COORDS: 51°30'26\"N  000°07'40\"W    ELEV: 11 meters"
        )

    def test_format_header_with_coordinates(self):
        """Header includes DMS coordinates."""
        loc = LocationInfo(
            name="Test",
            lat=51.5074,
            lon=-0.1278,
            elev=0.0,
        )
        header = loc.format_header()
        assert (
            header
            == "NAME: Test\n"
            "COORDS: 51°30'26\"N  000°07'40\"W    ELEV: 0 meters"
        )


class TestColumn:
    """Test Column dataclass."""

    def test_format_none(self):
        """None value formats as dash."""
        col = Column(width=6)
        result = col.format(None)
        assert result == "     -"  # Right-aligned, 6 chars

    def test_format_int(self):
        """Integer formats right-aligned."""
        col = Column(width=6)
        result = col.format(42)
        assert result == "    42"

    def test_format_int_with_comma(self):
        """Large integer with comma separator."""
        col = Column(width=10, comma_sep=True)
        result = col.format(1234567)
        assert result == " 1,234,567"

    def test_format_float(self):
        """Float formats with decimals."""
        col = Column(width=8, decimals=2)
        result = col.format(3.14159)
        assert result == "    3.14"

    def test_format_string(self):
        """String formats directly."""
        col = Column(width=10)
        result = col.format("hello")
        assert result == "     hello"

    def test_align_left(self):
        """Left alignment works."""
        col = Column(width=10, align="left")
        result = col.format("test")
        assert result == "test      "

    def test_align_center(self):
        """Center alignment works."""
        col = Column(width=10, align="center")
        result = col.format("hi")
        assert result == "    hi    "


class TestFormatRow:
    """Test _format_row function."""

    def test_formats_values(self):
        """Formats all values using column specs."""
        cols = [Column(4), Column(6, decimals=1), Column(8, comma_sep=True)]
        values = [1, 3.14, 12345]
        result = _format_row(cols, values)

        assert result == "   1   3.1  12,345"

    def test_total_width(self):
        """Row has correct total width."""
        cols = [Column(5), Column(10), Column(7)]
        values = ["a", "b", "c"]
        result = _format_row(cols, values)
        assert len(result) == 22


class TestFormatSeparator:
    """Test _format_separator function."""

    def test_default_char(self):
        """Default separator is dashes."""
        cols = [Column(5), Column(10)]
        result = _format_separator(cols)
        assert result == "---------------"

    def test_custom_char(self):
        """Custom separator character works."""
        cols = [Column(5), Column(5)]
        result = _format_separator(cols, "=")
        assert result == "=========="


class TestGetBatV:
    """Test _get_bat_v function."""

    def test_companion_battery_field(self):
        """Companion uses battery_mv field."""
        metrics = {
            "battery_mv": MetricStats(mean=3850.0, count=10)
        }
        result = _get_bat_v(metrics, "companion")
        assert result.mean == pytest.approx(3.85)

    def test_repeater_battery_field(self):
        """Repeater uses bat field."""
        metrics = {
            "bat": MetricStats(mean=4200.0, count=10)
        }
        result = _get_bat_v(metrics, "repeater")
        assert result.mean == pytest.approx(4.2)

    def test_converts_mv_to_v(self):
        """All values are converted from mV to V."""
        metrics = {
            "bat": MetricStats(
                mean=3850.0,
                min_value=3500.0,
                max_value=4200.0,
                min_time=datetime(2024, 1, 1, 5, 0),
                max_time=datetime(2024, 1, 1, 18, 0),
                count=100,
            )
        }
        result = _get_bat_v(metrics, "repeater")

        assert result.mean == pytest.approx(3.85)
        assert result.min_value == pytest.approx(3.5)
        assert result.max_value == pytest.approx(4.2)
        assert result.min_time == datetime(2024, 1, 1, 5, 0)
        assert result.max_time == datetime(2024, 1, 1, 18, 0)
        assert result.count == 100

    def test_missing_field_returns_empty(self):
        """Missing field returns empty MetricStats."""
        result = _get_bat_v({}, "companion")
        assert not result.has_data

    def test_no_data_returns_original(self):
        """Stats with no data returns unchanged."""
        metrics = {
            "bat": MetricStats()  # Empty
        }
        result = _get_bat_v(metrics, "repeater")
        assert not result.has_data


class TestComputeCounterTotal:
    """Test compute_counter_total function."""

    def test_empty_returns_none(self):
        """Empty list returns (None, 0)."""
        total, reboots = compute_counter_total([])
        assert total is None
        assert reboots == 0

    def test_single_value_returns_none(self):
        """Single value cannot compute delta."""
        values = [(datetime(2024, 1, 1), 100)]
        total, reboots = compute_counter_total(values)
        assert total is None
        assert reboots == 0

    def test_normal_increase(self):
        """Normal counter increases sum correctly."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 150),
            (datetime(2024, 1, 1, 2, 0), 200),
        ]
        total, reboots = compute_counter_total(values)
        assert total == 100  # 50 + 50
        assert reboots == 0

    def test_reboot_detected(self):
        """Negative delta indicates reboot."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 150),  # +50
            (datetime(2024, 1, 1, 2, 0), 20),   # Reboot! Add 20
            (datetime(2024, 1, 1, 3, 0), 50),   # +30
        ]
        total, reboots = compute_counter_total(values)
        assert total == 50 + 20 + 30  # 100
        assert reboots == 1

    def test_multiple_reboots(self):
        """Multiple reboots tracked correctly."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 10),   # Reboot
            (datetime(2024, 1, 1, 2, 0), 50),
            (datetime(2024, 1, 1, 3, 0), 5),    # Reboot
            (datetime(2024, 1, 1, 4, 0), 25),
        ]
        total, reboots = compute_counter_total(values)
        assert reboots == 2

    def test_no_change(self):
        """Zero delta (no change) is valid."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 100),
            (datetime(2024, 1, 1, 2, 0), 100),
        ]
        total, reboots = compute_counter_total(values)
        assert total == 0
        assert reboots == 0


class TestComputeGaugeStats:
    """Test _compute_gauge_stats function."""

    def test_empty_returns_empty(self):
        """Empty list returns empty stats."""
        stats = _compute_gauge_stats([])
        assert not stats.has_data

    def test_single_value(self):
        """Single value sets min=max=mean."""
        dt = datetime(2024, 1, 1, 12, 0)
        values = [(dt, 3.85)]
        stats = _compute_gauge_stats(values)

        assert stats.mean == 3.85
        assert stats.min_value == 3.85
        assert stats.max_value == 3.85
        assert stats.min_time == dt
        assert stats.max_time == dt
        assert stats.count == 1

    def test_multiple_values(self):
        """Multiple values compute correct stats."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 3.5),
            (datetime(2024, 1, 1, 6, 0), 4.0),
            (datetime(2024, 1, 1, 12, 0), 3.8),
            (datetime(2024, 1, 1, 18, 0), 4.2),
        ]
        stats = _compute_gauge_stats(values)

        assert stats.mean == pytest.approx(3.875)  # (3.5+4.0+3.8+4.2)/4
        assert stats.min_value == 3.5
        assert stats.max_value == 4.2
        assert stats.min_time == datetime(2024, 1, 1, 0, 0)
        assert stats.max_time == datetime(2024, 1, 1, 18, 0)
        assert stats.count == 4


class TestComputeCounterStats:
    """Test _compute_counter_stats function."""

    def test_empty_returns_empty(self):
        """Empty list returns empty stats."""
        stats = _compute_counter_stats([])
        assert not stats.has_data

    def test_single_value(self):
        """Single value has count but no total."""
        values = [(datetime(2024, 1, 1), 100)]
        stats = _compute_counter_stats(values)
        assert stats.total is None
        assert stats.count == 1

    def test_computes_total_and_reboots(self):
        """Total and reboot count computed correctly."""
        values = [
            (datetime(2024, 1, 1, 0, 0), 100),
            (datetime(2024, 1, 1, 1, 0), 200),  # +100
            (datetime(2024, 1, 1, 2, 0), 50),   # Reboot, +50
        ]
        stats = _compute_counter_stats(values)

        assert stats.total == 150
        assert stats.reboot_count == 1
        assert stats.count == 3


class TestValidateRole:
    """Test _validate_role function."""

    def test_valid_companion(self):
        """'companion' is valid."""
        result = _validate_role("companion")
        assert result == "companion"

    def test_valid_repeater(self):
        """'repeater' is valid."""
        result = _validate_role("repeater")
        assert result == "repeater"

    def test_invalid_raises(self):
        """Invalid role raises ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("invalid")

    def test_sql_injection_blocked(self):
        """SQL injection attempt raises ValueError."""
        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("'; DROP TABLE metrics; --")


class TestMetricStats:
    """Test MetricStats dataclass."""

    def test_has_data_false_when_empty(self):
        """has_data is False when count is 0."""
        stats = MetricStats()
        assert stats.has_data is False

    def test_has_data_true_when_populated(self):
        """has_data is True when count > 0."""
        stats = MetricStats(count=1)
        assert stats.has_data is True

    def test_defaults(self):
        """Default values are None/0."""
        stats = MetricStats()
        assert stats.mean is None
        assert stats.min_value is None
        assert stats.max_value is None
        assert stats.total is None
        assert stats.count == 0
        assert stats.reboot_count == 0
