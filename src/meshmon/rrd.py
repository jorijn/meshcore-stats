"""RRD create, update, and graph helpers."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from .env import get_config
from .extract import format_rrd_value
from .metrics import is_counter_metric, get_graph_scale
from . import log

# Type alias for theme names
ThemeName = Literal["light", "dark"]


@dataclass(frozen=True, slots=True)
class ChartTheme:
    """Color palette for RRD chart rendering."""

    back: str
    canvas: str
    font: str
    axis: str
    frame: str
    arrow: str
    grid: str
    mgrid: str
    line: str
    area: str  # Includes alpha, e.g., "2563eb40"


# Radio Observatory design theme
# Light: Warm cream paper background with solar amber accent
# Dark: Deep observatory night sky with amber accent
CHART_THEMES: dict[ThemeName, ChartTheme] = {
    "light": ChartTheme(
        back="faf8f5",      # Warm cream paper
        canvas="ffffff",
        font="1a1915",      # Charcoal text
        axis="8a857a",      # Muted axis labels
        frame="e8e4dc",     # Subtle border
        arrow="8a857a",
        grid="e8e4dc",
        mgrid="d4cfc4",
        line="b45309",      # Solar amber / burnt orange
        area="b4530926",    # 15% opacity amber fill
    ),
    "dark": ChartTheme(
        back="0f1114",      # Deep observatory night
        canvas="161a1e",
        font="f0efe8",      # Light text
        axis="706d62",      # Muted axis labels
        frame="252a30",     # Subtle border
        arrow="706d62",
        grid="252a30",
        mgrid="2d333a",
        line="f59e0b",      # Bright amber
        area="f59e0b33",    # 20% opacity amber fill
    ),
}


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


def fetch_chart_stats(
    role: str,
    ds_name: str,
    period: str,
) -> Optional[dict[str, Any]]:
    """
    Fetch min/avg/max/current statistics for a metric from RRD.

    Args:
        role: "companion" or "repeater"
        ds_name: Data source name
        period: Time period ("day", "week", "month", "year")

    Returns:
        Dict with 'min', 'avg', 'max', 'current' keys, or None on error
    """
    if not RRDTOOL_AVAILABLE:
        return None

    rrd_path = get_rrd_path(role)
    if not rrd_path.exists():
        return None

    # Map period to rrdtool time spec
    period_map = {
        "day": "-1d",
        "week": "-1w",
        "month": "-1m",
        "year": "-1y",
    }
    start = period_map.get(period, "-1d")

    # Get scaling factor for display
    scale = get_graph_scale(ds_name)

    try:
        # Use rrdtool graph with PRINT to extract stats (writes to /dev/null)
        # This is more reliable than parsing fetch output
        args = [
            "/dev/null",  # Don't actually create a graph
            "--start", start,
            "--end", "now",
            f"DEF:raw={rrd_path}:{ds_name}:AVERAGE",
        ]

        # Apply scaling
        if scale == 1.0:
            args.append("CDEF:scaled=raw")
        elif scale > 1:
            args.append(f"CDEF:scaled=raw,{int(scale)},*")
        else:
            divisor = int(1 / scale)
            args.append(f"CDEF:scaled=raw,{divisor},/")

        # Add PRINT statements to extract stats
        args.extend([
            "VDEF:vmin=scaled,MINIMUM",
            "VDEF:vavg=scaled,AVERAGE",
            "VDEF:vmax=scaled,MAXIMUM",
            "VDEF:vlast=scaled,LAST",
            "PRINT:vmin:%lf",
            "PRINT:vavg:%lf",
            "PRINT:vmax:%lf",
            "PRINT:vlast:%lf",
        ])

        result = rrdtool.graphv(*args)
        # result is a dict with 'print[0]', 'print[1]', etc.
        stats = {
            "min": float(result.get("print[0]", "nan")),
            "avg": float(result.get("print[1]", "nan")),
            "max": float(result.get("print[2]", "nan")),
            "current": float(result.get("print[3]", "nan")),
        }

        # Filter out NaN values
        for key in stats:
            if stats[key] != stats[key]:  # NaN check
                stats[key] = None

        return stats

    except Exception as e:
        log.debug(f"Failed to fetch stats for {ds_name}: {e}")
        return None


def graph_rrd(
    role: str,
    ds_name: str,
    period: str,
    output_path: Path,
    title: Optional[str] = None,
    vertical_label: Optional[str] = None,
    width: int = 800,
    height: int = 280,
    theme: ThemeName = "light",
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
        theme: Color theme ("light" or "dark")

    Returns:
        True on success, False on error
    """
    if theme not in CHART_THEMES:
        raise ValueError(f"Unknown theme '{theme}'. Valid: {list(CHART_THEMES.keys())}")

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

    # Get theme colors
    colors = CHART_THEMES[theme]

    args = [
        str(output_path),
        "--start", start,
        "--width", str(width),
        "--height", str(height),
        # Colors from theme
        "--color", f"BACK#{colors.back}",
        "--color", f"CANVAS#{colors.canvas}",
        "--color", f"FONT#{colors.font}",
        "--color", f"MGRID#{colors.mgrid}",
        "--color", f"GRID#{colors.grid}",
        "--color", f"FRAME#{colors.frame}",
        "--color", f"ARROW#{colors.arrow}",
        "--color", f"AXIS#{colors.axis}",
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

    # Fixed Y-axis ranges for battery metrics
    if ds_name == "bat_v":
        args.extend(["--lower-limit", "3.0", "--upper-limit", "4.2"])
    elif ds_name == "bat_pct":
        args.extend(["--lower-limit", "0", "--upper-limit", "100"])

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

    args.append(f"CDEF:{ds_name}={ds_name}_scaled")

    # Area fill with semi-transparent primary color, then line on top
    args.append(f"AREA:{ds_name}#{colors.area}")
    args.append(f"LINE2:{ds_name}#{colors.line}")

    try:
        log.debug(f"Generating graph: {output_path}")
        rrdtool.graph(*args)
        return True
    except Exception as e:
        log.error(f"Failed to generate graph: {e}")
        return False


def render_all_charts(
    role: str,
    metrics: dict[str, str],
) -> tuple[list[Path], dict[str, dict[str, dict[str, Any]]]]:
    """
    Render all charts for a role in both light and dark themes.

    Also collects min/avg/max/current statistics for each metric/period.

    Args:
        role: "companion" or "repeater"
        metrics: Metrics config

    Returns:
        Tuple of (list of generated chart paths, stats dict)
        Stats dict structure: {metric_name: {period: {min, avg, max, current}}}
    """
    cfg = get_config()
    charts_dir = cfg.out_dir / "assets" / role
    periods = ["day", "week", "month", "year"]
    themes: list[ThemeName] = ["light", "dark"]

    generated = []
    all_stats: dict[str, dict[str, dict[str, Any]]] = {}

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
        "uptime": "Days",
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
        all_stats[ds_name] = {}

        for period in periods:
            # Fetch stats once per metric/period (not per theme)
            stats = fetch_chart_stats(role, ds_name, period)
            if stats:
                all_stats[ds_name][period] = stats

            for theme in themes:
                output_path = charts_dir / f"{ds_name}_{period}_{theme}.png"
                vlabel = labels.get(ds_name, "Value")

                if graph_rrd(
                    role=role,
                    ds_name=ds_name,
                    period=period,
                    output_path=output_path,
                    vertical_label=vlabel,
                    theme=theme,
                ):
                    generated.append(output_path)

    return generated, all_stats


def save_chart_stats(role: str, stats: dict[str, dict[str, dict[str, Any]]]) -> Path:
    """
    Save chart statistics to a JSON file.

    Args:
        role: "companion" or "repeater"
        stats: Stats dict from render_all_charts

    Returns:
        Path to the saved JSON file
    """
    cfg = get_config()
    stats_path = cfg.out_dir / "assets" / role / "chart_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    log.debug(f"Saved chart stats to {stats_path}")
    return stats_path


def load_chart_stats(role: str) -> dict[str, dict[str, dict[str, Any]]]:
    """
    Load chart statistics from JSON file.

    Args:
        role: "companion" or "repeater"

    Returns:
        Stats dict, or empty dict if file doesn't exist
    """
    cfg = get_config()
    stats_path = cfg.out_dir / "assets" / role / "chart_stats.json"

    if not stats_path.exists():
        return {}

    try:
        with open(stats_path) as f:
            return json.load(f)
    except Exception as e:
        log.debug(f"Failed to load chart stats: {e}")
        return {}
