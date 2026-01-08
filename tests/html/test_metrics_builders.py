"""Tests for metrics builder functions."""


from meshmon.html import (
    _build_traffic_table_rows,
    build_companion_metrics,
    build_node_details,
    build_radio_config,
    build_repeater_metrics,
)


class TestBuildRepeaterMetrics:
    """Tests for build_repeater_metrics function."""

    def test_returns_dict(self, sample_repeater_metrics):
        """Returns a dictionary."""
        # build_repeater_metrics takes a row dict (firmware field names)
        result = build_repeater_metrics(sample_repeater_metrics)
        assert isinstance(result, dict)

    def test_returns_dict_structure(self, sample_repeater_metrics):
        """Returns dict with expected keys."""
        result = build_repeater_metrics(sample_repeater_metrics)
        # Should have critical_metrics, secondary_metrics, traffic_metrics
        assert "critical_metrics" in result
        assert "secondary_metrics" in result
        assert "traffic_metrics" in result

    def test_critical_metrics_is_list(self, sample_repeater_metrics):
        """Critical metrics is a list."""
        result = build_repeater_metrics(sample_repeater_metrics)
        assert isinstance(result["critical_metrics"], list)

    def test_handles_none(self):
        """Handles None row."""
        result = build_repeater_metrics(None)
        assert isinstance(result, dict)
        assert result["critical_metrics"] == []

    def test_handles_empty_dict(self):
        """Handles empty dict."""
        result = build_repeater_metrics({})
        assert isinstance(result, dict)


class TestBuildCompanionMetrics:
    """Tests for build_companion_metrics function."""

    def test_returns_dict(self, sample_companion_metrics):
        """Returns a dictionary."""
        result = build_companion_metrics(sample_companion_metrics)
        assert isinstance(result, dict)

    def test_returns_dict_structure(self, sample_companion_metrics):
        """Returns dict with expected keys."""
        result = build_companion_metrics(sample_companion_metrics)
        assert "critical_metrics" in result
        assert "secondary_metrics" in result
        assert "traffic_metrics" in result

    def test_handles_none(self):
        """Handles None row."""
        result = build_companion_metrics(None)
        assert isinstance(result, dict)
        assert result["critical_metrics"] == []

    def test_handles_empty_dict(self):
        """Handles empty dict."""
        result = build_companion_metrics({})
        assert isinstance(result, dict)


class TestBuildNodeDetails:
    """Tests for build_node_details function."""

    def test_returns_list(self, configured_env):
        """Returns a list of detail items."""
        result = build_node_details("repeater")
        assert isinstance(result, list)

    def test_items_have_label_value(self, configured_env):
        """Each item has label and value."""
        result = build_node_details("repeater")
        for item in result:
            assert isinstance(item, dict)
            assert "label" in item
            assert "value" in item

    def test_includes_hardware_info(self, configured_env, monkeypatch):
        """Includes hardware model info."""
        monkeypatch.setenv("REPEATER_HARDWARE", "Test LoRa Device")
        import meshmon.env
        meshmon.env._config = None

        result = build_node_details("repeater")

        # Should have hardware in one of the items
        labels = [item.get("label", "").lower() for item in result]
        assert "hardware" in labels

    def test_different_roles(self, configured_env):
        """Different roles return details."""
        repeater_details = build_node_details("repeater")
        companion_details = build_node_details("companion")

        assert isinstance(repeater_details, list)
        assert isinstance(companion_details, list)


class TestBuildRadioConfig:
    """Tests for build_radio_config function."""

    def test_returns_list(self, configured_env):
        """Returns a list of config items."""
        result = build_radio_config()
        assert isinstance(result, list)

    def test_items_have_label_value(self, configured_env):
        """Each item has label and value."""
        result = build_radio_config()
        for item in result:
            assert isinstance(item, dict)
            assert "label" in item
            assert "value" in item

    def test_includes_frequency_when_set(self, configured_env, monkeypatch):
        """Includes frequency when configured."""
        monkeypatch.setenv("RADIO_FREQUENCY", "869.618 MHz")
        import meshmon.env
        meshmon.env._config = None

        result = build_radio_config()

        values = [item.get("value", "") for item in result]
        assert any("869" in str(v) for v in values)

    def test_handles_missing_config(self, configured_env):
        """Returns list even with default config."""
        result = build_radio_config()
        assert isinstance(result, list)


class TestBuildTrafficTableRows:
    """Tests for _build_traffic_table_rows function."""

    def test_returns_list(self):
        """Returns a list of rows."""
        # Input is list of traffic metric dicts
        traffic_metrics = [
            {"label": "RX", "value": "100", "raw_value": 100, "unit": "/min"},
            {"label": "TX", "value": "50", "raw_value": 50, "unit": "/min"},
        ]
        rows = _build_traffic_table_rows(traffic_metrics)
        assert isinstance(rows, list)

    def test_rows_have_structure(self):
        """Each row has expected structure."""
        traffic_metrics = [
            {"label": "RX", "value": "100", "raw_value": 100, "unit": "/min"},
            {"label": "TX", "value": "50", "raw_value": 50, "unit": "/min"},
        ]
        rows = _build_traffic_table_rows(traffic_metrics)

        for row in rows:
            assert isinstance(row, dict)
            assert "label" in row
            assert "rx" in row
            assert "tx" in row

    def test_handles_empty_list(self):
        """Handles empty traffic metrics list."""
        rows = _build_traffic_table_rows([])
        assert isinstance(rows, list)
        assert len(rows) == 0

    def test_combines_rx_tx_pairs(self):
        """Combines RX and TX into single row."""
        traffic_metrics = [
            {"label": "Flood RX", "value": "100", "raw_value": 100, "unit": "/min"},
            {"label": "Flood TX", "value": "50", "raw_value": 50, "unit": "/min"},
        ]
        rows = _build_traffic_table_rows(traffic_metrics)

        # Should have one "Flood" row with both rx and tx
        assert len(rows) == 1
        assert rows[0]["label"] == "Flood"
        assert rows[0]["rx"] == "100"
        assert rows[0]["tx"] == "50"
