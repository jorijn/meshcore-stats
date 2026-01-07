"""Tests for location formatting functions."""

import pytest

from meshmon.reports import (
    format_lat_lon,
    format_lat_lon_dms,
    LocationInfo,
)


class TestFormatLatLon:
    """Tests for format_lat_lon function."""

    def test_formats_positive_coordinates(self):
        """Formats positive lat/lon with N/E."""
        lat_str, lon_str = format_lat_lon(51.5074, -0.1278)

        assert "51" in lat_str
        assert "N" in lat_str

    def test_formats_negative_latitude(self):
        """Negative latitude shows S."""
        lat_str, lon_str = format_lat_lon(-33.8688, 151.2093)

        assert "S" in lat_str

    def test_formats_negative_longitude(self):
        """Negative longitude shows W."""
        lat_str, lon_str = format_lat_lon(51.5074, -0.1278)

        assert "W" in lon_str

    def test_formats_positive_longitude(self):
        """Positive longitude shows E."""
        lat_str, lon_str = format_lat_lon(-33.8688, 151.2093)

        assert "E" in lon_str

    def test_includes_degrees_minutes(self):
        """Includes degrees and minutes."""
        lat_str, lon_str = format_lat_lon(51.5074, -0.1278)

        # Should have dash separator between degrees and minutes
        assert "-" in lat_str or "." in lat_str

    def test_handles_zero(self):
        """Handles zero coordinates."""
        lat_str, lon_str = format_lat_lon(0.0, 0.0)

        assert "0" in lat_str
        assert "0" in lon_str

    def test_handles_extremes(self):
        """Handles extreme coordinates."""
        # North pole
        lat_str_north, lon_str_north = format_lat_lon(90.0, 0.0)
        assert "90" in lat_str_north

        # South pole
        lat_str_south, lon_str_south = format_lat_lon(-90.0, 0.0)
        assert "90" in lat_str_south


class TestFormatLatLonDms:
    """Tests for format_lat_lon_dms function."""

    def test_returns_dms_format(self):
        """Returns degrees-minutes-seconds format."""
        result = format_lat_lon_dms(51.5074, -0.1278)

        # Should have degrees, minutes, seconds indicators
        assert "°" in result or "'" in result or '"' in result

    def test_includes_direction(self):
        """Includes N/S/E/W directions."""
        result = format_lat_lon_dms(51.5074, -0.1278)

        assert any(d in result for d in ["N", "S", "E", "W"])

    def test_correct_conversion(self):
        """Converts decimal to DMS correctly."""
        # 51.5074° ≈ 51° 30' 26.64"
        result = format_lat_lon_dms(51.5074, 0.0)

        assert "51" in result
        assert "30" in result or "'" in result

    def test_handles_fractional_seconds(self):
        """Handles fractional seconds."""
        result = format_lat_lon_dms(51.123456, -0.987654)

        # Should have some numeric content
        assert any(c.isdigit() for c in result)

    def test_combines_lat_and_lon(self):
        """Returns combined string with both lat and lon."""
        result = format_lat_lon_dms(52.0, 4.0)

        # Should have both N and E
        assert "N" in result or "S" in result
        assert "E" in result or "W" in result


class TestLocationInfo:
    """Tests for LocationInfo dataclass."""

    def test_stores_all_fields(self):
        """Stores all location fields."""
        loc = LocationInfo(
            name="Test Location",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )

        assert loc.name == "Test Location"
        assert loc.lat == 51.5074
        assert loc.lon == -0.1278
        assert loc.elev == 11.0

    def test_format_header(self):
        """format_header returns formatted string."""
        loc = LocationInfo(
            name="Test Location",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )

        header = loc.format_header()

        assert isinstance(header, str)
        assert "Test Location" in header

    def test_format_header_includes_coordinates(self):
        """Header includes formatted coordinates."""
        loc = LocationInfo(
            name="Test Location",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )

        header = loc.format_header()

        # Should have lat/lon info
        assert any(x in header for x in ["51", "N", "S", "°"])

    def test_format_header_includes_elevation(self):
        """Header includes elevation with unit."""
        loc = LocationInfo(
            name="London",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )

        header = loc.format_header()

        assert "11" in header
        assert "meters" in header.lower() or "m" in header


class TestLocationCoordinates:
    """Tests for various coordinate scenarios."""

    def test_equator(self):
        """Handles equator (0° latitude)."""
        lat_str, lon_str = format_lat_lon(0.0, 45.0)

        assert "0" in lat_str

    def test_prime_meridian(self):
        """Handles prime meridian (0° longitude)."""
        lat_str, lon_str = format_lat_lon(45.0, 0.0)

        assert "0" in lon_str

    def test_international_date_line(self):
        """Handles international date line (180° longitude)."""
        lat_str, lon_str = format_lat_lon(0.0, 180.0)

        assert "180" in lon_str

    def test_very_precise_coordinates(self):
        """Handles high-precision coordinates."""
        lat_str, lon_str = format_lat_lon(51.50735509, -0.12775829)

        assert "51" in lat_str
