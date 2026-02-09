"""Tests for metrics configuration and helper functions."""

import pytest

from meshmon.metrics import (
    COMPANION_CHART_METRICS,
    METRIC_CONFIG,
    REPEATER_CHART_METRICS,
    MetricConfig,
    convert_telemetry_value,
    discover_telemetry_chart_metrics,
    get_chart_metrics,
    get_graph_scale,
    get_metric_config,
    get_metric_label,
    get_metric_unit,
    get_telemetry_metric_decimals,
    get_telemetry_metric_label,
    get_telemetry_metric_unit,
    is_counter_metric,
    is_telemetry_metric,
    transform_value,
)


class TestMetricConfig:
    """Test MetricConfig dataclass."""

    def test_default_values(self):
        """Test MetricConfig default values."""
        config = MetricConfig(label="Test", unit="V")

        assert config.label == "Test"
        assert config.unit == "V"
        assert config.type == "gauge"
        assert config.scale == 1.0
        assert config.transform is None

    def test_counter_type(self):
        """Test counter metric configuration."""
        config = MetricConfig(label="Packets", unit="/min", type="counter", scale=60)

        assert config.type == "counter"
        assert config.scale == 60

    def test_with_transform(self):
        """Test metric with transform."""
        config = MetricConfig(label="Battery", unit="V", transform="mv_to_v")

        assert config.transform == "mv_to_v"

    def test_frozen_dataclass(self):
        """MetricConfig should be immutable (frozen)."""
        config = MetricConfig(label="Test", unit="V")

        with pytest.raises(AttributeError):
            config.label = "Changed"


class TestMetricConfigDict:
    """Test the METRIC_CONFIG dictionary."""

    def test_companion_metrics_exist(self):
        """All companion chart metrics should be in METRIC_CONFIG."""
        for metric in COMPANION_CHART_METRICS:
            assert metric in METRIC_CONFIG, f"Missing config for companion metric: {metric}"

    def test_repeater_metrics_exist(self):
        """All repeater chart metrics should be in METRIC_CONFIG."""
        for metric in REPEATER_CHART_METRICS:
            assert metric in METRIC_CONFIG, f"Missing config for repeater metric: {metric}"

    def test_battery_voltage_metrics_have_transform(self):
        """Battery voltage metrics should have mv_to_v transform."""
        voltage_metrics = ["battery_mv", "bat"]
        for metric in voltage_metrics:
            config = METRIC_CONFIG[metric]
            assert config.transform == "mv_to_v", (
                f"{metric} should have mv_to_v transform"
            )

    def test_counter_metrics_have_scale_60(self):
        """Counter metrics showing /min should have scale=60."""
        for name, config in METRIC_CONFIG.items():
            if config.type == "counter" and "/min" in config.unit:
                assert config.scale == 60, (
                    f"Counter metric {name} with /min unit should have scale=60"
                )


class TestGetChartMetrics:
    """Test get_chart_metrics function."""

    def test_companion_metrics(self):
        """get_chart_metrics('companion') returns companion metrics."""
        metrics = get_chart_metrics("companion")
        assert metrics == COMPANION_CHART_METRICS

    def test_repeater_metrics(self):
        """get_chart_metrics('repeater') returns repeater metrics."""
        metrics = get_chart_metrics("repeater")
        assert metrics == REPEATER_CHART_METRICS

    def test_invalid_role_raises(self):
        """get_chart_metrics with invalid role raises ValueError."""
        with pytest.raises(ValueError, match="Unknown role"):
            get_chart_metrics("invalid")

    def test_empty_role_raises(self):
        """get_chart_metrics with empty role raises ValueError."""
        with pytest.raises(ValueError, match="Unknown role"):
            get_chart_metrics("")

    def test_repeater_includes_telemetry_when_enabled(self):
        """Repeater chart metrics include discovered telemetry when enabled."""
        available_metrics = [
            "bat",
            "telemetry.temperature.1",
            "telemetry.humidity.1",
            "telemetry.voltage.1",
        ]

        metrics = get_chart_metrics(
            "repeater",
            available_metrics=available_metrics,
            telemetry_enabled=True,
        )

        assert "telemetry.temperature.1" in metrics
        assert "telemetry.humidity.1" in metrics
        assert "telemetry.voltage.1" not in metrics

    def test_repeater_does_not_include_telemetry_when_disabled(self):
        """Repeater chart metrics exclude telemetry when telemetry is disabled."""
        available_metrics = ["telemetry.temperature.1", "telemetry.humidity.1"]

        metrics = get_chart_metrics(
            "repeater",
            available_metrics=available_metrics,
            telemetry_enabled=False,
        )

        assert not any(metric.startswith("telemetry.") for metric in metrics)

    def test_companion_never_includes_telemetry(self):
        """Companion chart metrics stay unchanged, even with telemetry enabled."""
        metrics = get_chart_metrics(
            "companion",
            available_metrics=["telemetry.temperature.1"],
            telemetry_enabled=True,
        )
        assert metrics == COMPANION_CHART_METRICS


class TestTelemetryMetricHelpers:
    """Tests for telemetry metric parsing, discovery, and display helpers."""

    def test_is_telemetry_metric(self):
        """Telemetry metrics are detected by key pattern."""
        assert is_telemetry_metric("telemetry.temperature.1") is True
        assert is_telemetry_metric("telemetry.gps.0.latitude") is True
        assert is_telemetry_metric("bat") is False

    def test_discovery_excludes_voltage(self):
        """telemetry.voltage.* metrics are excluded from chart discovery."""
        discovered = discover_telemetry_chart_metrics(
            [
                "telemetry.temperature.1",
                "telemetry.voltage.1",
                "telemetry.humidity.1",
                "telemetry.gps.0.latitude",
            ]
        )
        assert "telemetry.temperature.1" in discovered
        assert "telemetry.humidity.1" in discovered
        assert "telemetry.voltage.1" not in discovered
        assert "telemetry.gps.0.latitude" not in discovered

    def test_discovery_is_deterministic(self):
        """Discovery order is deterministic and sorted by display intent."""
        discovered = discover_telemetry_chart_metrics(
            [
                "telemetry.temperature.2",
                "telemetry.humidity.1",
                "telemetry.temperature.1",
            ]
        )
        assert discovered == [
            "telemetry.humidity.1",
            "telemetry.temperature.1",
            "telemetry.temperature.2",
        ]

    def test_telemetry_label_is_human_readable(self):
        """Telemetry labels are transformed into readable UI labels."""
        label = get_telemetry_metric_label("telemetry.temperature.1")
        assert "Temperature" in label
        assert "CH1" in label

    def test_telemetry_unit_mapping(self):
        """Telemetry units adapt to selected unit system."""
        assert get_telemetry_metric_unit("telemetry.temperature.1", "metric") == "°C"
        assert get_telemetry_metric_unit("telemetry.temperature.1", "imperial") == "°F"
        assert get_telemetry_metric_unit("telemetry.barometer.1", "metric") == "hPa"
        assert get_telemetry_metric_unit("telemetry.barometer.1", "imperial") == "inHg"
        assert get_telemetry_metric_unit("telemetry.altitude.1", "metric") == "m"
        assert get_telemetry_metric_unit("telemetry.altitude.1", "imperial") == "ft"
        assert get_telemetry_metric_unit("telemetry.humidity.1", "imperial") == "%"

    def test_telemetry_decimals_mapping(self):
        """Telemetry decimals adapt to metric type and unit system."""
        assert get_telemetry_metric_decimals("telemetry.temperature.1", "metric") == 1
        assert get_telemetry_metric_decimals("telemetry.barometer.1", "imperial") == 2
        assert get_telemetry_metric_decimals("telemetry.unknown.1", "imperial") == 2

    def test_convert_temperature_c_to_f(self):
        """Temperature converts from Celsius to Fahrenheit for imperial display."""
        assert convert_telemetry_value("telemetry.temperature.1", 0.0, "imperial") == pytest.approx(32.0)
        assert convert_telemetry_value("telemetry.temperature.1", 20.0, "imperial") == pytest.approx(68.0)

    def test_convert_barometer_hpa_to_inhg(self):
        """Barometric pressure converts from hPa to inHg for imperial display."""
        assert convert_telemetry_value("telemetry.barometer.1", 1013.25, "imperial") == pytest.approx(29.92126, rel=1e-5)

    def test_convert_altitude_m_to_ft(self):
        """Altitude converts from meters to feet for imperial display."""
        assert convert_telemetry_value("telemetry.altitude.1", 100.0, "imperial") == pytest.approx(328.08399, rel=1e-5)

    def test_convert_humidity_unchanged(self):
        """Humidity remains unchanged across unit systems."""
        assert convert_telemetry_value("telemetry.humidity.1", 85.5, "metric") == pytest.approx(85.5)
        assert convert_telemetry_value("telemetry.humidity.1", 85.5, "imperial") == pytest.approx(85.5)

    def test_convert_unknown_metric_unchanged(self):
        """Unknown telemetry metric types remain unchanged."""
        assert convert_telemetry_value("telemetry.custom.1", 12.34, "imperial") == pytest.approx(12.34)


class TestGetMetricConfig:
    """Test get_metric_config function."""

    def test_existing_metric(self):
        """get_metric_config returns config for known metrics."""
        config = get_metric_config("bat")
        assert config is not None
        assert config.label == "Battery Voltage"
        assert config.unit == "V"

    def test_unknown_metric(self):
        """get_metric_config returns None for unknown metrics."""
        config = get_metric_config("nonexistent_metric")
        assert config is None

    def test_empty_string(self):
        """get_metric_config returns None for empty string."""
        config = get_metric_config("")
        assert config is None


class TestIsCounterMetric:
    """Test is_counter_metric function."""

    @pytest.mark.parametrize(
        "metric",
        ["recv", "sent", "nb_recv", "nb_sent", "airtime", "rx_airtime"],
    )
    def test_counter_metrics(self, metric: str):
        """Known counter metrics return True."""
        assert is_counter_metric(metric) is True

    @pytest.mark.parametrize(
        "metric",
        ["bat", "battery_mv", "bat_pct", "last_rssi", "last_snr", "uptime"],
    )
    def test_gauge_metrics(self, metric: str):
        """Known gauge metrics return False."""
        assert is_counter_metric(metric) is False

    def test_unknown_metric(self):
        """Unknown metrics return False (not True)."""
        assert is_counter_metric("unknown_metric") is False


class TestGetGraphScale:
    """Test get_graph_scale function."""

    def test_counter_with_scale(self):
        """Counter metrics should return their configured scale."""
        # nb_recv has scale=60 for per-minute display
        scale = get_graph_scale("nb_recv")
        assert scale == 60

    def test_gauge_default_scale(self):
        """Gauge metrics with default scale return 1.0."""
        # last_rssi has no special scale
        scale = get_graph_scale("last_rssi")
        assert scale == 1.0

    def test_uptime_scale(self):
        """Uptime metrics have fractional scale for days display."""
        # uptime has scale = 1/86400 to convert seconds to days
        scale = get_graph_scale("uptime")
        assert scale == pytest.approx(1 / 86400)

    def test_unknown_metric(self):
        """Unknown metrics return default scale of 1.0."""
        scale = get_graph_scale("unknown_metric")
        assert scale == 1.0


class TestGetMetricLabel:
    """Test get_metric_label function."""

    def test_existing_metric(self):
        """Known metrics return their configured label."""
        label = get_metric_label("bat")
        assert label == "Battery Voltage"

    def test_unknown_metric_returns_name(self):
        """Unknown metrics return the metric name as label."""
        label = get_metric_label("unknown_metric")
        assert label == "unknown_metric"

    def test_telemetry_metric_returns_human_label(self):
        """Telemetry metrics return a human-readable label."""
        label = get_metric_label("telemetry.temperature.1")
        assert "Temperature" in label
        assert "CH1" in label


class TestGetMetricUnit:
    """Test get_metric_unit function."""

    def test_voltage_unit(self):
        """Voltage metrics return 'V' unit."""
        unit = get_metric_unit("bat")
        assert unit == "V"

    def test_counter_unit(self):
        """Counter metrics return their configured unit."""
        unit = get_metric_unit("nb_recv")
        assert unit == "/min"

    def test_unitless_metric(self):
        """Unitless metrics return empty string."""
        unit = get_metric_unit("contacts")
        assert unit == ""

    def test_unknown_metric(self):
        """Unknown metrics return empty string."""
        unit = get_metric_unit("unknown_metric")
        assert unit == ""

    def test_telemetry_metric_metric_units(self):
        """Telemetry metrics use metric units by default."""
        unit = get_metric_unit("telemetry.temperature.1")
        assert unit == "°C"

    def test_telemetry_metric_imperial_units(self):
        """Telemetry metrics switch units when unit system is imperial."""
        unit = get_metric_unit("telemetry.barometer.1", unit_system="imperial")
        assert unit == "inHg"


class TestTransformValue:
    """Test transform_value function."""

    def test_mv_to_v_transform(self):
        """Metrics with mv_to_v transform convert millivolts to volts."""
        # bat metric has mv_to_v transform
        result = transform_value("bat", 3850.0)
        assert result == pytest.approx(3.85)

    def test_battery_mv_transform(self):
        """battery_mv metric also has mv_to_v transform."""
        result = transform_value("battery_mv", 4200.0)
        assert result == pytest.approx(4.2)

    def test_no_transform(self):
        """Metrics without transform return value unchanged."""
        result = transform_value("last_rssi", -85.0)
        assert result == -85.0

    def test_unknown_metric_no_transform(self):
        """Unknown metrics return value unchanged."""
        result = transform_value("unknown_metric", 12345.0)
        assert result == 12345.0

    def test_transform_with_zero(self):
        """Transform handles zero values correctly."""
        result = transform_value("bat", 0.0)
        assert result == 0.0

    def test_transform_with_negative(self):
        """Transform handles negative values (edge case)."""
        result = transform_value("bat", -100.0)
        assert result == pytest.approx(-0.1)
