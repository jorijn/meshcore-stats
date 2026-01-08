"""Tests for telemetry data extraction from Cayenne LPP format."""

from meshmon.telemetry import extract_lpp_from_payload, extract_telemetry_metrics


class TestExtractLppFromPayload:
    """Test extract_lpp_from_payload function."""

    def test_dict_payload_with_lpp_key(self):
        """Extract LPP data from dict payload with 'lpp' key."""
        payload = {"pubkey_pre": "abc123", "lpp": [{"type": "temperature", "value": 23.5}]}
        result = extract_lpp_from_payload(payload)
        assert result == [{"type": "temperature", "value": 23.5}]

    def test_dict_payload_empty_lpp_list(self):
        """Extract empty LPP list from dict payload."""
        payload = {"pubkey_pre": "abc123", "lpp": []}
        result = extract_lpp_from_payload(payload)
        assert result == []

    def test_direct_list_payload(self):
        """Extract LPP data from direct list payload."""
        payload = [{"type": "humidity", "channel": 0, "value": 65.0}]
        result = extract_lpp_from_payload(payload)
        assert result == [{"type": "humidity", "channel": 0, "value": 65.0}]

    def test_none_payload(self):
        """None payload returns None."""
        result = extract_lpp_from_payload(None)
        assert result is None

    def test_dict_without_lpp_key(self):
        """Dict payload without 'lpp' key returns None."""
        payload = {"pubkey_pre": "abc123", "data": []}
        result = extract_lpp_from_payload(payload)
        assert result is None

    def test_dict_with_non_list_lpp(self):
        """Dict payload with non-list 'lpp' value returns None."""
        payload = {"lpp": "invalid"}
        result = extract_lpp_from_payload(payload)
        assert result is None

    def test_unexpected_type_returns_none(self):
        """Unexpected payload type (string, int, etc.) returns None."""
        assert extract_lpp_from_payload("string") is None
        assert extract_lpp_from_payload(12345) is None
        assert extract_lpp_from_payload(12.34) is None

    def test_empty_dict(self):
        """Empty dict returns None."""
        result = extract_lpp_from_payload({})
        assert result is None


class TestExtractTelemetryMetrics:
    """Test extract_telemetry_metrics function."""

    # ==========================================================================
    # Basic scalar values
    # ==========================================================================

    def test_temperature_reading(self):
        """Extract temperature reading."""
        lpp_data = [{"type": "temperature", "channel": 0, "value": 23.5}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.temperature.0": 23.5}

    def test_humidity_reading(self):
        """Extract humidity reading."""
        lpp_data = [{"type": "humidity", "channel": 0, "value": 65}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.humidity.0": 65.0}

    def test_barometer_reading(self):
        """Extract barometer/pressure reading."""
        lpp_data = [{"type": "barometer", "channel": 0, "value": 1013.25}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.barometer.0": 1013.25}

    def test_multiple_channels(self):
        """Different channels produce different metric keys."""
        lpp_data = [
            {"type": "temperature", "channel": 0, "value": 23.5},
            {"type": "temperature", "channel": 1, "value": 25.0},
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {
            "telemetry.temperature.0": 23.5,
            "telemetry.temperature.1": 25.0,
        }

    def test_default_channel_zero(self):
        """Missing channel defaults to 0."""
        lpp_data = [{"type": "temperature", "value": 20.0}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.temperature.0": 20.0}

    # ==========================================================================
    # Compound values (GPS, etc.)
    # ==========================================================================

    def test_gps_compound_value(self):
        """Extract GPS reading with nested lat/lon/alt."""
        lpp_data = [
            {
                "type": "gps",
                "channel": 0,
                "value": {"latitude": 51.5074, "longitude": -0.1278, "altitude": 11.0},
            }
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {
            "telemetry.gps.0.latitude": 51.5074,
            "telemetry.gps.0.longitude": -0.1278,
            "telemetry.gps.0.altitude": 11.0,
        }

    def test_accelerometer_compound_value(self):
        """Extract accelerometer reading with x/y/z axes."""
        lpp_data = [
            {
                "type": "accelerometer",
                "channel": 0,
                "value": {"x": 0.02, "y": -0.01, "z": 9.81},
            }
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {
            "telemetry.accelerometer.0.x": 0.02,
            "telemetry.accelerometer.0.y": -0.01,
            "telemetry.accelerometer.0.z": 9.81,
        }

    # ==========================================================================
    # Boolean values
    # ==========================================================================

    def test_boolean_true_value(self):
        """Boolean True is converted to 1.0."""
        lpp_data = [{"type": "digital_input", "channel": 0, "value": True}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.digital_input.0": 1.0}

    def test_boolean_false_value(self):
        """Boolean False is converted to 0.0."""
        lpp_data = [{"type": "digital_input", "channel": 0, "value": False}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.digital_input.0": 0.0}

    def test_boolean_in_compound_value(self):
        """Boolean in nested dict is converted to float."""
        lpp_data = [
            {
                "type": "status",
                "channel": 0,
                "value": {"active": True, "error": False},
            }
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {
            "telemetry.status.0.active": 1.0,
            "telemetry.status.0.error": 0.0,
        }

    # ==========================================================================
    # Type normalization
    # ==========================================================================

    def test_type_normalized_lowercase(self):
        """Sensor type is converted to lowercase."""
        lpp_data = [{"type": "TEMPERATURE", "channel": 0, "value": 23.5}]
        result = extract_telemetry_metrics(lpp_data)
        assert "telemetry.temperature.0" in result

    def test_type_normalized_spaces_to_underscores(self):
        """Spaces in sensor type are converted to underscores."""
        lpp_data = [{"type": "analog input", "channel": 0, "value": 3.3}]
        result = extract_telemetry_metrics(lpp_data)
        assert "telemetry.analog_input.0" in result

    def test_type_trimmed(self):
        """Whitespace around type is trimmed."""
        lpp_data = [{"type": "  temperature  ", "channel": 0, "value": 23.5}]
        result = extract_telemetry_metrics(lpp_data)
        assert "telemetry.temperature.0" in result

    # ==========================================================================
    # Invalid/edge cases
    # ==========================================================================

    def test_empty_list(self):
        """Empty LPP list returns empty dict."""
        result = extract_telemetry_metrics([])
        assert result == {}

    def test_non_list_input(self):
        """Non-list input returns empty dict."""
        result = extract_telemetry_metrics({"type": "temperature"})
        assert result == {}
        result = extract_telemetry_metrics("invalid")
        assert result == {}
        result = extract_telemetry_metrics(None)
        assert result == {}

    def test_skips_non_dict_readings(self):
        """Non-dict entries in list are skipped."""
        lpp_data = [
            {"type": "temperature", "channel": 0, "value": 23.5},
            "invalid_entry",
            {"type": "humidity", "channel": 0, "value": 65.0},
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {
            "telemetry.temperature.0": 23.5,
            "telemetry.humidity.0": 65.0,
        }

    def test_skips_missing_type(self):
        """Entries without 'type' key are skipped."""
        lpp_data = [
            {"channel": 0, "value": 23.5},
            {"type": "humidity", "channel": 0, "value": 65.0},
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.humidity.0": 65.0}

    def test_skips_empty_type(self):
        """Entries with empty type are skipped."""
        lpp_data = [
            {"type": "", "channel": 0, "value": 23.5},
            {"type": "   ", "channel": 0, "value": 20.0},
            {"type": "temperature", "channel": 0, "value": 25.0},
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.temperature.0": 25.0}

    def test_skips_non_string_type(self):
        """Entries with non-string type are skipped."""
        lpp_data = [
            {"type": 123, "channel": 0, "value": 23.5},
            {"type": "temperature", "channel": 0, "value": 25.0},
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.temperature.0": 25.0}

    def test_skips_string_value(self):
        """String values are skipped (not numeric)."""
        lpp_data = [
            {"type": "name", "channel": 0, "value": "Sensor1"},
            {"type": "temperature", "channel": 0, "value": 25.0},
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.temperature.0": 25.0}

    def test_invalid_channel_defaults_to_zero(self):
        """Non-integer channel defaults to 0."""
        lpp_data = [{"type": "temperature", "channel": "invalid", "value": 23.5}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.temperature.0": 23.5}

    def test_integer_value(self):
        """Integer values are converted to float."""
        lpp_data = [{"type": "count", "channel": 0, "value": 42}]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {"telemetry.count.0": 42.0}
        assert isinstance(result["telemetry.count.0"], float)

    def test_nested_non_numeric_subvalue_skipped(self):
        """Non-numeric subvalues in compound readings are skipped."""
        lpp_data = [
            {
                "type": "mixed",
                "channel": 0,
                "value": {"numeric": 42.0, "text": "hello", "valid": 3.14},
            }
        ]
        result = extract_telemetry_metrics(lpp_data)
        assert result == {
            "telemetry.mixed.0.numeric": 42.0,
            "telemetry.mixed.0.valid": 3.14,
        }
