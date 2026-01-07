"""Tests for counter total computation with reboot handling."""

import pytest
from datetime import datetime, timedelta

from meshmon.reports import compute_counter_total


class TestComputeCounterTotal:
    """Tests for compute_counter_total function."""

    def test_calculates_total_from_deltas(self, sample_counter_values):
        """Calculates total as sum of positive deltas."""
        total, reboots = compute_counter_total(sample_counter_values)

        # Values: 100, 150, 200, 250, 300
        # Deltas: +50, +50, +50, +50 = 200
        assert total == 200
        assert reboots == 0

    def test_handles_single_value(self):
        """Single value cannot compute delta, returns None."""
        values = [(datetime(2024, 1, 15, 0, 0, 0), 100)]

        total, reboots = compute_counter_total(values)

        assert total is None
        assert reboots == 0

    def test_handles_empty_values(self):
        """Empty values returns None."""
        total, reboots = compute_counter_total([])

        assert total is None
        assert reboots == 0

    def test_detects_single_reboot(self, sample_counter_values_with_reboot):
        """Detects reboot and handles counter reset."""
        total, reboots = compute_counter_total(sample_counter_values_with_reboot)

        # Values: 100, 150, 200, 50 (reboot!), 100
        # Deltas: +50, +50, (reset to 50), +50
        # Total should be: 50 + 50 + 50 + 50 = 200
        # Or: (150-100) + (200-150) + 50 + (100-50) = 200
        assert total == 200
        assert reboots == 1

    def test_handles_multiple_reboots(self):
        """Handles multiple reboots in sequence."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        values = [
            (base_ts, 100),
            (base_ts + timedelta(minutes=15), 150),  # +50
            (base_ts + timedelta(minutes=30), 50),   # Reboot 1
            (base_ts + timedelta(minutes=45), 80),   # +30
            (base_ts + timedelta(hours=1), 30),      # Reboot 2
            (base_ts + timedelta(hours=1, minutes=15), 50),  # +20
        ]

        total, reboots = compute_counter_total(values)

        # Deltas: 50 + 50 + 30 + 30 + 20 = 180
        assert reboots == 2
        assert total == 50 + 50 + 30 + 30 + 20

    def test_zero_delta(self):
        """Handles zero delta (no change)."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        values = [
            (base_ts, 100),
            (base_ts + timedelta(minutes=15), 100),  # No change
            (base_ts + timedelta(minutes=30), 100),  # No change
        ]

        total, reboots = compute_counter_total(values)

        assert total == 0
        assert reboots == 0

    def test_large_values(self):
        """Handles large counter values."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        values = [
            (base_ts, 1000000000),
            (base_ts + timedelta(minutes=15), 1000001000),  # +1000
            (base_ts + timedelta(minutes=30), 1000002500),  # +1500
        ]

        total, reboots = compute_counter_total(values)

        assert total == 2500
        assert reboots == 0

    def test_sorted_values_required(self):
        """Function expects pre-sorted values by timestamp."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        # Properly sorted by timestamp
        values = [
            (base_ts, 100),
            (base_ts + timedelta(minutes=15), 150),
            (base_ts + timedelta(minutes=30), 200),
        ]

        total, reboots = compute_counter_total(values)

        # Deltas: 50, 50 = 100
        assert total == 100
        assert reboots == 0

    def test_two_values(self):
        """Two values gives single delta."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        values = [
            (base_ts, 100),
            (base_ts + timedelta(minutes=15), 175),
        ]

        total, reboots = compute_counter_total(values)

        assert total == 75
        assert reboots == 0

    def test_reboot_to_zero(self):
        """Handles reboot to exactly zero."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        values = [
            (base_ts, 100),
            (base_ts + timedelta(minutes=15), 150),  # +50
            (base_ts + timedelta(minutes=30), 0),    # Reboot to 0
            (base_ts + timedelta(minutes=45), 30),   # +30
        ]

        total, reboots = compute_counter_total(values)

        assert total == 50 + 0 + 30
        assert reboots == 1

    def test_float_values(self):
        """Handles float counter values."""
        base_ts = datetime(2024, 1, 15, 0, 0, 0)
        values = [
            (base_ts, 100.5),
            (base_ts + timedelta(minutes=15), 150.7),
            (base_ts + timedelta(minutes=30), 200.3),
        ]

        total, reboots = compute_counter_total(values)

        expected = (150.7 - 100.5) + (200.3 - 150.7)
        assert total == pytest.approx(expected)
        assert reboots == 0
