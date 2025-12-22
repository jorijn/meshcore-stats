"""Battery voltage to percentage conversion for 18650 Li-ion cells."""


# Voltage to percentage lookup table for 18650 Li-ion cells
# Based on typical discharge curve: 4.20V = 100%, 3.00V = 0%
# Source: https://www.benzoenergy.com/blog/post/what-is-the-relationship-between-voltage-and-capacity-of-18650-li-ion-battery.html
VOLTAGE_TABLE = [
    (4.20, 100),
    (4.06, 90),
    (3.98, 80),
    (3.92, 70),
    (3.87, 60),
    (3.82, 50),
    (3.79, 40),
    (3.77, 30),
    (3.74, 20),
    (3.68, 10),
    (3.45, 5),
    (3.00, 0),
]


def voltage_to_percentage(voltage: float) -> float:
    """
    Convert 18650 Li-ion battery voltage to percentage.

    Uses piecewise linear interpolation between known points
    on the discharge curve for accuracy.

    Args:
        voltage: Battery voltage in volts

    Returns:
        Estimated battery percentage (0-100)
    """
    if voltage >= 4.20:
        return 100.0
    if voltage <= 3.00:
        return 0.0

    # Find the two points to interpolate between
    for i in range(len(VOLTAGE_TABLE) - 1):
        v_high, p_high = VOLTAGE_TABLE[i]
        v_low, p_low = VOLTAGE_TABLE[i + 1]
        if v_low <= voltage <= v_high:
            # Linear interpolation
            ratio = (voltage - v_low) / (v_high - v_low)
            return p_low + ratio * (p_high - p_low)

    return 0.0
