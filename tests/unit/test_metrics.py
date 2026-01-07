"""Tests for metrics configuration and helper functions."""

import pytest
from meshmon.metrics import (
    MetricConfig,
    METRIC_CONFIG,
    COMPANION_CHART_METRICS,
    REPEATER_CHART_METRICS,
    get_chart_metrics,
    get_metric_config,
    is_counter_metric,
    get_graph_scale,
    get_metric_label,
    get_metric_unit,
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
