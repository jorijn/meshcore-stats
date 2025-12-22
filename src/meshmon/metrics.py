"""Centralized metrics configuration.

This module defines which metrics are counters (DERIVE) vs gauges (GAUGE),
and how they should be displayed. This is the single source of truth for
metric type information used by RRD creation, updates, and graphing.
"""

# Counter metrics use DERIVE in RRD (computes rate of change)
# These are cumulative counters that reset on device reboot
# RRD stores them as per-second rates
COUNTER_METRICS = {
    "rx", "tx",                    # Total packets
    "airtime", "rx_air",           # Airtime in seconds
    "fl_dups", "di_dups",          # Duplicate packet counts
    "fl_tx", "fl_rx",              # Flood packets
    "di_tx", "di_rx",              # Direct packets
}

# Airtime metrics are counters but displayed differently (seconds/min not packets/min)
AIRTIME_METRICS = {"airtime", "rx_air"}

# Metrics that need special scaling in graphs
GRAPH_SCALING = {
    # Counter metrics: per-second → per-minute (×60)
    "rx": 60,
    "tx": 60,
    "fl_dups": 60,
    "di_dups": 60,
    "fl_tx": 60,
    "fl_rx": 60,
    "di_tx": 60,
    "di_rx": 60,
    # Airtime: per-second → per-minute (×60)
    "airtime": 60,
    "rx_air": 60,
    # Uptime: seconds → hours (÷3600)
    "uptime": 1/3600,
}


def is_counter_metric(ds_name: str) -> bool:
    """Check if a metric is a counter (DERIVE) type."""
    return ds_name in COUNTER_METRICS


def get_graph_scale(ds_name: str) -> float:
    """Get the scaling factor for graphing a metric.

    Returns 1.0 for metrics that don't need scaling.
    """
    return GRAPH_SCALING.get(ds_name, 1.0)
