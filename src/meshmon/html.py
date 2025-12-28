"""HTML rendering helpers using Jinja2 templates."""

import calendar
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, PackageLoader, select_autoescape

from .env import get_config
from .extract import get_by_path
from .battery import voltage_to_percentage
from .formatters import (
    format_time,
    format_value,
    format_number,
    format_duration,
    format_uptime,
)
from . import log


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

# Chart groupings for repeater
REPEATER_CHART_GROUPS = [
    {
        "title": "Power",
        "metrics": ["bat_v", "bat_pct"],
    },
    {
        "title": "Signal Quality",
        "metrics": ["rssi", "snr", "noise"],
    },
    {
        "title": "Packet Traffic",
        "metrics": ["rx", "tx", "fl_rx", "fl_tx", "di_rx", "di_tx"],
    },
    {
        "title": "Airtime",
        "metrics": ["airtime", "rx_air"],
    },
    {
        "title": "Duplicates & Queue",
        "metrics": ["fl_dups", "di_dups", "txq", "uptime"],
    },
]

# Chart groupings for companion
COMPANION_CHART_GROUPS = [
    {
        "title": "Power",
        "metrics": ["bat_v", "bat_pct"],
    },
    {
        "title": "Network",
        "metrics": ["contacts", "uptime"],
    },
    {
        "title": "Packet Traffic",
        "metrics": ["rx", "tx"],
    },
]

# Chart labels
CHART_LABELS = {
    "bat_v": "Battery Voltage",
    "bat_pct": "Battery Percentage",
    "contacts": "Known Contacts",
    "neigh": "Neighbours",
    "rx": "Packets Received",
    "tx": "Packets Transmitted",
    "rssi": "RSSI",
    "snr": "Signal-to-Noise Ratio",
    "uptime": "Uptime",
    "noise": "Noise Floor",
    "airtime": "TX Airtime",
    "rx_air": "RX Airtime",
    "fl_dups": "Flood Duplicates",
    "di_dups": "Direct Duplicates",
    "fl_tx": "Flood TX",
    "fl_rx": "Flood RX",
    "di_tx": "Direct TX",
    "di_rx": "Direct RX",
    "txq": "TX Queue Length",
}

# Singleton Jinja2 environment
_jinja_env: Optional[Environment] = None


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

    _jinja_env = env
    return env


def get_status(ts: Optional[int]) -> tuple[str, str]:
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


def build_repeater_metrics(snapshot: Optional[dict]) -> dict:
    """Build metrics data from repeater snapshot.

    Returns dict with critical_metrics, secondary_metrics, traffic_metrics.
    """
    if not snapshot:
        return {
            "critical_metrics": [],
            "secondary_metrics": [],
            "traffic_metrics": [],
        }

    status = snapshot.get("status", {})

    # Battery
    bat_mv = status.get("bat")
    bat_v = bat_mv / 1000 if bat_mv else None
    bat_pct = voltage_to_percentage(bat_v) if bat_v else None

    # Critical metrics (top 4 in sidebar)
    critical_metrics = []
    if bat_v:
        critical_metrics.append({
            "value": f"{bat_v:.2f}",
            "unit": "V",
            "label": "Battery",
            "bar_pct": int(bat_pct) if bat_pct else 0,
        })
    if bat_pct:
        critical_metrics.append({
            "value": f"{bat_pct:.0f}",
            "unit": "%",
            "label": "Charge",
        })

    rssi = status.get("last_rssi")
    if rssi is not None:
        critical_metrics.append({
            "value": str(rssi),
            "unit": "dBm",
            "label": "RSSI",
        })

    snr = status.get("last_snr")
    if snr is not None:
        critical_metrics.append({
            "value": f"{snr:.2f}",
            "unit": "dB",
            "label": "SNR",
        })

    # Secondary metrics
    secondary_metrics = []
    uptime = status.get("uptime")
    if uptime is not None:
        secondary_metrics.append({
            "label": "Uptime",
            "value": format_uptime(uptime),
        })

    noise = status.get("noise_floor")
    if noise is not None:
        secondary_metrics.append({
            "label": "Noise Floor",
            "value": f"{noise} dBm",
        })

    txq = status.get("tx_queue_len")
    if txq is not None:
        secondary_metrics.append({
            "label": "TX Queue",
            "value": str(txq),
        })

    # Traffic metrics
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
        val = status.get(key)
        if val is not None:
            if "airtime" in key.lower():
                traffic_metrics.append({"label": label, "value": f"{val:,}s"})
            else:
                traffic_metrics.append({"label": label, "value": f"{val:,}"})

    return {
        "critical_metrics": critical_metrics,
        "secondary_metrics": secondary_metrics,
        "traffic_metrics": traffic_metrics,
    }


def build_companion_metrics(snapshot: Optional[dict]) -> dict:
    """Build metrics data from companion snapshot.

    Returns dict with critical_metrics, secondary_metrics.
    """
    if not snapshot:
        return {
            "critical_metrics": [],
            "secondary_metrics": [],
            "traffic_metrics": [],
        }

    stats = snapshot.get("stats", {}).get("core", {})
    packets = snapshot.get("stats", {}).get("packets", {})
    derived = snapshot.get("derived", {})

    # Battery
    bat_mv = stats.get("battery_mv")
    if not bat_mv:
        bat_mv = get_by_path(snapshot, "bat.level")
    bat_v = bat_mv / 1000 if bat_mv else None
    bat_pct = voltage_to_percentage(bat_v) if bat_v else None

    # Critical metrics
    critical_metrics = []
    if bat_v:
        critical_metrics.append({
            "value": f"{bat_v:.2f}",
            "unit": "V",
            "label": "Battery",
            "bar_pct": int(bat_pct) if bat_pct else 0,
        })
    if bat_pct:
        critical_metrics.append({
            "value": f"{bat_pct:.0f}",
            "unit": "%",
            "label": "Charge",
        })

    contacts = derived.get("contacts_count")
    if contacts is not None:
        critical_metrics.append({
            "value": str(contacts),
            "unit": None,
            "label": "Contacts",
        })

    uptime = stats.get("uptime_secs")
    if uptime is not None:
        critical_metrics.append({
            "value": format_uptime(uptime),
            "unit": None,
            "label": "Uptime",
        })

    # Secondary metrics
    secondary_metrics = []
    rx = packets.get("recv")
    if rx is not None:
        secondary_metrics.append({"label": "Packets RX", "value": f"{rx:,}"})
    tx = packets.get("sent")
    if tx is not None:
        secondary_metrics.append({"label": "Packets TX", "value": f"{tx:,}"})

    return {
        "critical_metrics": critical_metrics,
        "secondary_metrics": secondary_metrics,
        "traffic_metrics": [],
    }


def build_node_details(role: str, snapshot: Optional[dict]) -> list[dict]:
    """Build node details for sidebar."""
    cfg = get_config()
    details = []

    if role == "repeater":
        details.append({"label": "Location", "value": "Oosterhout, NL"})
        details.append({"label": "Coordinates", "value": f"{cfg.report_lat:.4f}°N, {cfg.report_lon:.4f}°E"})
        details.append({"label": "Elevation", "value": f"{cfg.report_elev:.0f}m"})
        details.append({"label": "Hardware", "value": "SenseCAP P1-Pro"})
    elif role == "companion" and snapshot:
        device_info = snapshot.get("device_info", {})
        model = device_info.get("model", "Unknown")
        ver = device_info.get("ver", "Unknown")
        details.append({"label": "Model", "value": model})
        details.append({"label": "Firmware", "value": ver})
        details.append({"label": "Connection", "value": "USB Serial"})

    return details


def build_radio_config(snapshot: Optional[dict]) -> list[dict]:
    """Build radio config for sidebar."""
    if not snapshot:
        return []

    self_info = snapshot.get("self_info", {})
    if not self_info:
        # For repeater, we might not have self_info, use defaults
        return [
            {"label": "Frequency", "value": "869.618 MHz"},
            {"label": "Bandwidth", "value": "62.5 kHz"},
            {"label": "Spread Factor", "value": "SF8"},
            {"label": "Coding Rate", "value": "CR8"},
        ]

    config = []
    freq = self_info.get("radio_freq")
    if freq:
        config.append({"label": "Frequency", "value": f"{freq} MHz"})
    bw = self_info.get("radio_bw")
    if bw:
        config.append({"label": "Bandwidth", "value": f"{bw} kHz"})
    sf = self_info.get("radio_sf")
    if sf:
        config.append({"label": "Spread Factor", "value": f"SF{sf}"})
    cr = self_info.get("radio_cr")
    if cr:
        config.append({"label": "Coding Rate", "value": f"CR{cr}"})

    return config


def build_chart_groups(
    role: str,
    period: str,
    metrics: dict[str, str],
) -> list[dict]:
    """Build chart groups for template.

    Each group contains title and list of charts with their data.
    """
    cfg = get_config()
    groups_config = REPEATER_CHART_GROUPS if role == "repeater" else COMPANION_CHART_GROUPS

    groups = []
    for group in groups_config:
        charts = []
        for metric in group["metrics"]:
            if metric not in metrics:
                continue

            # Check if chart exists
            chart_path = cfg.out_dir / "assets" / role / f"{metric}_{period}_light.png"
            if not chart_path.exists():
                continue

            charts.append({
                "label": CHART_LABELS.get(metric, metric),
                "src_light": f"/assets/{role}/{metric}_{period}_light.png",
                "src_dark": f"/assets/{role}/{metric}_{period}_dark.png",
                "current": None,  # Could be populated from RRD if needed
                "stats": None,    # Could be populated from RRD if needed
            })

        if charts:
            groups.append({
                "title": group["title"],
                "charts": charts,
            })

    return groups


def build_page_context(
    role: str,
    period: str,
    snapshot: Optional[dict],
    metrics: dict[str, str],
    at_root: bool,
) -> dict[str, Any]:
    """Build template context dictionary for node pages."""
    cfg = get_config()

    # Get node name
    node_name = role.capitalize()
    pubkey_pre = None
    if snapshot:
        node_name = (
            get_by_path(snapshot, "node.name")
            or get_by_path(snapshot, "self_info.name")
            or (cfg.repeater_display_name if role == "repeater" else cfg.companion_display_name)
        )
        pubkey_pre = (
            get_by_path(snapshot, "status.pubkey_pre")
            or get_by_path(snapshot, "self_telemetry.pubkey_pre")
        )

    # Status
    ts = snapshot.get("ts") if snapshot else None
    status_class, status_text = get_status(ts)

    # Last updated
    last_updated = None
    last_updated_iso = None
    if ts:
        dt = datetime.fromtimestamp(ts)
        last_updated = dt.strftime("%b %d, %Y at %H:%M UTC")
        last_updated_iso = dt.isoformat()

    # Build metrics for sidebar
    if role == "repeater":
        metrics_data = build_repeater_metrics(snapshot)
    else:
        metrics_data = build_companion_metrics(snapshot)

    # Node details
    node_details = build_node_details(role, snapshot)

    # Radio config
    radio_config = build_radio_config(snapshot)

    # Chart groups
    chart_groups = build_chart_groups(role, period, metrics)

    # Period config
    page_title, page_subtitle = PERIOD_CONFIG.get(period, ("Observations", "Radio telemetry"))
    if role == "companion":
        page_subtitle = page_subtitle.replace("Radio", "Companion node")

    # Meta description
    meta_descriptions = {
        "repeater": (
            "Live stats for MeshCore LoRa repeater in Oosterhout, NL. "
            "Battery, signal strength, packet counts, and uptime charts."
        ),
        "companion": (
            "Live stats for MeshCore companion node. "
            "Battery, contacts, packet counts, and uptime monitoring."
        ),
    }

    # CSS and link paths - depend on whether we're at root or in /companion/
    css_path = "/" if at_root else "../"
    base_path = "" if at_root else "/companion"

    return {
        # Page meta
        "title": f"{node_name} — {period.capitalize()}",
        "meta_description": meta_descriptions.get(role, "MeshCore mesh network statistics dashboard."),
        "og_image": None,
        "css_path": css_path,

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

        # Node details
        "node_details": node_details,
        "radio_config": radio_config,

        # Navigation
        "period": period,
        "base_path": base_path,
        "repeater_link": f"{css_path}day.html",
        "companion_link": f"{css_path}companion/day.html",
        "reports_link": f"{css_path}reports/",

        # Timestamps
        "last_updated": last_updated,
        "last_updated_iso": last_updated_iso,

        # Main content
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "chart_groups": chart_groups,
    }


def render_node_page(
    role: str,
    period: str,
    snapshot: Optional[dict],
    metrics: dict[str, str],
    at_root: bool = False,
) -> str:
    """Render a node page (companion or repeater)."""
    env = get_jinja_env()
    context = build_page_context(role, period, snapshot, metrics, at_root)
    template = env.get_template("node.html")
    return template.render(**context)


def copy_styles():
    """Copy styles.css to output directory."""
    cfg = get_config()
    # styles.css lives alongside templates in src/meshmon/templates/
    src = Path(__file__).parent / "templates" / "styles.css"
    dst = cfg.out_dir / "styles.css"

    if src.exists():
        shutil.copy2(src, dst)
        log.debug(f"Copied {src} to {dst}")
    else:
        log.warn(f"styles.css not found at {src}")


def write_site(
    companion_snapshot: Optional[dict],
    repeater_snapshot: Optional[dict],
) -> list[Path]:
    """
    Write all static site pages.

    Repeater pages are rendered at the site root (day.html, week.html, etc.).
    Companion pages are rendered under /companion/.

    Returns list of written paths.
    """
    cfg = get_config()
    written = []

    # Ensure output directories exist
    (cfg.out_dir / "companion").mkdir(parents=True, exist_ok=True)
    (cfg.out_dir / "assets" / "repeater").mkdir(parents=True, exist_ok=True)
    (cfg.out_dir / "assets" / "companion").mkdir(parents=True, exist_ok=True)

    # Copy styles.css
    copy_styles()

    # Repeater pages at root level
    for period in ["day", "week", "month", "year"]:
        page_path = cfg.out_dir / f"{period}.html"
        page_path.write_text(
            render_node_page("repeater", period, repeater_snapshot, cfg.repeater_metrics, at_root=True)
        )
        written.append(page_path)
        log.debug(f"Wrote {page_path}")

    # Companion pages under /companion/
    for period in ["day", "week", "month", "year"]:
        page_path = cfg.out_dir / "companion" / f"{period}.html"
        page_path.write_text(
            render_node_page("companion", period, companion_snapshot, cfg.companion_metrics)
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
    """Format a value with day number in <small> tag, for summary rows."""
    if value is None:
        return "-"
    day_str = f"{time_obj.day:02d}" if time_obj else ""
    if day_str:
        return f"{value:{fmt}} <small>{day_str}</small>"
    return f"{value:{fmt}}"


def build_monthly_table_data(
    agg: "MonthlyAggregate", role: str
) -> tuple[list[dict], list[dict], list[dict]]:
    """Build table column groups, headers and rows for a monthly report.

    Args:
        agg: Monthly aggregate data
        role: "companion" or "repeater"

    Returns:
        (col_groups, headers, rows) where each is a list of dicts
    """
    from .reports import MetricStats

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
            bat_v = m.get("bat_v", MetricStats())
            bat_pct = m.get("bat_pct", MetricStats())
            rssi = m.get("rssi", MetricStats())
            snr = m.get("snr", MetricStats())
            noise = m.get("noise", MetricStats())
            rx = m.get("rx", MetricStats())
            tx = m.get("tx", MetricStats())
            airtime = m.get("airtime", MetricStats())

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": f"{daily.date.day:02d}", "class": None},
                    {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                    {"value": _fmt_val_time(bat_v.min_value, bat_v.min_time), "class": "muted"},
                    {"value": _fmt_val_time(bat_v.max_value, bat_v.max_time), "class": "muted"},
                    {"value": f"{rssi.mean:.0f}" if rssi.mean else "-", "class": None},
                    {"value": f"{snr.mean:.1f}" if snr.mean else "-", "class": None},
                    {"value": f"{noise.mean:.0f}" if noise.mean else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
                    {"value": f"{airtime.total:,}" if airtime.total else "-", "class": None},
                ],
            })

        # Add summary row
        s = agg.summary
        bat_v = s.get("bat_v", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        rssi = s.get("rssi", MetricStats())
        snr = s.get("snr", MetricStats())
        noise = s.get("noise", MetricStats())
        rx = s.get("rx", MetricStats())
        tx = s.get("tx", MetricStats())
        airtime = s.get("airtime", MetricStats())

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "Avg", "class": None},
                {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                {"value": _fmt_val_day(bat_v.min_value, bat_v.min_time), "class": "muted"},
                {"value": _fmt_val_day(bat_v.max_value, bat_v.max_time), "class": "muted"},
                {"value": f"{rssi.mean:.0f}" if rssi.mean else "-", "class": None},
                {"value": f"{snr.mean:.1f}" if snr.mean else "-", "class": None},
                {"value": f"{noise.mean:.0f}" if noise.mean else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
                {"value": f"{airtime.total:,}" if airtime.total else "-", "class": None},
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
            bat_v = m.get("bat_v", MetricStats())
            bat_pct = m.get("bat_pct", MetricStats())
            contacts = m.get("contacts", MetricStats())
            rx = m.get("rx", MetricStats())
            tx = m.get("tx", MetricStats())

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": f"{daily.date.day:02d}", "class": None},
                    {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                    {"value": _fmt_val_time(bat_v.min_value, bat_v.min_time), "class": "muted"},
                    {"value": _fmt_val_time(bat_v.max_value, bat_v.max_time), "class": "muted"},
                    {"value": f"{contacts.mean:.0f}" if contacts.mean else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
                ],
            })

        # Summary row
        s = agg.summary
        bat_v = s.get("bat_v", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        contacts = s.get("contacts", MetricStats())
        rx = s.get("rx", MetricStats())
        tx = s.get("tx", MetricStats())

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "Avg", "class": None},
                {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                {"value": _fmt_val_day(bat_v.min_value, bat_v.min_time), "class": "muted"},
                {"value": _fmt_val_day(bat_v.max_value, bat_v.max_time), "class": "muted"},
                {"value": f"{contacts.mean:.0f}" if contacts.mean else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
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
    agg: "YearlyAggregate", role: str
) -> tuple[list[dict], list[dict], list[dict]]:
    """Build table column groups, headers and rows for a yearly report.

    Args:
        agg: Yearly aggregate data
        role: "companion" or "repeater"

    Returns:
        (col_groups, headers, rows) where each is a list of dicts
    """
    from .reports import MetricStats

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
            bat_v = s.get("bat_v", MetricStats())
            bat_pct = s.get("bat_pct", MetricStats())
            rssi = s.get("rssi", MetricStats())
            snr = s.get("snr", MetricStats())
            rx = s.get("rx", MetricStats())
            tx = s.get("tx", MetricStats())

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": str(agg.year), "class": None},
                    {"value": f"{monthly.month:02d}", "class": None},
                    {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                    {"value": _fmt_val_day(bat_v.max_value, bat_v.max_time), "class": "muted"},
                    {"value": _fmt_val_day(bat_v.min_value, bat_v.min_time), "class": "muted"},
                    {"value": f"{rssi.mean:.0f}" if rssi.mean else "-", "class": None},
                    {"value": f"{snr.mean:.1f}" if snr.mean else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
                ],
            })

        # Summary row
        s = agg.summary
        bat_v = s.get("bat_v", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        rssi = s.get("rssi", MetricStats())
        snr = s.get("snr", MetricStats())
        rx = s.get("rx", MetricStats())
        tx = s.get("tx", MetricStats())

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "", "class": None},
                {"value": "Avg", "class": None},
                {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                {"value": _fmt_val_month(bat_v.max_value, bat_v.max_time), "class": "muted"},
                {"value": _fmt_val_month(bat_v.min_value, bat_v.min_time), "class": "muted"},
                {"value": f"{rssi.mean:.0f}" if rssi.mean else "-", "class": None},
                {"value": f"{snr.mean:.1f}" if snr.mean else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
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
            bat_v = s.get("bat_v", MetricStats())
            bat_pct = s.get("bat_pct", MetricStats())
            contacts = s.get("contacts", MetricStats())
            rx = s.get("rx", MetricStats())
            tx = s.get("tx", MetricStats())

            rows.append({
                "is_summary": False,
                "cells": [
                    {"value": str(agg.year), "class": None},
                    {"value": f"{monthly.month:02d}", "class": None},
                    {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                    {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                    {"value": _fmt_val_day(bat_v.max_value, bat_v.max_time), "class": "muted"},
                    {"value": _fmt_val_day(bat_v.min_value, bat_v.min_time), "class": "muted"},
                    {"value": f"{contacts.mean:.0f}" if contacts.mean else "-", "class": None},
                    {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                    {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
                ],
            })

        # Summary row
        s = agg.summary
        bat_v = s.get("bat_v", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        contacts = s.get("contacts", MetricStats())
        rx = s.get("rx", MetricStats())
        tx = s.get("tx", MetricStats())

        rows.append({
            "is_summary": True,
            "cells": [
                {"value": "", "class": None},
                {"value": "Avg", "class": None},
                {"value": f"{bat_v.mean:.2f}" if bat_v.mean else "-", "class": None},
                {"value": f"{bat_pct.mean:.0f}" if bat_pct.mean else "-", "class": None},
                {"value": _fmt_val_month(bat_v.max_value, bat_v.max_time), "class": "muted"},
                {"value": _fmt_val_month(bat_v.min_value, bat_v.min_time), "class": "muted"},
                {"value": f"{contacts.mean:.0f}" if contacts.mean else "-", "class": None},
                {"value": f"{rx.total:,}" if rx.total else "-", "class": "highlight"},
                {"value": f"{tx.total:,}" if tx.total else "-", "class": None},
            ],
        })

    return col_groups, headers, rows


def render_report_page(
    agg: Any,
    node_name: str,
    report_type: str,
    prev_report: Optional[dict] = None,
    next_report: Optional[dict] = None,
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
    }

    template = env.get_template("report.html")
    return template.render(**context)


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
        "repeater": f"{cfg.repeater_display_name} — Solar-powered remote node in Oosterhout, NL",
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
    }

    template = env.get_template("report_index.html")
    return template.render(**context)
