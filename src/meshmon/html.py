"""HTML rendering helpers using Jinja2 templates."""

from __future__ import annotations

import calendar
import shutil
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from jinja2 import Environment, PackageLoader, select_autoescape

from . import log
from .charts import load_chart_stats
from .env import get_config
from .formatters import (
    format_compact_number,
    format_duration,
    format_duration_compact,
    format_number,
    format_time,
    format_uptime,
    format_value,
)
from .metrics import (
    get_chart_metrics,
    get_metric_label,
    get_metric_unit,
    get_telemetry_metric_decimals,
    is_telemetry_metric,
)

if TYPE_CHECKING:
    from .reports import MonthlyAggregate, YearlyAggregate


class MetricDisplay(TypedDict, total=False):
    """A metric display item for the UI."""

    label: str
    value: str
    unit: str | None
    raw_value: int

# Status indicator thresholds (seconds)
STATUS_ONLINE_THRESHOLD = 1800  # 30 minutes
STATUS_STALE_THRESHOLD = 7200   # 2 hours

# Period titles and subtitles
PERIOD_CONFIG = {
    "day": ("24-Hour Observations", "Radio telemetry from the past day"),
    "week": ("7-Day Observations", "Radio telemetry from the past week"),
    "month": ("30-Day Observations", "Radio telemetry from the past month"),
    "year": ("365-Day Observations", "Radio telemetry from the past year"),
}

# Chart groupings for repeater (using firmware field names)
REPEATER_CHART_GROUPS = [
    {
        "title": "Power",
        "metrics": ["bat", "bat_pct"],
    },
    {
        "title": "Signal Quality",
        "metrics": ["last_rssi", "last_snr", "noise_floor"],
    },
    {
        "title": "Packet Traffic",
        "metrics": ["nb_recv", "nb_sent", "recv_flood", "sent_flood", "recv_direct", "sent_direct"],
    },
    {
        "title": "Airtime",
        "metrics": ["airtime", "rx_airtime"],
    },
    {
        "title": "Duplicates & Queue",
        "metrics": ["flood_dups", "direct_dups", "tx_queue_len", "uptime"],
    },
]

# Chart groupings for companion (using firmware field names)
COMPANION_CHART_GROUPS = [
    {
        "title": "Power",
        "metrics": ["battery_mv", "bat_pct"],
    },
    {
        "title": "Network",
        "metrics": ["contacts", "uptime_secs"],
    },
    {
        "title": "Packet Traffic",
        "metrics": ["recv", "sent"],
    },
]

# Singleton Jinja2 environment
_jinja_env: Environment | None = None


def get_jinja_env() -> Environment:
    """Get or create the singleton Jinja2 environment.

    Uses PackageLoader to load templates from src/meshmon/templates/
    with autoescape enabled for security.
    """
    global _jinja_env
    if _jinja_env is not None:
        return _jinja_env

    # Create environment with package loader
    env = Environment(
        loader=PackageLoader("meshmon", "templates"),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Register custom filters
    env.filters["format_time"] = format_time
    env.filters["format_value"] = format_value
    env.filters["format_number"] = format_number
    env.filters["format_duration"] = format_duration
    env.filters["format_uptime"] = format_uptime
    env.filters["format_compact_number"] = format_compact_number
    env.filters["format_duration_compact"] = format_duration_compact

    _jinja_env = env
    return env


def get_status(ts: int | None) -> tuple[str, str]:
    """Determine status based on timestamp age.

    Returns:
        (status_class, status_text) tuple
    """
    if not ts:
        return ("offline", "No data")

    age_seconds = int(datetime.now().timestamp()) - ts
    if age_seconds < STATUS_ONLINE_THRESHOLD:
        return ("online", "Online")
    elif age_seconds < STATUS_STALE_THRESHOLD:
        return ("stale", "Stale")
    else:
        return ("offline", "Offline")


def build_repeater_metrics(row: dict | None) -> dict:
    """Build metrics data from repeater database row.

    Args:
        row: Database row dict with firmware field names (bat, last_rssi, last_snr, etc.)
             Battery is in millivolts, bat_pct is computed at query time.

    Returns dict with critical_metrics, secondary_metrics, traffic_metrics.
    """
    if not row:
        return {
            "critical_metrics": [],
            "secondary_metrics": [],
            "traffic_metrics": [],
        }

    # Battery (stored in millivolts, convert to volts)
    bat_mv = row.get("bat")
    bat_v = bat_mv / 1000.0 if bat_mv is not None else None
    bat_pct = row.get("bat_pct")

    # Critical metrics (top 4 in sidebar)
    critical_metrics = []
    if bat_v is not None:
        critical_metrics.append({
            "value": f"{bat_v:.2f}",
            "unit": "V",
            "label": "Battery",
            "bar_pct": int(bat_pct) if bat_pct else 0,
        })
    if bat_pct is not None:
        critical_metrics.append({
            "value": f"{bat_pct:.0f}",
            "unit": "%",
            "label": "Charge",
        })

    rssi = row.get("last_rssi")
    if rssi is not None:
        critical_metrics.append({
            "value": str(int(rssi)),
            "unit": "dBm",
            "label": "RSSI",
        })

    snr = row.get("last_snr")
    if snr is not None:
        critical_metrics.append({
            "value": f"{snr:.2f}",
            "unit": "dB",
            "label": "SNR",
        })

    # Secondary metrics
    secondary_metrics = []
    uptime = row.get("uptime")
    if uptime is not None:
        secondary_metrics.append({
            "label": "Uptime",
            "value": format_duration_compact(int(uptime)),
        })

    noise = row.get("noise_floor")
    if noise is not None:
        secondary_metrics.append({
            "label": "Noise Floor",
            "value": f"{int(noise)} dBm",
        })

    txq = row.get("tx_queue_len")
    if txq is not None:
        secondary_metrics.append({
            "label": "TX Queue",
            "value": str(int(txq)),
        })

    # Traffic metrics (firmware field names)
    traffic_metrics = []
    traffic_fields = [
        ("RX", "nb_recv"),
        ("TX", "nb_sent"),
        ("Flood RX", "recv_flood"),
        ("Flood TX", "sent_flood"),
        ("Direct RX", "recv_direct"),
        ("Direct TX", "sent_direct"),
        ("Airtime TX", "airtime"),
        ("Airtime RX", "rx_airtime"),
    ]
    for label, key in traffic_fields:
        val = row.get(key)
        if val is not None:
            int_val = int(val)
            if "airtime" in key.lower():
                traffic_metrics.append({
                    "label": label,
                    "value": format_duration_compact(int_val),
                    "raw_value": int_val,
                    "unit": "seconds",
                })
            else:
                traffic_metrics.append({
                    "label": label,
                    "value": format_compact_number(int_val),
                    "raw_value": int_val,
                    "unit": "packets",
                })

    return {
        "critical_metrics": critical_metrics,
        "secondary_metrics": secondary_metrics,
        "traffic_metrics": traffic_metrics,
    }


def build_companion_metrics(row: dict | None) -> dict:
    """Build metrics data from companion database row.

    Args:
        row: Database row dict with firmware field names (battery_mv, contacts, etc.)
             Battery is in millivolts, bat_pct is computed at query time.

    Returns dict with critical_metrics, secondary_metrics, traffic_metrics.
    """
    if not row:
        return {
            "critical_metrics": [],
            "secondary_metrics": [],
            "traffic_metrics": [],
        }

    # Battery (stored in millivolts, convert to volts)
    bat_mv = row.get("battery_mv")
    bat_v = bat_mv / 1000.0 if bat_mv is not None else None
    bat_pct = row.get("bat_pct")

    # Critical metrics
    critical_metrics = []
    if bat_v is not None:
        critical_metrics.append({
            "value": f"{bat_v:.2f}",
            "unit": "V",
            "label": "Battery",
            "bar_pct": int(bat_pct) if bat_pct else 0,
        })
    if bat_pct is not None:
        critical_metrics.append({
            "value": f"{bat_pct:.0f}",
            "unit": "%",
            "label": "Charge",
        })

    contacts = row.get("contacts")
    if contacts is not None:
        critical_metrics.append({
            "value": str(int(contacts)),
            "unit": None,
            "label": "Contacts",
        })

    uptime = row.get("uptime_secs")
    if uptime is not None:
        critical_metrics.append({
            "value": format_duration_compact(int(uptime)),
            "unit": None,
            "label": "Uptime",
        })

    # Secondary metrics (empty for companion)
    secondary_metrics: list[MetricDisplay] = []

    # Traffic metrics for companion
    traffic_metrics = []
    rx = row.get("recv")
    if rx is not None:
        int_rx = int(rx)
        traffic_metrics.append({
            "label": "RX",
            "value": format_compact_number(int_rx),
            "raw_value": int_rx,
            "unit": "packets",
        })
    tx = row.get("sent")
    if tx is not None:
        int_tx = int(tx)
        traffic_metrics.append({
            "label": "TX",
            "value": format_compact_number(int_tx),
            "raw_value": int_tx,
            "unit": "packets",
        })

    return {
        "critical_metrics": critical_metrics,
        "secondary_metrics": secondary_metrics,
        "traffic_metrics": traffic_metrics,
    }


def _build_traffic_table_rows(traffic_metrics: list[dict]) -> list[dict]:
    """Convert flat traffic metrics to structured table rows with RX/TX columns.

    Input: List of dicts with 'label', 'value', 'raw_value', 'unit'
    Output: List of row dicts with 'label', 'rx', 'rx_raw', 'tx', 'tx_raw', 'unit'
    """
    rows_map: dict[str, dict] = {}

    for metric in traffic_metrics:
        label = metric.get("label", "")
        # Determine base name and direction from label
        if label == "RX":
            base, direction = "Packets", "rx"
        elif label == "TX":
            base, direction = "Packets", "tx"
        elif label.endswith(" RX"):
            base, direction = label[:-3], "rx"
        elif label.endswith(" TX"):
            base, direction = label[:-3], "tx"
        else:
            continue

        if base not in rows_map:
            rows_map[base] = {
                "label": base,
                "rx": None,
                "rx_raw": None,
                "tx": None,
                "tx_raw": None,
                "unit": metric.get("unit", ""),
            }

        rows_map[base][direction] = metric.get("value")
        rows_map[base][f"{direction}_raw"] = metric.get("raw_value")

    # Return in order: Packets, Flood, Direct, Airtime
    order = ["Packets", "Flood", "Direct", "Airtime"]
    return [rows_map[k] for k in order if k in rows_map]


def build_node_details(role: str) -> list[dict]:
    """Build node details for sidebar.

    Uses configuration values from environment.
    """
    cfg = get_config()
    details = []

    if role == "repeater":
        details.append({"label": "Location", "value": cfg.report_location_short})
        lat_dir = "N" if cfg.report_lat >= 0 else "S"
        lon_dir = "E" if cfg.report_lon >= 0 else "W"
        details.append({"label": "Coordinates", "value": f"{abs(cfg.report_lat):.4f}°{lat_dir}, {abs(cfg.report_lon):.4f}°{lon_dir}"})
        details.append({"label": "Elevation", "value": f"{cfg.report_elev:.0f} {cfg.report_elev_unit}"})
        details.append({"label": "Hardware", "value": cfg.repeater_hardware})
    elif role == "companion":
        details.append({"label": "Hardware", "value": cfg.companion_hardware})
        details.append({"label": "Connection", "value": "USB Serial"})

    return details


def build_radio_config() -> list[dict]:
    """Build radio config for sidebar.

    Uses configuration values from environment.
    """
    cfg = get_config()
    return [
        {"label": "Frequency", "value": cfg.radio_frequency},
        {"label": "Bandwidth", "value": cfg.radio_bandwidth},
        {"label": "Spread Factor", "value": cfg.radio_spread_factor},
        {"label": "Coding Rate", "value": cfg.radio_coding_rate},
    ]


def _format_stat_value(value: float | None, metric: str) -> str:
    """Format a statistic value for display in chart footer.

    Args:
        value: The numeric value (or None)
        metric: Metric name (firmware field name) to determine formatting

    Returns:
        Formatted string like "4.08 V", "85%", "2.3/min"
    """
    if value is None:
        return "-"

    # Telemetry metrics can be auto-discovered and need dynamic unit conversion.
    if is_telemetry_metric(metric):
        cfg = get_config()
        decimals = get_telemetry_metric_decimals(metric, cfg.display_unit_system)
        unit = get_metric_unit(metric, cfg.display_unit_system)
        formatted = f"{value:.{decimals}f}"
        return f"{formatted} {unit}" if unit else formatted

    # Determine format and suffix based on metric (using firmware field names)
    # Battery voltage (already transformed to volts in charts.py)
    if metric in ("bat", "battery_mv"):
        return f"{value:.2f} V"
    elif metric == "bat_pct":
        return f"{value:.0f}%"
    # Signal metrics
    elif metric in ("last_rssi", "noise_floor"):
        return f"{value:.0f} dBm"
    elif metric == "last_snr":
        return f"{value:.1f} dB"
    # Counters (contacts, queue)
    elif metric in ("contacts", "tx_queue_len"):
        return f"{value:.0f}"
    # Uptime (already scaled to days in charts.py)
    elif metric in ("uptime", "uptime_secs"):
        return f"{value:.1f} d"
    # Packet counters (per-minute rate from charts.py)
    elif metric in ("recv", "sent", "nb_recv", "nb_sent",
                    "recv_flood", "sent_flood", "recv_direct", "sent_direct",
                    "flood_dups", "direct_dups"):
        return f"{value:.1f}/min"
    # Airtime (per-minute rate from charts.py)
    elif metric in ("airtime", "rx_airtime"):
        return f"{value:.1f} s/min"
    else:
        return f"{value:.2f}"


def _load_svg_content(path: Path) -> str | None:
    """Load SVG file content for inline embedding.

    Args:
        path: Path to SVG file

    Returns:
        SVG content string, or None if file doesn't exist
    """
    if not path.exists():
        return None

    try:
        return path.read_text()
    except Exception as e:
        log.debug(f"Failed to load SVG {path}: {e}")
        return None


def build_chart_groups(
    role: str,
    period: str,
    chart_stats: dict | None = None,
    asset_prefix: str = "",
) -> list[dict]:
    """Build chart groups for template.

    Each group contains title and list of charts with their data.
    SVG content is loaded and included for inline embedding.

    Args:
        role: "companion" or "repeater"
        period: Time period ("day", "week", etc.)
        chart_stats: Stats dict from chart_stats.json (optional)
        asset_prefix: Relative path prefix to reach /assets from page location
    """
    cfg = get_config()
    available_metrics = sorted(chart_stats.keys()) if chart_stats else []
    chart_metrics = get_chart_metrics(
        role,
        available_metrics=available_metrics,
        telemetry_enabled=cfg.telemetry_enabled,
    )
    groups_config = [
        {"title": group["title"], "metrics": list(group["metrics"])}
        for group in (
            REPEATER_CHART_GROUPS if role == "repeater" else COMPANION_CHART_GROUPS
        )
    ]

    if role == "repeater" and cfg.telemetry_enabled:
        telemetry_metrics = [metric for metric in chart_metrics if is_telemetry_metric(metric)]
        if telemetry_metrics:
            groups_config.append(
                {
                    "title": "Telemetry",
                    "metrics": telemetry_metrics,
                }
            )

    if chart_stats is None:
        chart_stats = {}

    groups = []
    for group in groups_config:
        charts = []
        for metric in group["metrics"]:
            if metric not in chart_metrics:
                continue

            # Try SVG first (new format), fall back to PNG (legacy)
            svg_light_path = cfg.out_dir / "assets" / role / f"{metric}_{period}_light.svg"
            svg_dark_path = cfg.out_dir / "assets" / role / f"{metric}_{period}_dark.svg"
            png_light_path = cfg.out_dir / "assets" / role / f"{metric}_{period}_light.png"

            svg_light = _load_svg_content(svg_light_path)
            svg_dark = _load_svg_content(svg_dark_path)

            # Skip if neither SVG nor PNG exists
            if svg_light is None and not png_light_path.exists():
                continue

            # Get stats for this metric/period
            metric_stats = chart_stats.get(metric, {}).get(period, {})
            current_val = metric_stats.get("current")
            min_val = metric_stats.get("min")
            avg_val = metric_stats.get("avg")
            max_val = metric_stats.get("max")

            # Format current value for header
            current_formatted = _format_stat_value(current_val, metric) if current_val is not None else None

            # Build stats list for footer
            stats_list = None
            if any(v is not None for v in [min_val, avg_val, max_val]):
                stats_list = [
                    {"label": "Min", "value": _format_stat_value(min_val, metric)},
                    {"label": "Avg", "value": _format_stat_value(avg_val, metric)},
                    {"label": "Max", "value": _format_stat_value(max_val, metric)},
                ]

            # Build chart data for template - mixed types require Any
            chart_data: dict[str, Any] = {
                "label": get_metric_label(metric),
                "metric": metric,
                "current": current_formatted,
                "stats": stats_list,
            }

            # Include SVG content if available (for inline embedding)
            if svg_light is not None:
                chart_data["svg_light"] = svg_light
                chart_data["svg_dark"] = svg_dark
                chart_data["use_svg"] = True
            else:
                # Fallback to PNG paths
                asset_base = f"{asset_prefix}assets/{role}/"
                chart_data["src_light"] = f"{asset_base}{metric}_{period}_light.png"
                chart_data["src_dark"] = f"{asset_base}{metric}_{period}_dark.png"
                chart_data["use_svg"] = False

            charts.append(chart_data)

        if charts:
            groups.append({
                "title": group["title"],
                "charts": charts,
            })

    return groups


def build_page_context(
    role: str,
    period: str,
    row: dict | None,
    at_root: bool,
) -> dict[str, Any]:
    """Build template context dictionary for node pages.

    Args:
        role: "companion" or "repeater"
        period: "day", "week", "month", or "year"
        row: Latest metrics row from database (or None)
        at_root: Whether page is at site root (vs /companion/)
    """
    cfg = get_config()

    # Get node name from config
    node_name = cfg.repeater_display_name if role == "repeater" else cfg.companion_display_name

    # Pubkey prefix from config
    pubkey_pre = cfg.repeater_pubkey_prefix if role == "repeater" else cfg.companion_pubkey_prefix

    # Status based on timestamp
    ts = row.get("ts") if row else None
    status_class, status_text = get_status(ts)

    # Last updated
    last_updated = None
    last_updated_iso = None
    if ts:
        dt = datetime.fromtimestamp(ts).astimezone()
        last_updated = dt.strftime("%b %d, %Y at %H:%M %Z")
        last_updated_iso = dt.isoformat()

    # Build metrics for sidebar
    if role == "repeater":
        metrics_data = build_repeater_metrics(row)
    else:
        metrics_data = build_companion_metrics(row)

    # Node details
    node_details = build_node_details(role)

    # Radio config
    radio_config = build_radio_config()

    # Load chart stats and build chart groups
    chart_stats = load_chart_stats(role)

    # Relative path prefixes (avoid absolute paths for subpath deployments)
    css_path = "" if at_root else "../"
    asset_prefix = "" if at_root else "../"

    # Period config
    page_title, page_subtitle = PERIOD_CONFIG.get(period, ("Observations", "Radio telemetry"))
    if role == "companion":
        page_subtitle = page_subtitle.replace("Radio", "Companion node")

    # Meta description
    cfg = get_config()
    meta_descriptions = {
        "repeater": (
            f"Live stats for MeshCore LoRa repeater in {cfg.report_location_short}. "
            "Battery, signal strength, packet counts, and uptime charts."
        ),
        "companion": (
            "Live stats for MeshCore companion node. "
            "Battery, contacts, packet counts, and uptime monitoring."
        ),
    }

    chart_groups = build_chart_groups(role, period, chart_stats, asset_prefix=asset_prefix)

    # Navigation links depend on whether we're at root or in /companion/
    base_path = ""
    if at_root:
        repeater_link = "day.html"
        companion_link = "companion/day.html"
        reports_link = "reports/"
    else:
        repeater_link = "../day.html"
        companion_link = "day.html"
        reports_link = "../reports/"

    return {
        # Page meta
        "title": f"{node_name} — {period.capitalize()}",
        "meta_description": meta_descriptions.get(role, "MeshCore mesh network statistics dashboard."),
        "og_image": None,
        "css_path": css_path,
        "display_unit_system": cfg.display_unit_system,

        # Node info
        "node_name": node_name,
        "pubkey_pre": pubkey_pre,
        "role": role,
        "status_class": status_class,
        "status_text": status_text,

        # Sidebar metrics
        "critical_metrics": metrics_data["critical_metrics"],
        "secondary_metrics": metrics_data["secondary_metrics"],
        "traffic_metrics": metrics_data["traffic_metrics"],
        "traffic_table_rows": _build_traffic_table_rows(metrics_data["traffic_metrics"]),

        # Node details
        "node_details": node_details,
        "radio_config": radio_config,

        # Navigation
        "period": period,
        "base_path": base_path,
        "repeater_link": repeater_link,
        "companion_link": companion_link,
        "reports_link": reports_link,

        # Timestamps
        "last_updated": last_updated,
        "last_updated_iso": last_updated_iso,

        # Main content
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "chart_groups": chart_groups,

        # Custom HTML
        "custom_head_html": cfg.custom_head_html,
    }


def render_node_page(
    role: str,
    period: str,
    row: dict | None,
    at_root: bool = False,
) -> str:
    """Render a node page (companion or repeater).

    Args:
        role: "companion" or "repeater"
        period: "day", "week", "month", or "year"
        row: Latest metrics row from database (or None)
        at_root: Whether page is at site root (vs /companion/)
    """
    env = get_jinja_env()
    context = build_page_context(role, period, row, at_root)
    template = env.get_template("node.html")
    return str(template.render(**context))


def copy_static_assets():
    """Copy static assets (CSS, JS) to output directory."""
    cfg = get_config()
    templates_dir = Path(__file__).parent / "templates"

    # Files to copy from templates/ to out/
    static_files = ["styles.css", "chart-tooltip.js"]

    for filename in static_files:
        src = templates_dir / filename
        dst = cfg.out_dir / filename

        if src.exists():
            shutil.copy2(src, dst)
            log.debug(f"Copied {src} to {dst}")
        else:
            log.warn(f"Static asset not found: {src}")


def write_site(
    companion_row: dict | None,
    repeater_row: dict | None,
) -> list[Path]:
    """
    Write all static site pages.

    Repeater pages are rendered at the site root (day.html, week.html, etc.).
    Companion pages are rendered under /companion/.

    Args:
        companion_row: Latest companion metrics row from database (or None)
        repeater_row: Latest repeater metrics row from database (or None)

    Returns list of written paths.
    """
    cfg = get_config()
    written = []

    # Ensure output directories exist
    (cfg.out_dir / "companion").mkdir(parents=True, exist_ok=True)
    (cfg.out_dir / "assets" / "repeater").mkdir(parents=True, exist_ok=True)
    (cfg.out_dir / "assets" / "companion").mkdir(parents=True, exist_ok=True)

    # Copy static assets (CSS, JS)
    copy_static_assets()

    # Repeater pages at root level
    for period in ["day", "week", "month", "year"]:
        page_path = cfg.out_dir / f"{period}.html"
        page_path.write_text(
            render_node_page("repeater", period, repeater_row, at_root=True),
            encoding="utf-8",
        )
        written.append(page_path)
        log.debug(f"Wrote {page_path}")

    # Companion pages under /companion/
    for period in ["day", "week", "month", "year"]:
        page_path = cfg.out_dir / "companion" / f"{period}.html"
        page_path.write_text(
            render_node_page("companion", period, companion_row),
            encoding="utf-8",
        )
        written.append(page_path)
        log.debug(f"Wrote {page_path}")

    return written


# =============================================================================
# Report rendering functions
# =============================================================================


def _fmt_val_time(value: float | None, time_obj, fmt: str = ".2f", time_fmt: str = "%H:%M") -> str:
    """Format a value with time in <small> tag, matching redesign format."""
    if value is None:
        return "-"
    time_str = time_obj.strftime(time_fmt) if time_obj else ""
    if time_str:
        return f"{value:{fmt}} <small>{time_str}</small>"
    return f"{value:{fmt}}"


def _fmt_val_day(value: float | None, time_obj, fmt: str = ".2f") -> str:
    """Format a value with day number in <small> tag, for yearly data rows."""
    if value is None:
        return "-"
    day_str = f"{time_obj.day:02d}" if time_obj else ""
    if day_str:
        return f"{value:{fmt}} <small>{day_str}</small>"
    return f"{value:{fmt}}"


def _fmt_val_plain(value: float | None, fmt: str = ".2f") -> str:
    """Format a value without any suffix, for tfoot summary rows."""
    if value is None:
        return "-"
    return f"{value:{fmt}}"


def build_monthly_table_data(
    agg: MonthlyAggregate, role: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build table column groups, headers and rows for a monthly report.

    Args:
        agg: Monthly aggregate data
        role: "companion" or "repeater"

    Returns:
        (col_groups, headers, rows) where each is a list of dicts
    """
    from .reports import MetricStats

    # Define types upfront for mypy
    col_groups: list[dict[str, Any]]
    headers: list[dict[str, Any]]
    rows: list[dict[str, Any]]

    if role == "repeater":
        # Column groups matching redesign/reports/monthly.html
        col_groups = [
            {"label": "", "colspan": 1},
            {"label": "Battery", "colspan": 4},
            {"label": "Signal", "colspan": 3},
            {"label": "Packets", "colspan": 2},
            {"label": "Air", "colspan": 1},
        ]

        headers = [
            {"label": "Day", "tooltip": None},
            {"label": "Avg V", "tooltip": "Average battery voltage"},
            {"label": "Avg %", "tooltip": "Average battery percentage"},
            {"label": "Min V", "tooltip": "Minimum battery voltage with time"},
            {"label": "Max V", "tooltip": "Maximum battery voltage with time"},
            {"label": "RSSI", "tooltip": "Average signal strength (dBm)"},
            {"label": "SNR", "tooltip": "Average signal-to-noise ratio (dB)"},
            {"label": "Noise", "tooltip": "Average noise floor (dBm)"},
            {"label": "RX", "tooltip": "Total packets received"},
            {"label": "TX", "tooltip": "Total packets transmitted"},
            {"label": "Secs", "tooltip": "Total TX airtime (seconds)"},
        ]

        rows = []
        for daily in agg.daily:
            m = daily.metrics
            # Firmware: bat (mV), bat_pct, last_rssi, last_snr, noise_floor, nb_recv, nb_sent, airtime
            bat = m.get("bat", MetricStats())
            bat_pct = m.get("bat_pct", MetricStats())
            rssi = m.get("last_rssi", MetricStats())
            snr = m.get("last_snr", MetricStats())
            noise = m.get("noise_floor", MetricStats())
            rx = m.get("nb_recv", MetricStats())
            tx = m.get("nb_sent", MetricStats())
            airtime = m.get("airtime", MetricStats())

            # Convert mV to V for display
            bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
            bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
            bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": f"{daily.date.day:02d}", "class": None},
                    {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                    {"value": _fmt_val_time(bat_v_min, bat.min_time), "class": "muted"},
                    {"value": _fmt_val_time(bat_v_max, bat.max_time), "class": "muted"},
                    {"value": f"{rssi.mean:.0f}" if rssi.mean is not None else "-", "class": None},
                    {"value": f"{snr.mean:.1f}" if snr.mean is not None else "-", "class": None},
                    {"value": f"{noise.mean:.0f}" if noise.mean is not None else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
                    {"value": f"{airtime.total:,}" if airtime.total is not None else "-", "class": None},
                ],
            })

        # Add summary row
        s = agg.summary
        bat = s.get("bat", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        rssi = s.get("last_rssi", MetricStats())
        snr = s.get("last_snr", MetricStats())
        noise = s.get("noise_floor", MetricStats())
        rx = s.get("nb_recv", MetricStats())
        tx = s.get("nb_sent", MetricStats())
        airtime = s.get("airtime", MetricStats())

        bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
        bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
        bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "", "class": None},
                {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                {"value": _fmt_val_day(bat_v_min, bat.min_time), "class": "muted"},
                {"value": _fmt_val_day(bat_v_max, bat.max_time), "class": "muted"},
                {"value": f"{rssi.mean:.0f}" if rssi.mean is not None else "-", "class": None},
                {"value": f"{snr.mean:.1f}" if snr.mean is not None else "-", "class": None},
                {"value": f"{noise.mean:.0f}" if noise.mean is not None else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
                {"value": f"{airtime.total:,}" if airtime.total is not None else "-", "class": None},
            ],
        })

    else:  # companion
        col_groups = [
            {"label": "", "colspan": 1},
            {"label": "Battery", "colspan": 4},
            {"label": "Network", "colspan": 1},
            {"label": "Packets", "colspan": 2},
        ]

        headers = [
            {"label": "Day", "tooltip": None},
            {"label": "Avg V", "tooltip": "Average battery voltage"},
            {"label": "Avg %", "tooltip": "Average battery percentage"},
            {"label": "Min V", "tooltip": "Minimum battery voltage with time"},
            {"label": "Max V", "tooltip": "Maximum battery voltage with time"},
            {"label": "Contacts", "tooltip": "Average number of mesh contacts"},
            {"label": "RX", "tooltip": "Total packets received"},
            {"label": "TX", "tooltip": "Total packets transmitted"},
        ]

        rows = []
        for daily in agg.daily:
            m = daily.metrics
            # Firmware: battery_mv, bat_pct, contacts, recv, sent
            bat = m.get("battery_mv", MetricStats())
            bat_pct = m.get("bat_pct", MetricStats())
            contacts = m.get("contacts", MetricStats())
            rx = m.get("recv", MetricStats())
            tx = m.get("sent", MetricStats())

            # Convert mV to V for display
            bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
            bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
            bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": f"{daily.date.day:02d}", "class": None},
                    {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                    {"value": _fmt_val_time(bat_v_min, bat.min_time), "class": "muted"},
                    {"value": _fmt_val_time(bat_v_max, bat.max_time), "class": "muted"},
                    {"value": f"{contacts.mean:.0f}" if contacts.mean is not None else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
                ],
            })

        # Summary row
        s = agg.summary
        bat = s.get("battery_mv", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        contacts = s.get("contacts", MetricStats())
        rx = s.get("recv", MetricStats())
        tx = s.get("sent", MetricStats())

        bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
        bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
        bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "", "class": None},
                {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                {"value": _fmt_val_day(bat_v_min, bat.min_time), "class": "muted"},
                {"value": _fmt_val_day(bat_v_max, bat.max_time), "class": "muted"},
                {"value": f"{contacts.mean:.0f}" if contacts.mean is not None else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
            ],
        })

    return col_groups, headers, rows


def _fmt_val_month(value: float | None, time_obj, fmt: str = ".2f") -> str:
    """Format a value with month abbr in <small> tag, for yearly summary rows."""
    if value is None:
        return "-"
    month_str = calendar.month_abbr[time_obj.month] if time_obj else ""
    if month_str:
        return f"{value:{fmt}} <small>{month_str}</small>"
    return f"{value:{fmt}}"


def build_yearly_table_data(
    agg: YearlyAggregate, role: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Build table column groups, headers and rows for a yearly report.

    Args:
        agg: Yearly aggregate data
        role: "companion" or "repeater"

    Returns:
        (col_groups, headers, rows) where each is a list of dicts
    """
    from .reports import MetricStats

    # Define types upfront for mypy
    col_groups: list[dict[str, Any]]
    headers: list[dict[str, Any]]
    rows: list[dict[str, Any]]

    if role == "repeater":
        # Column groups matching redesign/reports/yearly.html
        col_groups = [
            {"label": "", "colspan": 2},
            {"label": "Battery", "colspan": 4},
            {"label": "Signal", "colspan": 2},
            {"label": "Packets", "colspan": 2},
        ]

        headers = [
            {"label": "Year", "tooltip": None},
            {"label": "Mo", "tooltip": None},
            {"label": "Volt", "tooltip": "Average battery voltage"},
            {"label": "%", "tooltip": "Average battery percentage"},
            {"label": "High", "tooltip": "Maximum battery voltage with day"},
            {"label": "Low", "tooltip": "Minimum battery voltage with day"},
            {"label": "RSSI", "tooltip": "Average signal strength (dBm)"},
            {"label": "SNR", "tooltip": "Average signal-to-noise ratio (dB)"},
            {"label": "RX", "tooltip": "Total packets received"},
            {"label": "TX", "tooltip": "Total packets transmitted"},
        ]

        rows = []
        for monthly in agg.monthly:
            s = monthly.summary
            # Firmware: bat (mV), bat_pct, last_rssi, last_snr, nb_recv, nb_sent
            bat = s.get("bat", MetricStats())
            bat_pct = s.get("bat_pct", MetricStats())
            rssi = s.get("last_rssi", MetricStats())
            snr = s.get("last_snr", MetricStats())
            rx = s.get("nb_recv", MetricStats())
            tx = s.get("nb_sent", MetricStats())

            # Convert mV to V
            bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
            bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
            bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": str(agg.year), "class": None},
                    {"value": f"{monthly.month:02d}", "class": None},
                    {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                    {"value": _fmt_val_day(bat_v_max, bat.max_time), "class": "muted"},
                    {"value": _fmt_val_day(bat_v_min, bat.min_time), "class": "muted"},
                    {"value": f"{rssi.mean:.0f}" if rssi.mean is not None else "-", "class": None},
                    {"value": f"{snr.mean:.1f}" if snr.mean is not None else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
                ],
            })

        # Summary row
        s = agg.summary
        bat = s.get("bat", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        rssi = s.get("last_rssi", MetricStats())
        snr = s.get("last_snr", MetricStats())
        rx = s.get("nb_recv", MetricStats())
        tx = s.get("nb_sent", MetricStats())

        bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
        bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
        bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "", "class": None},
                {"value": "", "class": None},
                {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                {"value": _fmt_val_month(bat_v_max, bat.max_time), "class": "muted"},
                {"value": _fmt_val_month(bat_v_min, bat.min_time), "class": "muted"},
                {"value": f"{rssi.mean:.0f}" if rssi.mean is not None else "-", "class": None},
                {"value": f"{snr.mean:.1f}" if snr.mean is not None else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
            ],
        })

    else:  # companion
        col_groups = [
            {"label": "", "colspan": 2},
            {"label": "Battery", "colspan": 4},
            {"label": "Network", "colspan": 1},
            {"label": "Packets", "colspan": 2},
        ]

        headers = [
            {"label": "Year", "tooltip": None},
            {"label": "Mo", "tooltip": None},
            {"label": "Volt", "tooltip": "Average battery voltage"},
            {"label": "%", "tooltip": "Average battery percentage"},
            {"label": "High", "tooltip": "Maximum battery voltage with day"},
            {"label": "Low", "tooltip": "Minimum battery voltage with day"},
            {"label": "Contacts", "tooltip": "Average number of mesh contacts"},
            {"label": "RX", "tooltip": "Total packets received"},
            {"label": "TX", "tooltip": "Total packets transmitted"},
        ]

        rows = []
        for monthly in agg.monthly:
            s = monthly.summary
            # Firmware: battery_mv, bat_pct, contacts, recv, sent
            bat = s.get("battery_mv", MetricStats())
            bat_pct = s.get("bat_pct", MetricStats())
            contacts = s.get("contacts", MetricStats())
            rx = s.get("recv", MetricStats())
            tx = s.get("sent", MetricStats())

            # Convert mV to V
            bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
            bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
            bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": str(agg.year), "class": None},
                    {"value": f"{monthly.month:02d}", "class": None},
                    {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                    {"value": _fmt_val_day(bat_v_max, bat.max_time), "class": "muted"},
                    {"value": _fmt_val_day(bat_v_min, bat.min_time), "class": "muted"},
                    {"value": f"{contacts.mean:.0f}" if contacts.mean is not None else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
                ],
            })

        # Summary row
        s = agg.summary
        bat = s.get("battery_mv", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        contacts = s.get("contacts", MetricStats())
        rx = s.get("recv", MetricStats())
        tx = s.get("sent", MetricStats())

        bat_v_mean = bat.mean / 1000.0 if bat.mean is not None else None
        bat_v_min = bat.min_value / 1000.0 if bat.min_value is not None else None
        bat_v_max = bat.max_value / 1000.0 if bat.max_value is not None else None

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "", "class": None},
                {"value": "", "class": None},
                {"value": f"{bat_v_mean:.2f}" if bat_v_mean is not None else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean is not None else "-", "class": None},
                {"value": _fmt_val_month(bat_v_max, bat.max_time), "class": "muted"},
                {"value": _fmt_val_month(bat_v_min, bat.min_time), "class": "muted"},
                {"value": f"{contacts.mean:.0f}" if contacts.mean is not None else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total is not None else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total is not None else "-", "class": None},
            ],
        })

    return col_groups, headers, rows


def render_report_page(
    agg: Any,
    node_name: str,
    report_type: str,
    prev_report: dict | None = None,
    next_report: dict | None = None,
) -> str:
    """Render a report page (monthly or yearly).

    Args:
        agg: MonthlyAggregate or YearlyAggregate
        node_name: Name of the node
        report_type: "monthly" or "yearly"
        prev_report: Dict with 'url' and 'label' for previous report link
        next_report: Dict with 'url' and 'label' for next report link

    Returns:
        Rendered HTML string
    """
    from .reports import format_lat_lon_dms

    cfg = get_config()
    env = get_jinja_env()

    coords_str = format_lat_lon_dms(cfg.report_lat, cfg.report_lon)
    now = datetime.now()

    monthly_links = None
    if report_type == "monthly":
        report_title = calendar.month_name[agg.month] + " " + str(agg.year)
        report_subtitle = f"Monthly report for {node_name}"
        download_prefix = f"{agg.role}-{agg.year}-{agg.month:02d}"
        month_name = calendar.month_name[agg.month]
        col_groups, headers, rows = build_monthly_table_data(agg, agg.role)
    else:
        report_title = str(agg.year)
        report_subtitle = f"Yearly report for {node_name}"
        download_prefix = f"{agg.role}-{agg.year}"
        month_name = None
        col_groups, headers, rows = build_yearly_table_data(agg, agg.role)
        # Build monthly links for yearly reports
        monthly_links = []
        for monthly in agg.monthly:
            monthly_links.append({
                "url": f"{monthly.month:02d}/",
                "label": calendar.month_abbr[monthly.month],
            })

    # Calculate CSS path depth for reports (always /reports/{role}/{year}/ or /reports/{role}/{year}/{month}/)
    css_path = "../../../../" if report_type == "monthly" else "../../../"

    context = {
        "title": report_title,
        "meta_description": f"MeshCore {report_type} report for {node_name}",
        "css_path": css_path,
        "report_type": report_type,
        "role": agg.role,
        "year": agg.year,
        "month_name": month_name,
        "report_title": report_title,
        "report_subtitle": report_subtitle,
        "node_name": node_name,
        "location_name": cfg.report_location_name,
        "coords_str": coords_str,
        "elev": f"{cfg.report_elev:.0f}",
        "generated_at": now.strftime("%Y-%m-%d %H:%M"),
        "generated_iso": now.isoformat(),
        "download_prefix": download_prefix,
        "table_headers": headers,
        "table_rows": rows,
        "col_groups": col_groups,
        "monthly_links": monthly_links,
        "prev_report": prev_report,
        "next_report": next_report,
        "custom_head_html": cfg.custom_head_html,
    }

    template = env.get_template("report.html")
    return str(template.render(**context))


def render_reports_index(report_sections: list[dict]) -> str:
    """Render the reports index page.

    Args:
        report_sections: List of dicts with 'role' and 'years' keys.
            Each year has 'year' and 'months' (list of dicts with 'month' and 'name')

    Returns:
        Rendered HTML string
    """
    cfg = get_config()
    env = get_jinja_env()

    # Add descriptions to sections
    descriptions = {
        "repeater": f"{cfg.repeater_display_name} — Remote node in {cfg.report_location_short}",
        "companion": f"{cfg.companion_display_name} — Local USB-connected node",
    }

    for section in report_sections:
        section["description"] = descriptions.get(section["role"], "")

    # Month abbreviations for template
    month_abbrs = {i: calendar.month_abbr[i] for i in range(1, 13)}

    context = {
        "title": "Reports Archive",
        "meta_description": "Monthly and yearly statistics reports for MeshCore nodes",
        "css_path": "../",
        "report_sections": report_sections,
        "month_abbrs": month_abbrs,
        "custom_head_html": cfg.custom_head_html,
    }

    template = env.get_template("report_index.html")
    return str(template.render(**context))
