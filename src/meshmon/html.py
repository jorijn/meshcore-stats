"""HTML rendering helpers using Jinja2 templates."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, PackageLoader, select_autoescape

from .env import get_config
from .extract import get_by_path
from .battery import voltage_to_percentage
from .snapshot_config import extract_snapshot_table
from . import log


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


def format_time(ts: Optional[int]) -> str:
    """Format Unix timestamp to human readable string."""
    if ts is None:
        return "N/A"
    try:
        dt = datetime.fromtimestamp(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError):
        return "N/A"


def format_value(value: Any) -> str:
    """Format a value for display."""
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def format_number(value: int) -> str:
    """Format an integer with thousands separators."""
    if value is None:
        return "N/A"
    return f"{value:,}"


def format_duration(seconds: int) -> str:
    """Format duration in seconds to human readable string (days, hours, minutes, seconds)."""
    if seconds is None:
        return "N/A"

    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60
    secs = seconds % 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    if mins > 0 or hours > 0 or days > 0:
        parts.append(f"{mins}m")
    parts.append(f"{secs}s")

    return " ".join(parts)


def format_uptime(seconds: int) -> str:
    """Format uptime seconds to human readable string (days, hours, minutes)."""
    days = seconds // 86400
    hours = (seconds % 86400) // 3600
    mins = (seconds % 3600) // 60

    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0 or days > 0:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")

    return " ".join(parts)




def build_page_context(
    role: str,
    period: str,
    snapshot: Optional[dict],
    metrics: dict[str, str],
    at_root: bool,
) -> dict[str, Any]:
    """Build template context dictionary.

    Extracted from render_node_page() for clarity.

    Args:
        role: "companion" or "repeater"
        period: "day", "week", "month", or "year"
        snapshot: Latest snapshot data
        metrics: Dict of metric mappings
        at_root: If True, page is rendered at site root (for repeater)

    Returns:
        Dictionary of template context variables
    """
    cfg = get_config()

    # Build chart list - assets always in /assets/{role}/
    charts = []
    chart_labels = {
        "bat_v": "Battery Voltage",
        "bat_pct": "Battery Percentage",
        "contacts": "Known Contacts",
        "neigh": "Neighbours",
        "rx": "Packets Received",
        "tx": "Packets Transmitted",
        "rssi": "Signal Strength (RSSI)",
        "snr": "Signal-to-Noise Ratio",
        "uptime": "Uptime",
        "noise": "Noise Floor",
        "airtime": "Transmit Airtime",
        "rx_air": "Receive Airtime",
        "fl_dups": "Duplicate Flood Packets",
        "di_dups": "Duplicate Direct Packets",
        "fl_tx": "Flood Packets Sent",
        "fl_rx": "Flood Packets Received",
        "di_tx": "Direct Packets Sent",
        "di_rx": "Direct Packets Received",
        "txq": "Transmit Queue Depth",
    }

    # Chart display order: most important first
    chart_order = [
        "bat_v", "bat_pct", "uptime",
        "rssi", "snr", "noise",
        "rx", "tx",
        "airtime", "rx_air",
        "fl_rx", "fl_tx", "di_rx", "di_tx",
        "fl_dups", "di_dups", "txq",
        "contacts", "neigh",
    ]

    def chart_sort_key(ds_name: str) -> tuple:
        """Sort by priority order, then alphabetically for unlisted metrics."""
        try:
            return (0, chart_order.index(ds_name))
        except ValueError:
            return (1, ds_name)

    for ds_name in sorted(metrics.keys(), key=chart_sort_key):
        chart_path = cfg.out_dir / "assets" / role / f"{ds_name}_{period}.png"
        if chart_path.exists():
            charts.append({
                "label": chart_labels.get(ds_name, ds_name),
                "src": f"/assets/{role}/{ds_name}_{period}.png",
            })

    # Extract snapshot table
    snapshot_table = []
    if snapshot:
        snapshot_table = extract_snapshot_table(snapshot, role)

    # Get last updated time
    last_updated = None
    if snapshot and snapshot.get("ts"):
        last_updated = format_time(snapshot["ts"])

    # Extract node name and pubkey prefix
    node_name = role.capitalize()
    pubkey_pre = None
    if snapshot:
        node_name = (
            get_by_path(snapshot, "node.name")
            or get_by_path(snapshot, "self_info.name")
            or role.capitalize()
        )
        pubkey_pre = (
            get_by_path(snapshot, "status.pubkey_pre")
            or get_by_path(snapshot, "self_telemetry.pubkey_pre")
        )

    # About text for each node type (HTML allowed)
    about_text = {
        "repeater": (
            "This is a MeshCore LoRa mesh repeater located in <strong>Oosterhout, The Netherlands</strong>. "
            "The hardware is a <strong>Seeed SenseCAP Solar Node P1-Pro</strong> running MeshCore firmware. "
            "It operates on the <strong>MeshCore EU/UK Narrow</strong> preset "
            "(869.618 MHz, 62.5 kHz bandwidth, SF8, CR8) and relays messages across the mesh network. "
            "<br><br>Stats are collected every 15 minutes via LoRa from a local companion node, "
            "stored in RRD databases, and rendered into these charts."
        ),
        "companion": (
            "This is the local MeshCore companion node connected via USB serial to the monitoring system. "
            "It serves as the gateway to communicate with remote nodes over LoRa. "
            "Stats are collected every minute directly from the device."
        ),
    }

    # Calculate status indicator based on last update time
    status_class = "offline"
    status_text = "No data"
    if snapshot and snapshot.get("ts"):
        age_seconds = int(datetime.now().timestamp()) - snapshot["ts"]
        if age_seconds < 1800:  # 30 minutes
            status_class = "online"
            status_text = "Online"
        elif age_seconds < 7200:  # 2 hours
            status_class = "stale"
            status_text = "Stale data"
        else:
            status_class = "offline"
            status_text = "Offline"

    # Build metrics bar with key values
    metrics_bar = []
    if snapshot:
        if role == "repeater":
            bat_mv = get_by_path(snapshot, "status.bat")
            if bat_mv is not None:
                bat_pct = voltage_to_percentage(bat_mv / 1000)
                metrics_bar.append({"value": f"{bat_pct:.0f}%", "label": "Battery"})
            uptime = get_by_path(snapshot, "status.uptime")
            if uptime is not None:
                metrics_bar.append({"value": format_uptime(uptime), "label": "Uptime"})
            rssi = get_by_path(snapshot, "status.last_rssi")
            if rssi is not None:
                metrics_bar.append({"value": f"{rssi} dBm", "label": "RSSI"})
            snr = get_by_path(snapshot, "status.last_snr")
            if snr is not None:
                metrics_bar.append({"value": f"{snr:.1f} dB", "label": "SNR"})
        elif role == "companion":
            bat_mv = get_by_path(snapshot, "stats.core.battery_mv")
            if bat_mv is not None:
                bat_pct = voltage_to_percentage(bat_mv / 1000)
                metrics_bar.append({"value": f"{bat_pct:.0f}%", "label": "Battery"})
            uptime = get_by_path(snapshot, "stats.core.uptime_secs")
            if uptime is not None:
                metrics_bar.append({"value": format_uptime(uptime), "label": "Uptime"})
            contacts = get_by_path(snapshot, "derived.contacts_count")
            if contacts is not None:
                metrics_bar.append({"value": str(contacts), "label": "Contacts"})
            rx = get_by_path(snapshot, "stats.packets.recv")
            if rx is not None:
                metrics_bar.append({"value": f"{rx:,}", "label": "RX Packets"})

    # Base path for tab links
    base_path = "" if at_root else f"/{role}"

    # Meta description for social sharing
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

    return {
        "title": f"{node_name} - {period.capitalize()}",
        "meta_description": meta_descriptions.get(role, "MeshCore mesh network statistics dashboard."),
        "og_image": None,  # Optional, can be added later
        "node_name": node_name,
        "pubkey_pre": pubkey_pre,
        "status_class": status_class,
        "status_text": status_text,
        "role": role,
        "period": period,
        "base_path": base_path,
        "about": about_text.get(role),
        "last_updated": last_updated,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "snapshot": snapshot,
        "snapshot_table": snapshot_table,
        "metrics_bar": metrics_bar,
        "charts": charts,
    }


def render_node_page(
    role: str,
    period: str,
    snapshot: Optional[dict],
    metrics: dict[str, str],
    at_root: bool = False,
) -> str:
    """Render a node page (companion or repeater).

    Args:
        role: "companion" or "repeater"
        period: "day", "week", "month", or "year"
        snapshot: Latest snapshot data
        metrics: Dict of metric mappings
        at_root: If True, page is rendered at site root (for repeater)
    """
    env = get_jinja_env()
    context = build_page_context(role, period, snapshot, metrics, at_root)
    template = env.get_template("node.html")
    return template.render(**context)


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
