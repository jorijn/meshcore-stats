"""Tests for location formatting functions."""


from meshmon.reports import (
    LocationInfo,
    format_lat_lon,
    format_lat_lon_dms,
)


class TestFormatLatLon:
    """Tests for format_lat_lon function."""

    def test_formats_positive_coordinates(self):
        """Formats positive lat/lon with N/E."""
        lat_str, lon_str = format_lat_lon(51.5074, 0.1278)

        assert lat_str == "51-30.44 N"
        assert lon_str == "000-07.67 E"

    def test_formats_negative_latitude(self):
        """Negative latitude shows S."""
        lat_str, lon_str = format_lat_lon(-33.8688, 151.2093)

        assert lat_str == "33-52.13 S"
        assert lon_str == "151-12.56 E"

    def test_formats_negative_longitude(self):
        """Negative longitude shows W."""
        lat_str, lon_str = format_lat_lon(51.5074, -0.1278)

        assert lon_str == "000-07.67 W"

    def test_formats_positive_longitude(self):
        """Positive longitude shows E."""
        lat_str, lon_str = format_lat_lon(0.0, 4.0)

        assert lon_str == "004-00.00 E"

    def test_includes_degrees_minutes(self):
        """Includes degrees and minutes."""
        lat_str, lon_str = format_lat_lon(3.5, 7.25)

        assert lat_str.startswith("03-")
        assert lon_str.startswith("007-")

    def test_handles_zero(self):
        """Handles zero coordinates."""
        lat_str, lon_str = format_lat_lon(0.0, 0.0)

        assert lat_str == "00-00.00 N"
        assert lon_str == "000-00.00 E"

    def test_handles_extremes(self):
        """Handles extreme coordinates."""
        # North pole
        lat_str_north, lon_str_north = format_lat_lon(90.0, 0.0)
        assert lat_str_north == "90-00.00 N"

        # South pole
        lat_str_south, lon_str_south = format_lat_lon(-90.0, 0.0)
        assert lat_str_south == "90-00.00 S"


class TestFormatLatLonDms:
    """Tests for format_lat_lon_dms function."""

    def test_returns_dms_format(self):
        """Returns degrees-minutes-seconds format."""
        result = format_lat_lon_dms(51.5074, -0.1278)

        assert result == "51°30'26\"N  000°07'40\"W"

    def test_includes_direction(self):
        """Includes N/S/E/W directions."""
        result = format_lat_lon_dms(51.5074, -0.1278)

        assert "N" in result
        assert "W" in result

    def test_correct_conversion(self):
        """Converts decimal to DMS correctly."""
        result = format_lat_lon_dms(0.0, 0.0)

        assert result == "00°00'00\"N  000°00'00\"E"

    def test_handles_fractional_seconds(self):
        """Handles fractional seconds."""
        result = format_lat_lon_dms(51.123456, -0.987654)

        assert result == "51°07'24\"N  000°59'15\"W"

    def test_combines_lat_and_lon(self):
        """Returns combined string with both lat and lon."""
        result = format_lat_lon_dms(52.0, 4.0)

        assert result == "52°00'00\"N  004°00'00\"E"


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

        assert header == (
            "NAME: Test Location\n"
            "COORDS: 51°30'26\"N  000°07'40\"W    ELEV: 11 meters"
        )

    def test_format_header_includes_coordinates(self):
        """Header includes formatted coordinates."""
        loc = LocationInfo(
            name="Test Location",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )

        header = loc.format_header()

        assert "COORDS: 51°30'26\"N  000°07'40\"W" in header

    def test_format_header_includes_elevation(self):
        """Header includes elevation with unit."""
        loc = LocationInfo(
            name="London",
            lat=51.5074,
            lon=-0.1278,
            elev=11.0,
        )

        header = loc.format_header()

        assert "ELEV: 11 meters" in header


class TestLocationCoordinates:
    """Tests for various coordinate scenarios."""

    def test_equator(self):
        """Handles equator (0° latitude)."""
        lat_str, lon_str = format_lat_lon(0.0, 45.0)

        assert lat_str == "00-00.00 N"
        assert lon_str == "045-00.00 E"

    def test_prime_meridian(self):
        """Handles prime meridian (0° longitude)."""
        lat_str, lon_str = format_lat_lon(45.0, 0.0)

        assert lat_str == "45-00.00 N"
        assert lon_str == "000-00.00 E"

    def test_international_date_line(self):
        """Handles international date line (180° longitude)."""
        lat_str, lon_str = format_lat_lon(0.0, 180.0)

        assert lat_str == "00-00.00 N"
        assert lon_str == "180-00.00 E"

    def test_very_precise_coordinates(self):
        """Handles high-precision coordinates."""
        lat_str, lon_str = format_lat_lon(51.50735509, -0.12775829)

        assert lat_str == "51-30.44 N"
        assert lon_str == "000-07.67 W"
