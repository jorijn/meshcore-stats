"""HTML rendering helpers using Jinja2 templates."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, BaseLoader

from .env import get_config
from .extract import get_by_path
from . import log


# Base HTML template
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - MeshCore Stats</title>
    <style>
        :root {
            --bg: #f5f5f5;
            --card-bg: #ffffff;
            --text: #333333;
            --text-muted: #666666;
            --border: #dddddd;
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
        }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
            padding: 1rem;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        header {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
        }
        header h1 { font-size: 1.5rem; margin-bottom: 0.5rem; }
        header .meta { color: var(--text-muted); font-size: 0.875rem; }
        nav {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 0.75rem 1rem;
            margin-bottom: 1rem;
            display: flex;
            gap: 0.5rem;
            flex-wrap: wrap;
        }
        nav a {
            color: var(--primary);
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            background: var(--bg);
            border: 1px solid var(--border);
        }
        nav a:hover { background: var(--primary); color: white; }
        nav a.active { background: var(--primary); color: white; }
        .tabs {
            display: flex;
            gap: 0.25rem;
            margin-bottom: 1rem;
        }
        .tabs a {
            padding: 0.5rem 1rem;
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 4px 4px 0 0;
            text-decoration: none;
            color: var(--text);
        }
        .tabs a.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        .card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem 1.5rem;
            margin-bottom: 1rem;
        }
        .card h2 { font-size: 1.125rem; margin-bottom: 1rem; color: var(--text); }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th, td {
            text-align: left;
            padding: 0.5rem;
            border-bottom: 1px solid var(--border);
        }
        th { font-weight: 600; color: var(--text-muted); }
        .charts {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 1rem;
        }
        @media (max-width: 900px) {
            .charts {
                grid-template-columns: 1fr;
            }
        }
        .chart-card {
            background: var(--card-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 1rem;
        }
        .chart-card h3 { font-size: 0.875rem; margin-bottom: 0.5rem; color: var(--text-muted); }
        .chart-card img { max-width: 100%; height: auto; }
        footer {
            text-align: center;
            padding: 1rem;
            color: var(--text-muted);
            font-size: 0.875rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{{ node_name }}{% if pubkey_pre %} <code style="font-size: 0.75rem; color: var(--text-muted);">[{{ pubkey_pre }}]</code>{% endif %}</h1>
            <div class="meta">
                {% if last_updated %}Last updated: {{ last_updated }}{% endif %}
            </div>
        </header>
        <nav>
            <a href="/day.html" {% if role == 'repeater' %}class="active"{% endif %}>Repeater</a>
            <a href="/companion/day.html" {% if role == 'companion' %}class="active"{% endif %}>Companion</a>
        </nav>
        {% block content %}{% endblock %}
        <footer>
            MeshCore Stats &middot; Generated {{ generated_at }}
        </footer>
    </div>
</body>
</html>
"""

NODE_TEMPLATE = """
{% extends "base" %}
{% block content %}
<div class="tabs">
    <a href="{{ base_path }}/day.html" {% if period == 'day' %}class="active"{% endif %}>Day</a>
    <a href="{{ base_path }}/week.html" {% if period == 'week' %}class="active"{% endif %}>Week</a>
    <a href="{{ base_path }}/month.html" {% if period == 'month' %}class="active"{% endif %}>Month</a>
    <a href="{{ base_path }}/year.html" {% if period == 'year' %}class="active"{% endif %}>Year</a>
</div>

{% if about %}
<div class="card">
    <h2>About this Node</h2>
    <p style="color: var(--text-muted); line-height: 1.8;">{{ about }}</p>
</div>
{% endif %}

{% if snapshot %}
<div class="card">
    <h2>Latest Snapshot</h2>
    <table>
        {% for key, value in snapshot_table %}
        <tr>
            <th>{{ key }}</th>
            <td>{{ value }}</td>
        </tr>
        {% endfor %}
    </table>
</div>
{% endif %}

<div class="card">
    <h2>Charts - {{ period | capitalize }}</h2>
    <div class="charts">
        {% for chart in charts %}
        <div class="chart-card">
            <h3>{{ chart.label }}</h3>
            <img src="{{ chart.src }}" alt="{{ chart.label }}">
        </div>
        {% endfor %}
    </div>
</div>
{% endblock %}
"""


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


def create_jinja_env() -> Environment:
    """Create Jinja2 environment with templates."""
    env = Environment(loader=BaseLoader())

    # Add filters
    env.filters["format_time"] = format_time
    env.filters["format_value"] = format_value

    # Pre-compile templates
    env.globals["base_template"] = env.from_string(BASE_TEMPLATE)

    return env


def extract_snapshot_table(snapshot: dict, role: str) -> list[tuple[str, str]]:
    """
    Extract key-value pairs from snapshot for display.

    Returns list of (label, formatted_value) tuples.
    """
    table = []

    # Timestamp
    ts = snapshot.get("ts")
    if ts:
        table.append(("Timestamp", format_time(ts)))

    if role == "companion":
        # Battery (from stats.core.battery_mv in millivolts)
        bat_mv = get_by_path(snapshot, "stats.core.battery_mv")
        if bat_mv is not None:
            bat_v = bat_mv / 1000.0
            table.append(("Battery Voltage", f"{format_value(bat_v)} V"))

        # Contacts
        contacts_count = get_by_path(snapshot, "derived.contacts_count")
        if contacts_count is not None:
            table.append(("Contacts", str(contacts_count)))

        # Packets (from stats.packets.recv/sent)
        rx = get_by_path(snapshot, "stats.packets.recv")
        if rx is not None:
            table.append(("RX Packets", format_number(rx)))

        tx = get_by_path(snapshot, "stats.packets.sent")
        if tx is not None:
            table.append(("TX Packets", format_number(tx)))

        # Radio info (from self_info)
        freq = get_by_path(snapshot, "self_info.radio_freq")
        if freq is not None:
            table.append(("Frequency", f"{format_value(freq)} MHz"))

        sf = get_by_path(snapshot, "self_info.radio_sf")
        if sf is not None:
            table.append(("Spreading Factor", str(sf)))

        bw = get_by_path(snapshot, "self_info.radio_bw")
        if bw is not None:
            table.append(("Bandwidth", f"{format_value(bw)} kHz"))

        tx_power = get_by_path(snapshot, "self_info.tx_power")
        if tx_power is not None:
            table.append(("TX Power", f"{tx_power} dBm"))

        # Uptime
        uptime = get_by_path(snapshot, "stats.core.uptime_secs")
        if uptime is not None:
            table.append(("Uptime", format_uptime(uptime)))

    elif role == "repeater":
        # Battery - status.bat is in millivolts
        bat_mv = get_by_path(snapshot, "status.bat")
        if bat_mv is not None:
            bat_v = bat_mv / 1000.0
            table.append(("Battery Voltage", f"{format_value(bat_v)} V"))

        # Also check telemetry array for voltage channel
        telemetry = snapshot.get("telemetry")
        if isinstance(telemetry, list):
            for item in telemetry:
                if isinstance(item, dict) and item.get("type") == "voltage":
                    table.append(("Battery (telemetry)", f"{format_value(item.get('value'))} V"))
                    break

        # Neighbours
        neigh = get_by_path(snapshot, "derived.neighbours_count")
        if neigh is not None:
            table.append(("Neighbours", str(neigh)))

        # Radio stats - actual field names from status
        rssi = get_by_path(snapshot, "status.last_rssi")
        if rssi is not None:
            table.append(("RSSI", f"{rssi} dBm"))

        snr = get_by_path(snapshot, "status.last_snr")
        if snr is not None:
            table.append(("SNR", f"{format_value(snr)} dB"))

        noise = get_by_path(snapshot, "status.noise_floor")
        if noise is not None:
            table.append(("Noise Floor", f"{noise} dBm"))

        # Packets - from status, not telemetry
        rx = get_by_path(snapshot, "status.nb_recv")
        if rx is not None:
            table.append(("RX Packets", format_number(rx)))

        tx = get_by_path(snapshot, "status.nb_sent")
        if tx is not None:
            table.append(("TX Packets", format_number(tx)))

        # Uptime
        uptime = get_by_path(snapshot, "status.uptime")
        if uptime is not None:
            table.append(("Uptime", format_uptime(uptime)))

        # Airtime
        airtime = get_by_path(snapshot, "status.airtime")
        if airtime is not None:
            table.append(("TX Airtime", format_duration(airtime)))

        # Skip reason
        skip = get_by_path(snapshot, "skip_reason")
        if skip:
            table.append(("Status", f"Skipped: {skip}"))

    return table


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
    env = create_jinja_env()
    cfg = get_config()

    # Build chart list - assets always in /assets/{role}/
    charts = []
    chart_labels = {
        "bat_v": "Battery Voltage",
        "bat_pct": "Battery %",
        "contacts": "Contacts Count",
        "neigh": "Neighbours Count",
        "rx": "RX Packets",
        "tx": "TX Packets",
        "rssi": "RSSI",
        "snr": "SNR",
        "uptime": "Uptime",
    }

    for ds_name in sorted(metrics.keys()):
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
        # Try different paths for node name depending on role
        node_name = (
            get_by_path(snapshot, "node.name")
            or get_by_path(snapshot, "self_info.name")
            or role.capitalize()
        )
        # Pubkey prefix location differs by role
        pubkey_pre = (
            get_by_path(snapshot, "status.pubkey_pre")
            or get_by_path(snapshot, "self_telemetry.pubkey_pre")
        )

    # About text for each node type
    about_text = {
        "repeater": (
            "This is a MeshCore LoRa mesh repeater located in Oosterhout, The Netherlands. "
            "The hardware is a Seeed SenseCAP Solar Node P1-Pro running MeshCore firmware. "
            "It operates on the EU868 frequency band and relays messages across the mesh network. "
            "Stats are collected every 15 minutes via LoRa from a local companion node, "
            "stored in RRD databases, and rendered into these charts."
        ),
        "companion": (
            "This is the local MeshCore companion node connected via USB serial to the monitoring system. "
            "It serves as the gateway to communicate with remote nodes over LoRa. "
            "Stats are collected every minute directly from the device."
        ),
    }

    # Base path for tab links: root pages use "", others use "/role"
    base_path = "" if at_root else f"/{role}"

    # Create combined template
    full_template = BASE_TEMPLATE.replace(
        "{% block content %}{% endblock %}",
        NODE_TEMPLATE.replace("{% extends \"base\" %}\n{% block content %}", "").replace("{% endblock %}", "")
    )

    template = env.from_string(full_template)
    return template.render(
        title=f"{role.capitalize()} - {period.capitalize()}",
        node_name=node_name,
        pubkey_pre=pubkey_pre,
        role=role,
        period=period,
        base_path=base_path,
        about=about_text.get(role),
        last_updated=last_updated,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        snapshot=snapshot,
        snapshot_table=snapshot_table,
        charts=charts,
    )


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
