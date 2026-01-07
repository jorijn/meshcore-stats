"""Tests for database insert functions."""

import pytest
import time

from meshmon.db import (
    insert_metric,
    insert_metrics,
    get_connection,
)


class TestInsertMetric:
    """Tests for insert_metric function."""

    def test_inserts_single_metric(self, initialized_db):
        """Inserts a single metric successfully."""
        ts = int(time.time())

        result = insert_metric(ts, "companion", "battery_mv", 3850.0, initialized_db)

        assert result is True

        with get_connection(initialized_db, readonly=True) as conn:
            cursor = conn.execute(
                "SELECT value FROM metrics WHERE ts = ? AND role = ? AND metric = ?",
                (ts, "companion", "battery_mv")
            )
            row = cursor.fetchone()
            assert row is not None
            assert row["value"] == 3850.0

    def test_returns_false_on_duplicate(self, initialized_db):
        """Returns False for duplicate (ts, role, metric) tuple."""
        ts = int(time.time())

        # First insert succeeds
        assert insert_metric(ts, "companion", "test", 1.0, initialized_db) is True

        # Second insert with same key returns False
        assert insert_metric(ts, "companion", "test", 2.0, initialized_db) is False

    def test_different_roles_not_duplicate(self, initialized_db):
        """Same ts/metric with different roles are not duplicates."""
        ts = int(time.time())

        assert insert_metric(ts, "companion", "test", 1.0, initialized_db) is True
        assert insert_metric(ts, "repeater", "test", 2.0, initialized_db) is True

    def test_different_metrics_not_duplicate(self, initialized_db):
        """Same ts/role with different metrics are not duplicates."""
        ts = int(time.time())

        assert insert_metric(ts, "companion", "test1", 1.0, initialized_db) is True
        assert insert_metric(ts, "companion", "test2", 2.0, initialized_db) is True

    def test_invalid_role_raises(self, initialized_db):
        """Invalid role raises ValueError."""
        ts = int(time.time())

        with pytest.raises(ValueError, match="Invalid role"):
            insert_metric(ts, "invalid", "test", 1.0, initialized_db)

    def test_sql_injection_blocked(self, initialized_db):
        """SQL injection attempt raises ValueError."""
        ts = int(time.time())

        with pytest.raises(ValueError, match="Invalid role"):
            insert_metric(ts, "'; DROP TABLE metrics; --", "test", 1.0, initialized_db)


class TestInsertMetrics:
    """Tests for insert_metrics function (bulk insert)."""

    def test_inserts_multiple_metrics(self, initialized_db):
        """Inserts multiple metrics from dict."""
        ts = int(time.time())
        metrics = {
            "battery_mv": 3850.0,
            "contacts": 5,
            "uptime_secs": 86400,
        }

        count = insert_metrics(ts, "companion", metrics, initialized_db)

        assert count == 3

        with get_connection(initialized_db, readonly=True) as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM metrics WHERE ts = ?",
                (ts,)
            )
            assert cursor.fetchone()[0] == 3

    def test_returns_insert_count(self, initialized_db):
        """Returns correct count of inserted metrics."""
        ts = int(time.time())
        metrics = {"a": 1.0, "b": 2.0, "c": 3.0}

        count = insert_metrics(ts, "companion", metrics, initialized_db)

        assert count == 3

    def test_skips_non_numeric_values(self, initialized_db):
        """Non-numeric values are silently skipped."""
        ts = int(time.time())
        metrics = {
            "battery_mv": 3850.0,      # Numeric - inserted
            "name": "test",             # String - skipped
            "status": None,             # None - skipped
            "flags": [1, 2, 3],         # List - skipped
            "nested": {"a": 1},         # Dict - skipped
        }

        count = insert_metrics(ts, "companion", metrics, initialized_db)

        assert count == 1  # Only battery_mv

    def test_handles_int_and_float(self, initialized_db):
        """Both int and float values are inserted."""
        ts = int(time.time())
        metrics = {
            "int_value": 42,
            "float_value": 3.14,
        }

        count = insert_metrics(ts, "companion", metrics, initialized_db)

        assert count == 2

    def test_converts_int_to_float(self, initialized_db):
        """Integer values are stored as float."""
        ts = int(time.time())
        metrics = {"contacts": 5}

        insert_metrics(ts, "companion", metrics, initialized_db)

        with get_connection(initialized_db, readonly=True) as conn:
            cursor = conn.execute(
                "SELECT value FROM metrics WHERE metric = 'contacts'"
            )
            row = cursor.fetchone()
            assert row["value"] == 5.0
            assert isinstance(row["value"], float)

    def test_empty_dict_returns_zero(self, initialized_db):
        """Empty dict returns 0."""
        ts = int(time.time())

        count = insert_metrics(ts, "companion", {}, initialized_db)

        assert count == 0

    def test_skips_duplicates_silently(self, initialized_db):
        """Duplicate metrics are skipped without error."""
        ts = int(time.time())
        metrics = {"test": 1.0}

        # First insert
        count1 = insert_metrics(ts, "companion", metrics, initialized_db)
        assert count1 == 1

        # Second insert - same key
        count2 = insert_metrics(ts, "companion", metrics, initialized_db)
        assert count2 == 0  # Duplicate skipped

    def test_partial_duplicates(self, initialized_db):
        """Partial duplicates: some inserted, some skipped."""
        ts = int(time.time())

        # First insert
        insert_metrics(ts, "companion", {"existing": 1.0}, initialized_db)

        # Second insert with mix
        metrics = {
            "existing": 2.0,  # Duplicate - skipped
            "new": 3.0,       # New - inserted
        }
        count = insert_metrics(ts, "companion", metrics, initialized_db)

        assert count == 1  # Only "new" inserted

    def test_invalid_role_raises(self, initialized_db):
        """Invalid role raises ValueError."""
        ts = int(time.time())

        with pytest.raises(ValueError, match="Invalid role"):
            insert_metrics(ts, "invalid", {"test": 1.0}, initialized_db)

    def test_companion_metrics(self, initialized_db, sample_companion_metrics):
        """Inserts companion metrics dict."""
        ts = int(time.time())

        count = insert_metrics(ts, "companion", sample_companion_metrics, initialized_db)

        # Should insert all numeric fields
        assert count >= 4  # At least battery_mv, uptime_secs, contacts, recv, sent

    def test_repeater_metrics(self, initialized_db, sample_repeater_metrics):
        """Inserts repeater metrics dict."""
        ts = int(time.time())

        count = insert_metrics(ts, "repeater", sample_repeater_metrics, initialized_db)

        # Should insert all numeric fields
        assert count >= 10  # Many metrics
