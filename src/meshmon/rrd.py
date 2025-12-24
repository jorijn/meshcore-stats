"""RRD create, update, and graph helpers."""

from pathlib import Path
from typing import Optional

from .env import get_config
from .extract import format_rrd_value
from .metrics import is_counter_metric, get_graph_scale
from . import log

# Try to import rrdtool
try:
    import rrdtool
    RRDTOOL_AVAILABLE = True
except ImportError:
    RRDTOOL_AVAILABLE = False
    rrdtool = None


def get_rrd_path(role: str) -> Path:
    """Get path to RRD file for a role."""
    cfg = get_config()
    return cfg.rrd_dir / f"{role}.rrd"


def create_rrd(
    role: str,
    metrics: dict[str, str],
    step: int,
    start_time: Optional[int] = None,
) -> bool:
    """
    Create an RRD file if it doesn't exist.

    Args:
        role: "companion" or "repeater"
        metrics: Dict of ds_name -> path (we use ds_names)
        step: Step interval in seconds
        start_time: Start time (default: now - 10s)

    Returns:
        True if created or already exists, False on error
    """
    if not RRDTOOL_AVAILABLE:
        log.error("rrdtool-bindings not available")
        return False

    rrd_path = get_rrd_path(role)

    if rrd_path.exists():
        log.debug(f"RRD already exists: {rrd_path}")
        return True

    rrd_path.parent.mkdir(parents=True, exist_ok=True)

    # Build DS definitions
    # Heartbeat = step * 2 (allow missing one update)
    heartbeat = step * 2
    ds_defs = []

    for ds_name in sorted(metrics.keys()):
        if is_counter_metric(ds_name):
            # DERIVE computes rate of change, min 0 to ignore counter resets
            ds_defs.append(f"DS:{ds_name}:DERIVE:{heartbeat}:0:U")
        else:
            # GAUGE for instantaneous values
            ds_defs.append(f"DS:{ds_name}:GAUGE:{heartbeat}:U:U")

    # Build RRA definitions for day/week/month/year
    # AVERAGE consolidation function
    rra_defs = []

    # Day: 1-step resolution for 24 hours
    # For companion (60s step): 24*60 = 1440 rows
    # For repeater (900s step): 24*4 = 96 rows
    day_rows = (24 * 3600) // step
    rra_defs.append(f"RRA:AVERAGE:0.5:1:{day_rows}")

    # Week: 5-minute resolution for 7 days
    # Steps per 5 min = 300 / step
    week_steps = max(1, 300 // step)
    week_rows = (7 * 24 * 3600) // (week_steps * step)
    rra_defs.append(f"RRA:AVERAGE:0.5:{week_steps}:{week_rows}")

    # Month: 30-minute resolution for 31 days
    month_steps = max(1, 1800 // step)
    month_rows = (31 * 24 * 3600) // (month_steps * step)
    rra_defs.append(f"RRA:AVERAGE:0.5:{month_steps}:{month_rows}")

    # Year: 2-hour resolution for 365 days
    year_steps = max(1, 7200 // step)
    year_rows = (365 * 24 * 3600) // (year_steps * step)
    rra_defs.append(f"RRA:AVERAGE:0.5:{year_steps}:{year_rows}")

    # Also add MIN/MAX for some use cases
    rra_defs.append(f"RRA:MIN:0.5:1:{day_rows}")
    rra_defs.append(f"RRA:MAX:0.5:1:{day_rows}")

    # Build full args
    args = [str(rrd_path), "--step", str(step)]
    if start_time:
        args.extend(["--start", str(start_time - 10)])
    args.extend(ds_defs)
    args.extend(rra_defs)

    try:
        log.debug(f"Creating RRD: {' '.join(args)}")
        rrdtool.create(*args)
        log.info(f"Created RRD: {rrd_path}")
        return True
    except Exception as e:
        log.error(f"Failed to create RRD: {e}")
        return False


def update_rrd(
    role: str,
    ts: int,
    values: dict[str, Optional[float]],
    metrics: dict[str, str],
) -> bool:
    """
    Update RRD with new values.

    Args:
        role: "companion" or "repeater"
        ts: Unix timestamp
        values: Dict of ds_name -> value (None for unknown)
        metrics: Metrics config (to get DS order)

    Returns:
        True on success, False on error
    """
    if not RRDTOOL_AVAILABLE:
        log.error("rrdtool-bindings not available")
        return False

    rrd_path = get_rrd_path(role)
    if not rrd_path.exists():
        log.error(f"RRD does not exist: {rrd_path}")
        return False

    # Build update string: timestamp:val1:val2:...
    # Values must be in same order as DS definitions (sorted by name)
    # Counter metrics (DERIVE) require integer values
    ds_names = sorted(metrics.keys())
    value_strs = [
        format_rrd_value(values.get(name), as_integer=is_counter_metric(name))
        for name in ds_names
    ]
    update_str = f"{ts}:{':'.join(value_strs)}"

    try:
        log.debug(f"Updating RRD: {rrd_path} with {update_str}")
        rrdtool.update(str(rrd_path), update_str)
        return True
    except Exception as e:
        log.error(f"Failed to update RRD: {e}")
        return False


def graph_rrd(
    role: str,
    ds_name: str,
    period: str,
    output_path: Path,
    title: Optional[str] = None,
    vertical_label: Optional[str] = None,
    width: int = 800,
    height: int = 280,
) -> bool:
    """
    Generate a graph from RRD data.

    Args:
        role: "companion" or "repeater"
        ds_name: Data source name to graph
        period: Time period ("day", "week", "month", "year")
        output_path: Output PNG path
        title: Graph title (not shown in chart, used in card header)
        vertical_label: Y-axis label
        width: Graph width in pixels
        height: Graph height in pixels

    Returns:
        True on success, False on error
    """
    if not RRDTOOL_AVAILABLE:
        log.error("rrdtool-bindings not available")
        return False

    rrd_path = get_rrd_path(role)
    if not rrd_path.exists():
        log.error(f"RRD does not exist: {rrd_path}")
        return False

    # Map period to rrdtool time spec
    period_map = {
        "day": "-1d",
        "week": "-1w",
        "month": "-1m",
        "year": "-1y",
    }
    start = period_map.get(period, "-1d")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Design system colors (matching CSS variables)
    color_primary = "2563eb"        # --primary (blue)
    color_primary_light = "dbeafe"  # --primary-light
    color_text = "1e293b"           # --text
    color_text_muted = "64748b"     # --text-muted
    color_border = "e2e8f0"         # --border
    color_bg = "ffffff"             # --bg-elevated (white)
    color_canvas = "f8fafc"         # --bg (slightly gray)

    args = [
        str(output_path),
        "--start", start,
        "--width", str(width),
        "--height", str(height),
        # Colors matching design system
        "--color", f"BACK#{color_bg}",
        "--color", f"CANVAS#{color_bg}",
        "--color", f"FONT#{color_text}",
        "--color", f"MGRID#{color_border}",
        "--color", f"GRID#{color_border}",
        "--color", f"FRAME#{color_border}",
        "--color", f"ARROW#{color_text_muted}",
        "--color", f"AXIS#{color_text_muted}",
        # Styling
        "--border", "0",
        "--full-size-mode",
        "--slope-mode",
        "--alt-autoscale",
        "--rigid",
        # Larger fonts for readability when scaled down
        "--font", "DEFAULT:12:",
        "--font", "LEGEND:14:",
        "--font", "UNIT:12:",
        "--font", "AXIS:11:",
    ]

    if vertical_label:
        args.extend(["--vertical-label", vertical_label])

    args.append(f"DEF:{ds_name}_raw={rrd_path}:{ds_name}:AVERAGE")

    # Apply scaling based on metric type
    scale = get_graph_scale(ds_name)
    if scale == 1.0:
        args.append(f"CDEF:{ds_name}_scaled={ds_name}_raw")
    elif scale > 1:
        # Multiply (e.g., per-second to per-minute: ×60)
        args.append(f"CDEF:{ds_name}_scaled={ds_name}_raw,{int(scale)},*")
    else:
        # Divide (e.g., seconds to hours: ÷3600)
        divisor = int(1 / scale)
        args.append(f"CDEF:{ds_name}_scaled={ds_name}_raw,{divisor},/")

    # Apply smoothing to battery metrics to reduce fluctuations
    # TREND applies a centered moving average over a time window
    if ds_name in ("bat_v", "bat_pct"):
        # Smoothing window: 2 hours for better stability
        args.append(f"CDEF:{ds_name}={ds_name}_scaled,7200,TREND")
    else:
        args.append(f"CDEF:{ds_name}={ds_name}_scaled")

    # Area fill with semi-transparent primary color, then line on top
    args.append(f"AREA:{ds_name}#{color_primary}40")  # 40 = ~25% opacity
    args.append(f"LINE2:{ds_name}#{color_primary}:  ")  # Label with spacing

    # Add statistics (min/avg/max/current) below the chart
    args.append(f"GPRINT:{ds_name}:MIN:Min\\: %6.2lf%s")
    args.append(f"GPRINT:{ds_name}:AVERAGE:Avg\\: %6.2lf%s")
    args.append(f"GPRINT:{ds_name}:MAX:Max\\: %6.2lf%s")
    args.append(f"GPRINT:{ds_name}:LAST:Current\\: %6.2lf%s\\n")

    try:
        log.debug(f"Generating graph: {output_path}")
        rrdtool.graph(*args)
        return True
    except Exception as e:
        log.error(f"Failed to generate graph: {e}")
        return False


def render_all_charts(role: str, metrics: dict[str, str]) -> list[Path]:
    """
    Render all charts for a role.

    Args:
        role: "companion" or "repeater"
        metrics: Metrics config

    Returns:
        List of generated chart paths
    """
    cfg = get_config()
    charts_dir = cfg.out_dir / "assets" / role
    periods = ["day", "week", "month", "year"]

    generated = []

    # Define labels for known metrics
    labels = {
        "bat_v": "Voltage (V)",
        "bat_pct": "Battery (%)",
        "contacts": "Count",
        "neigh": "Count",
        "rx": "Packets/min",
        "tx": "Packets/min",
        "rssi": "RSSI (dBm)",
        "snr": "SNR (dB)",
        "uptime": "Hours",
        "noise": "dBm",
        "airtime": "Seconds/min",
        "rx_air": "Seconds/min",
        "fl_dups": "Packets/min",
        "di_dups": "Packets/min",
        "fl_tx": "Packets/min",
        "fl_rx": "Packets/min",
        "di_tx": "Packets/min",
        "di_rx": "Packets/min",
        "txq": "Queue depth",
    }

    for ds_name in sorted(metrics.keys()):
        for period in periods:
            output_path = charts_dir / f"{ds_name}_{period}.png"
            vlabel = labels.get(ds_name, "Value")

            if graph_rrd(
                role=role,
                ds_name=ds_name,
                period=period,
                output_path=output_path,
                vertical_label=vlabel,
            ):
                generated.append(output_path)

    return generated
