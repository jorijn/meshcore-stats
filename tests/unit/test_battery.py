"""Tests for battery voltage to percentage conversion."""

import pytest
from meshmon.battery import voltage_to_percentage, VOLTAGE_TABLE


class TestVoltageToPercentage:
    """Test battery voltage to percentage conversion."""

    # ==========================================================================
    # Boundary conditions
    # ==========================================================================

    @pytest.mark.parametrize(
        "voltage,expected",
        [
            (4.20, 100.0),  # Exact maximum
            (4.21, 100.0),  # Above maximum (clamped)
            (4.50, 100.0),  # Well above maximum
            (5.00, 100.0),  # Way above maximum
            (3.00, 0.0),  # Exact minimum
            (2.99, 0.0),  # Below minimum (clamped)
            (2.50, 0.0),  # Well below minimum
            (0.00, 0.0),  # Zero voltage
            (-1.0, 0.0),  # Negative (impossible but should handle)
        ],
    )
    def test_boundary_values(self, voltage: float, expected: float):
        """Test values at and beyond the voltage table boundaries."""
        assert voltage_to_percentage(voltage) == expected

    # ==========================================================================
    # Table lookup exact values
    # ==========================================================================

    @pytest.mark.parametrize("voltage,expected", VOLTAGE_TABLE)
    def test_exact_table_values(self, voltage: float, expected: float):
        """Test that exact table values return correct percentages."""
        result = voltage_to_percentage(voltage)
        assert result == expected, f"Expected {expected}% at {voltage}V, got {result}%"

    # ==========================================================================
    # Interpolation tests
    # ==========================================================================

    @pytest.mark.parametrize(
        "voltage,expected_range",
        [
            (4.13, (90.0, 100.0)),  # Between 4.20 and 4.06
            (4.02, (80.0, 90.0)),  # Between 4.06 and 3.98
            (3.95, (70.0, 80.0)),  # Between 3.98 and 3.92
            (3.50, (0.0, 10.0)),  # Between 3.45 and 3.68
            (3.72, (10.0, 20.0)),  # Between 3.68 and 3.74
        ],
    )
    def test_interpolation_ranges(
        self, voltage: float, expected_range: tuple[float, float]
    ):
        """Test that interpolated values fall within expected ranges."""
        result = voltage_to_percentage(voltage)
        assert expected_range[0] <= result <= expected_range[1], (
            f"At {voltage}V, expected {expected_range[0]}-{expected_range[1]}%, "
            f"got {result}%"
        )

    def test_midpoint_interpolation(self):
        """Midpoint between two table entries should give midpoint percentage."""
        # Use the first two table entries (4.20V=100%, 4.06V=90%)
        v_high, p_high = 4.20, 100
        v_low, p_low = 4.06, 90
        midpoint_v = (v_high + v_low) / 2  # 4.13V
        midpoint_p = (p_high + p_low) / 2  # 95%

        result = voltage_to_percentage(midpoint_v)
        # Allow small floating point tolerance
        assert abs(result - midpoint_p) < 0.01, (
            f"Midpoint voltage {midpoint_v}V should give ~{midpoint_p}%, "
            f"got {result}%"
        )

    def test_interpolation_is_linear(self):
        """Verify linear interpolation between adjacent table points."""
        # Test linearity between 3.82V (50%) and 3.87V (60%)
        v1, p1 = 3.82, 50
        v2, p2 = 3.87, 60

        # Test at 25%, 50%, and 75% between the points
        for fraction in [0.25, 0.50, 0.75]:
            test_voltage = v1 + fraction * (v2 - v1)
            expected_pct = p1 + fraction * (p2 - p1)
            result = voltage_to_percentage(test_voltage)

            assert abs(result - expected_pct) < 0.01, (
                f"At {test_voltage}V ({fraction*100}% between {v1}V and {v2}V), "
                f"expected {expected_pct}%, got {result}%"
            )

    # ==========================================================================
    # Monotonicity test
    # ==========================================================================

    def test_percentage_is_monotonic(self):
        """Battery percentage should decrease monotonically as voltage drops."""
        voltages = [v / 100 for v in range(420, 299, -1)]  # 4.20 down to 3.00
        percentages = [voltage_to_percentage(v) for v in voltages]

        for i in range(1, len(percentages)):
            assert percentages[i] <= percentages[i - 1], (
                f"Monotonicity violation: at {voltages[i]}V got {percentages[i]}%, "
                f"but at {voltages[i-1]}V got {percentages[i-1]}%"
            )

    # ==========================================================================
    # Type handling
    # ==========================================================================

    def test_integer_voltage_input(self):
        """Function should handle integer input."""
        # Integer 4 should be treated as 4.0V
        result = voltage_to_percentage(4)
        assert isinstance(result, float)
        assert 80.0 <= result <= 100.0  # 4.0V is between 3.98V (80%) and 4.06V (90%)


class TestVoltageTable:
    """Test the VOLTAGE_TABLE constant."""

    def test_table_is_sorted_descending(self):
        """Voltage table should be sorted in descending order by voltage."""
        voltages = [v for v, _ in VOLTAGE_TABLE]
        assert voltages == sorted(voltages, reverse=True), (
            "VOLTAGE_TABLE should be sorted by voltage in descending order"
        )

    def test_table_has_expected_endpoints(self):
        """Table should cover the full 18650 range."""
        voltages = [v for v, _ in VOLTAGE_TABLE]
        percentages = [p for _, p in VOLTAGE_TABLE]

        assert voltages[0] == 4.20, "Table should start at 4.20V (100%)"
        assert voltages[-1] == 3.00, "Table should end at 3.00V (0%)"
        assert percentages[0] == 100, "First entry should be 100%"
        assert percentages[-1] == 0, "Last entry should be 0%"

    def test_table_has_reasonable_entries(self):
        """Table should have enough entries for smooth interpolation."""
        assert len(VOLTAGE_TABLE) >= 10, "Table should have at least 10 entries"

    def test_percentages_are_descending(self):
        """Percentages should decrease as voltage decreases."""
        percentages = [p for _, p in VOLTAGE_TABLE]
        assert percentages == sorted(percentages, reverse=True), (
            "Percentages should be in descending order"
        )
