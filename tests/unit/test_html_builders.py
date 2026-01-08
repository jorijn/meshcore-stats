"""Tests for HTML builder functions in html.py."""


from meshmon.html import (
    COMPANION_CHART_GROUPS,
    PERIOD_CONFIG,
    REPEATER_CHART_GROUPS,
    _build_traffic_table_rows,
    build_companion_metrics,
    build_node_details,
    build_radio_config,
    build_repeater_metrics,
    get_jinja_env,
)


class TestBuildTrafficTableRows:
    """Test _build_traffic_table_rows function."""

    def test_empty_list(self):
        """Empty list returns empty list."""
        result = _build_traffic_table_rows([])
        assert result == []

    def test_rx_tx_packets(self):
        """RX and TX become Packets row."""
        traffic = [
            {"label": "RX", "value": "1.2k", "raw_value": 1200, "unit": "packets"},
            {"label": "TX", "value": "800", "raw_value": 800, "unit": "packets"},
        ]
        result = _build_traffic_table_rows(traffic)

        assert len(result) == 1
        assert result[0]["label"] == "Packets"
        assert result[0]["rx"] == "1.2k"
        assert result[0]["rx_raw"] == 1200
        assert result[0]["tx"] == "800"
        assert result[0]["tx_raw"] == 800
        assert result[0]["unit"] == "packets"

    def test_flood_rx_tx(self):
        """Flood RX/TX become Flood row."""
        traffic = [
            {"label": "Flood RX", "value": "500", "raw_value": 500, "unit": "packets"},
            {"label": "Flood TX", "value": "300", "raw_value": 300, "unit": "packets"},
        ]
        result = _build_traffic_table_rows(traffic)

        assert len(result) == 1
        assert result[0]["label"] == "Flood"
        assert result[0]["rx"] == "500"
        assert result[0]["tx"] == "300"
        assert result[0]["rx_raw"] == 500
        assert result[0]["tx_raw"] == 300
        assert result[0]["unit"] == "packets"

    def test_direct_rx_tx(self):
        """Direct RX/TX become Direct row."""
        traffic = [
            {"label": "Direct RX", "value": "200", "raw_value": 200, "unit": "packets"},
            {"label": "Direct TX", "value": "100", "raw_value": 100, "unit": "packets"},
        ]
        result = _build_traffic_table_rows(traffic)

        assert len(result) == 1
        assert result[0]["label"] == "Direct"
        assert result[0]["rx"] == "200"
        assert result[0]["tx"] == "100"
        assert result[0]["rx_raw"] == 200
        assert result[0]["tx_raw"] == 100
        assert result[0]["unit"] == "packets"

    def test_airtime_rx_tx(self):
        """Airtime TX/RX become Airtime row."""
        traffic = [
            {"label": "Airtime TX", "value": "1h 30m", "raw_value": 5400, "unit": "seconds"},
            {"label": "Airtime RX", "value": "3h 0m", "raw_value": 10800, "unit": "seconds"},
        ]
        result = _build_traffic_table_rows(traffic)

        assert len(result) == 1
        assert result[0]["label"] == "Airtime"
        assert result[0]["tx"] == "1h 30m"
        assert result[0]["rx"] == "3h 0m"
        assert result[0]["rx_raw"] == 10800
        assert result[0]["tx_raw"] == 5400
        assert result[0]["unit"] == "seconds"

    def test_output_order(self):
        """Output follows order: Packets, Flood, Direct, Airtime."""
        traffic = [
            {"label": "Airtime TX", "value": "1h", "raw_value": 3600, "unit": "seconds"},
            {"label": "Direct RX", "value": "100", "raw_value": 100, "unit": "packets"},
            {"label": "Flood RX", "value": "200", "raw_value": 200, "unit": "packets"},
            {"label": "RX", "value": "500", "raw_value": 500, "unit": "packets"},
        ]
        result = _build_traffic_table_rows(traffic)

        labels = [r["label"] for r in result]
        assert labels == ["Packets", "Flood", "Direct", "Airtime"]

    def test_missing_pair(self):
        """Missing pair leaves None for that direction."""
        traffic = [
            {"label": "RX", "value": "500", "raw_value": 500, "unit": "packets"},
        ]
        result = _build_traffic_table_rows(traffic)

        assert result[0]["rx"] == "500"
        assert result[0]["tx"] is None
        assert result[0]["rx_raw"] == 500
        assert result[0]["tx_raw"] is None

    def test_unrecognized_label_skipped(self):
        """Unrecognized labels are skipped."""
        traffic = [
            {"label": "Unknown", "value": "100", "raw_value": 100, "unit": "packets"},
            {"label": "RX", "value": "500", "raw_value": 500, "unit": "packets"},
        ]
        result = _build_traffic_table_rows(traffic)

        assert len(result) == 1
        assert result[0]["label"] == "Packets"


class TestBuildNodeDetails:
    """Test build_node_details function."""

    def test_repeater_details(self, configured_env, monkeypatch):
        """Repeater node details include location info."""
        monkeypatch.setenv("REPORT_LOCATION_SHORT", "Test Location")
        monkeypatch.setenv("REPORT_LAT", "51.5074")
        monkeypatch.setenv("REPORT_LON", "-0.1278")
        monkeypatch.setenv("REPORT_ELEV", "11")
        monkeypatch.setenv("REPORT_ELEV_UNIT", "m")
        monkeypatch.setenv("REPEATER_HARDWARE", "RAK 4631")

        # Reset config to pick up new values
        import meshmon.env
        meshmon.env._config = None

        result = build_node_details("repeater")

        labels = [d["label"] for d in result]
        assert "Location" in labels
        assert "Coordinates" in labels
        assert "Elevation" in labels
        assert "Hardware" in labels

        # Check specific values
        location = next(d for d in result if d["label"] == "Location")
        assert location["value"] == "Test Location"
        coords = next(d for d in result if d["label"] == "Coordinates")
        assert coords["value"] == "51.5074°N, 0.1278°W"
        elevation = next(d for d in result if d["label"] == "Elevation")
        assert elevation["value"] == "11 m"

        hardware = next(d for d in result if d["label"] == "Hardware")
        assert hardware["value"] == "RAK 4631"

    def test_companion_details(self, configured_env, monkeypatch):
        """Companion node details are simpler."""
        monkeypatch.setenv("COMPANION_HARDWARE", "T-Beam Supreme")

        # Reset config
        import meshmon.env
        meshmon.env._config = None

        result = build_node_details("companion")

        labels = [d["label"] for d in result]
        assert "Hardware" in labels
        assert "Connection" in labels
        assert next(d for d in result if d["label"] == "Connection")["value"] == "USB Serial"
        assert next(d for d in result if d["label"] == "Hardware")["value"] == "T-Beam Supreme"

        # No location info for companion
        assert "Location" not in labels
        assert "Coordinates" not in labels

    def test_coordinate_directions(self, configured_env, monkeypatch):
        """Coordinate directions are correct for positive/negative."""
        monkeypatch.setenv("REPORT_LAT", "-33.8688")  # Sydney
        monkeypatch.setenv("REPORT_LON", "151.2093")

        import meshmon.env
        meshmon.env._config = None

        result = build_node_details("repeater")
        coords = next(d for d in result if d["label"] == "Coordinates")

        assert coords["value"] == "33.8688°S, 151.2093°E"


class TestBuildRadioConfig:
    """Test build_radio_config function."""

    def test_returns_radio_settings(self, configured_env, monkeypatch):
        """Returns radio configuration from env."""
        monkeypatch.setenv("RADIO_FREQUENCY", "915.0 MHz")
        monkeypatch.setenv("RADIO_BANDWIDTH", "125 kHz")
        monkeypatch.setenv("RADIO_SPREAD_FACTOR", "SF12")
        monkeypatch.setenv("RADIO_CODING_RATE", "CR5")

        import meshmon.env
        meshmon.env._config = None

        result = build_radio_config()

        labels = [d["label"] for d in result]
        assert "Frequency" in labels
        assert "Bandwidth" in labels
        assert "Spread Factor" in labels
        assert "Coding Rate" in labels

        freq = next(d for d in result if d["label"] == "Frequency")
        assert freq["value"] == "915.0 MHz"
        assert next(d for d in result if d["label"] == "Bandwidth")["value"] == "125 kHz"
        assert next(d for d in result if d["label"] == "Spread Factor")["value"] == "SF12"
        assert next(d for d in result if d["label"] == "Coding Rate")["value"] == "CR5"


class TestBuildRepeaterMetrics:
    """Test build_repeater_metrics function."""

    def test_none_row_returns_empty(self):
        """None row returns empty metric lists."""
        result = build_repeater_metrics(None)
        assert result["critical_metrics"] == []
        assert result["secondary_metrics"] == []
        assert result["traffic_metrics"] == []

    def test_empty_row_returns_empty(self):
        """Empty row returns empty metric lists."""
        result = build_repeater_metrics({})
        assert result["critical_metrics"] == []
        assert result["secondary_metrics"] == []
        assert result["traffic_metrics"] == []

    def test_full_row_extracts_metrics(self):
        """Full row extracts all metric categories."""
        row = {
            "bat": 3850.0,
            "bat_pct": 55.0,
            "last_rssi": -85.0,
            "last_snr": 7.5,
            "uptime": 86400,
            "noise_floor": -115.0,
            "tx_queue_len": 0,
            "nb_recv": 1234,
            "nb_sent": 567,
            "recv_flood": 500,
            "sent_flood": 200,
            "recv_direct": 100,
            "sent_direct": 50,
            "airtime": 3600,
            "rx_airtime": 7200,
        }
        result = build_repeater_metrics(row)

        # Critical metrics
        assert [m["label"] for m in result["critical_metrics"]] == [
            "Battery",
            "Charge",
            "RSSI",
            "SNR",
        ]
        battery = result["critical_metrics"][0]
        assert battery == {
            "value": "3.85",
            "unit": "V",
            "label": "Battery",
            "bar_pct": 55,
        }
        assert result["critical_metrics"][1] == {
            "value": "55",
            "unit": "%",
            "label": "Charge",
        }
        assert result["critical_metrics"][2] == {
            "value": "-85",
            "unit": "dBm",
            "label": "RSSI",
        }
        assert result["critical_metrics"][3] == {
            "value": "7.50",
            "unit": "dB",
            "label": "SNR",
        }

        # Secondary metrics
        assert result["secondary_metrics"] == [
            {"label": "Uptime", "value": "1d 0h"},
            {"label": "Noise Floor", "value": "-115 dBm"},
            {"label": "TX Queue", "value": "0"},
        ]

        # Traffic metrics
        assert [
            (metric["label"], metric["value"], metric["raw_value"], metric["unit"])
            for metric in result["traffic_metrics"]
        ] == [
            ("RX", "1,234", 1234, "packets"),
            ("TX", "567", 567, "packets"),
            ("Flood RX", "500", 500, "packets"),
            ("Flood TX", "200", 200, "packets"),
            ("Direct RX", "100", 100, "packets"),
            ("Direct TX", "50", 50, "packets"),
            ("Airtime TX", "1h 0m", 3600, "seconds"),
            ("Airtime RX", "2h 0m", 7200, "seconds"),
        ]

    def test_battery_converts_mv_to_v(self):
        """Battery value is converted from mV to V."""
        row = {"bat": 4200.0, "bat_pct": 100.0}
        result = build_repeater_metrics(row)

        battery = next(m for m in result["critical_metrics"] if m["label"] == "Battery")
        assert battery["value"] == "4.20"

    def test_bar_pct_for_battery(self):
        """Battery has bar_pct for progress display."""
        row = {"bat": 3850.0, "bat_pct": 55.0}
        result = build_repeater_metrics(row)

        battery = next(m for m in result["critical_metrics"] if m["label"] == "Battery")
        assert battery["bar_pct"] == 55


class TestBuildCompanionMetrics:
    """Test build_companion_metrics function."""

    def test_none_row_returns_empty(self):
        """None row returns empty metric lists."""
        result = build_companion_metrics(None)
        assert result["critical_metrics"] == []
        assert result["secondary_metrics"] == []
        assert result["traffic_metrics"] == []

    def test_full_row_extracts_metrics(self):
        """Full row extracts all metric categories."""
        row = {
            "battery_mv": 3850.0,
            "bat_pct": 55.0,
            "contacts": 5,
            "uptime_secs": 86400,
            "recv": 1234,
            "sent": 567,
        }
        result = build_companion_metrics(row)

        # Critical metrics
        assert result["critical_metrics"] == [
            {
                "value": "3.85",
                "unit": "V",
                "label": "Battery",
                "bar_pct": 55,
            },
            {"value": "55", "unit": "%", "label": "Charge"},
            {"value": "5", "unit": None, "label": "Contacts"},
            {"value": "1d 0h", "unit": None, "label": "Uptime"},
        ]

        # Secondary metrics (empty for companion)
        assert result["secondary_metrics"] == []

        # Traffic metrics
        assert result["traffic_metrics"] == [
            {"label": "RX", "value": "1,234", "raw_value": 1234, "unit": "packets"},
            {"label": "TX", "value": "567", "raw_value": 567, "unit": "packets"},
        ]

    def test_battery_converts_mv_to_v(self):
        """Battery value is converted from mV to V."""
        row = {"battery_mv": 4000.0, "bat_pct": 80.0}
        result = build_companion_metrics(row)

        battery = next(m for m in result["critical_metrics"] if m["label"] == "Battery")
        assert battery["value"] == "4.00"

    def test_contacts_displays_correctly(self):
        """Contacts are displayed as integer."""
        row = {"contacts": 7}
        result = build_companion_metrics(row)

        contacts = next(m for m in result["critical_metrics"] if m["label"] == "Contacts")
        assert contacts["value"] == "7"
        assert contacts["unit"] is None


class TestGetJinjaEnv:
    """Test get_jinja_env function."""

    def test_returns_environment(self):
        """Returns a Jinja2 Environment."""
        from jinja2 import Environment

        # Reset singleton for clean test
        import meshmon.html
        meshmon.html._jinja_env = None

        env = get_jinja_env()
        assert isinstance(env, Environment)

    def test_returns_singleton(self):
        """Returns same instance on subsequent calls."""
        import meshmon.html
        meshmon.html._jinja_env = None

        env1 = get_jinja_env()
        env2 = get_jinja_env()
        assert env1 is env2

    def test_registers_custom_filters(self):
        """Custom format filters are registered."""
        import meshmon.html
        meshmon.html._jinja_env = None

        env = get_jinja_env()

        assert "format_time" in env.filters
        assert "format_value" in env.filters
        assert "format_number" in env.filters
        assert "format_duration" in env.filters
        assert "format_uptime" in env.filters
        assert "format_compact_number" in env.filters
        assert "format_duration_compact" in env.filters


class TestChartGroupConstants:
    """Test chart group configuration constants."""

    def test_repeater_chart_groups_defined(self):
        """Repeater chart groups are defined."""
        assert len(REPEATER_CHART_GROUPS) > 0
        for group in REPEATER_CHART_GROUPS:
            assert "title" in group
            assert "metrics" in group
            assert len(group["metrics"]) > 0

    def test_companion_chart_groups_defined(self):
        """Companion chart groups are defined."""
        assert len(COMPANION_CHART_GROUPS) > 0
        for group in COMPANION_CHART_GROUPS:
            assert "title" in group
            assert "metrics" in group
            assert len(group["metrics"]) > 0

    def test_period_config_defined(self):
        """Period config has all expected periods."""
        assert "day" in PERIOD_CONFIG
        assert "week" in PERIOD_CONFIG
        assert "month" in PERIOD_CONFIG
        assert "year" in PERIOD_CONFIG

        for _period, (title, subtitle) in PERIOD_CONFIG.items():
            assert isinstance(title, str)
            assert isinstance(subtitle, str)
