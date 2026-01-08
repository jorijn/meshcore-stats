"""Tests for database validation and security functions."""

import pytest

from meshmon.db import (
    VALID_ROLES,
    _validate_role,
    get_available_metrics,
    get_distinct_timestamps,
    get_latest_metrics,
    get_metric_count,
    get_metrics_for_period,
    insert_metric,
    insert_metrics,
)


class TestValidateRole:
    """Tests for _validate_role function."""

    def test_accepts_companion(self):
        """Accepts 'companion' as valid role."""
        result = _validate_role("companion")
        assert result == "companion"

    def test_accepts_repeater(self):
        """Accepts 'repeater' as valid role."""
        result = _validate_role("repeater")
        assert result == "repeater"

    def test_returns_input_on_success(self):
        """Returns the validated role string."""
        for role in VALID_ROLES:
            result = _validate_role(role)
            assert result == role

    def test_rejects_invalid_role(self):
        """Rejects invalid role names."""
        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("invalid")

    def test_rejects_empty_string(self):
        """Rejects empty string as role."""
        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("")

    def test_rejects_none(self):
        """Rejects None as role."""
        with pytest.raises(ValueError):
            _validate_role(None)

    def test_case_sensitive(self):
        """Role validation is case-sensitive."""
        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("Companion")

        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("REPEATER")

    def test_rejects_whitespace_variants(self):
        """Rejects roles with leading/trailing whitespace."""
        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role(" companion")

        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role("repeater ")

        with pytest.raises(ValueError, match="Invalid role"):
            _validate_role(" companion ")


class TestSqlInjectionPrevention:
    """Tests to verify SQL injection is prevented via role validation."""

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "admin'; DROP TABLE metrics;--",
        "companion OR 1=1",
        "companion; DELETE FROM metrics",
        "companion' UNION SELECT * FROM db_meta --",
        "companion\"; DROP TABLE metrics; --",
        "1 OR 1=1",
        "companion/*comment*/",
    ])
    def test_insert_metric_rejects_injection(self, initialized_db, malicious_role):
        """insert_metric rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            insert_metric(1000, malicious_role, "test", 1.0, initialized_db)

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "companion OR 1=1",
    ])
    def test_insert_metrics_rejects_injection(self, initialized_db, malicious_role):
        """insert_metrics rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            insert_metrics(1000, malicious_role, {"test": 1.0}, initialized_db)

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "companion OR 1=1",
    ])
    def test_get_metrics_for_period_rejects_injection(self, initialized_db, malicious_role):
        """get_metrics_for_period rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_metrics_for_period(malicious_role, 0, 100, initialized_db)

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "companion OR 1=1",
    ])
    def test_get_latest_metrics_rejects_injection(self, initialized_db, malicious_role):
        """get_latest_metrics rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_latest_metrics(malicious_role, initialized_db)

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "companion OR 1=1",
    ])
    def test_get_metric_count_rejects_injection(self, initialized_db, malicious_role):
        """get_metric_count rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_metric_count(malicious_role, initialized_db)

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "companion OR 1=1",
    ])
    def test_get_distinct_timestamps_rejects_injection(self, initialized_db, malicious_role):
        """get_distinct_timestamps rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_distinct_timestamps(malicious_role, initialized_db)

    @pytest.mark.parametrize("malicious_role", [
        "'; DROP TABLE metrics; --",
        "companion OR 1=1",
    ])
    def test_get_available_metrics_rejects_injection(self, initialized_db, malicious_role):
        """get_available_metrics rejects SQL injection attempts."""
        with pytest.raises(ValueError, match="Invalid role"):
            get_available_metrics(malicious_role, initialized_db)


class TestValidRolesConstant:
    """Tests for VALID_ROLES constant."""

    def test_contains_companion(self):
        """VALID_ROLES includes 'companion'."""
        assert "companion" in VALID_ROLES

    def test_contains_repeater(self):
        """VALID_ROLES includes 'repeater'."""
        assert "repeater" in VALID_ROLES

    def test_is_tuple(self):
        """VALID_ROLES is immutable (tuple)."""
        assert isinstance(VALID_ROLES, tuple)

    def test_exactly_two_roles(self):
        """There are exactly two valid roles."""
        assert len(VALID_ROLES) == 2


class TestMetricNameValidation:
    """Tests for metric name handling (not validated, but should handle safely)."""

    def test_metric_name_with_special_chars(self, initialized_db):
        """Metric names with special chars are handled via parameterized queries."""
        # These should work because we use parameterized queries
        insert_metric(1000, "companion", "test.metric", 1.0, initialized_db)
        insert_metric(1001, "companion", "test-metric", 2.0, initialized_db)
        insert_metric(1002, "companion", "test_metric", 3.0, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)
        assert "test.metric" in metrics
        assert "test-metric" in metrics
        assert "test_metric" in metrics

    def test_metric_name_with_spaces(self, initialized_db):
        """Metric names with spaces are handled safely."""
        insert_metric(1000, "companion", "test metric", 1.0, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)
        assert "test metric" in metrics

    def test_metric_name_unicode(self, initialized_db):
        """Unicode metric names are handled safely."""
        insert_metric(1000, "companion", "température", 1.0, initialized_db)
        insert_metric(1001, "companion", "温度", 2.0, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)
        assert "température" in metrics
        assert "温度" in metrics

    def test_empty_metric_name(self, initialized_db):
        """Empty metric name is allowed (not validated)."""
        # Empty string is allowed as metric name
        insert_metric(1000, "companion", "", 1.0, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)
        assert "" in metrics

    def test_very_long_metric_name(self, initialized_db):
        """Very long metric names are handled."""
        long_name = "a" * 1000
        insert_metric(1000, "companion", long_name, 1.0, initialized_db)

        metrics = get_available_metrics("companion", initialized_db)
        assert long_name in metrics
