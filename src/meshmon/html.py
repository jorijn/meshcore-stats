"""HTML rendering helpers using Jinja2 templates."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, BaseLoader

from .env import get_config
from .extract import get_by_path
from .battery import voltage_to_percentage
from . import log


# Base HTML template
BASE_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - MeshCore Stats</title>
    <meta name="description" content="{{ meta_description }}">

    <!-- Open Graph -->
    <meta property="og:type" content="website">
    <meta property="og:title" content="{{ title }} - MeshCore Stats">
    <meta property="og:description" content="{{ meta_description }}">
    <meta property="og:site_name" content="MeshCore Stats">
    {% if og_image %}<meta property="og:image" content="{{ og_image }}">{% endif %}

    <!-- Twitter Card -->
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{{ title }} - MeshCore Stats">
    <meta name="twitter:description" content="{{ meta_description }}">
    {% if og_image %}<meta name="twitter:image" content="{{ og_image }}">{% endif %}

    <style>
        :root {
            /* Typography */
            --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            --font-mono: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace;
            --font-size-xs: 0.75rem;
            --font-size-sm: 0.875rem;
            --font-size-base: 1rem;
            --font-size-lg: 1.125rem;
            --font-size-xl: 1.25rem;
            --font-size-2xl: 1.5rem;

            /* Spacing */
            --space-1: 0.25rem;
            --space-2: 0.5rem;
            --space-3: 0.75rem;
            --space-4: 1rem;
            --space-5: 1.25rem;
            --space-6: 1.5rem;
            --space-8: 2rem;

            /* Colors */
            --bg: #f8fafc;
            --bg-elevated: #ffffff;
            --bg-sunken: #f1f5f9;
            --text: #1e293b;
            --text-muted: #64748b;
            --text-subtle: #94a3b8;
            --border: #e2e8f0;
            --border-strong: #cbd5e1;

            /* Brand */
            --primary: #2563eb;
            --primary-hover: #1d4ed8;
            --primary-light: #dbeafe;

            /* Semantic */
            --success: #16a34a;
            --success-light: #dcfce7;
            --warning: #ca8a04;
            --warning-light: #fef9c3;
            --danger: #dc2626;
            --danger-light: #fee2e2;

            /* Effects */
            --shadow-sm: 0 1px 2px 0 rgb(0 0 0 / 0.05);
            --shadow: 0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1);
            --radius: 8px;
            --radius-lg: 12px;
        }

        * { box-sizing: border-box; margin: 0; padding: 0; }

        body {
            font-family: var(--font-sans);
            font-size: var(--font-size-base);
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            min-height: 100vh;
        }

        /* Skip link for accessibility */
        .skip-link {
            position: absolute;
            top: -40px;
            left: var(--space-4);
            background: var(--primary);
            color: white;
            padding: var(--space-2) var(--space-4);
            border-radius: var(--radius);
            z-index: 1000;
            text-decoration: none;
            font-weight: 500;
        }
        .skip-link:focus { top: var(--space-4); }

        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: var(--space-4);
        }

        /* Header */
        .site-header {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: var(--space-4) var(--space-6);
            margin-bottom: var(--space-4);
            box-shadow: var(--shadow-sm);
            display: grid;
            grid-template-columns: auto 1fr auto;
            align-items: center;
            gap: var(--space-6);
        }
        .header-brand {
            font-size: var(--font-size-sm);
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .header-node {
            display: flex;
            align-items: center;
            gap: var(--space-3);
            flex-wrap: wrap;
        }
        .header-node h1 {
            font-size: var(--font-size-xl);
            font-weight: 600;
            margin: 0;
        }
        .pubkey {
            font-family: var(--font-mono);
            font-size: var(--font-size-xs);
            color: var(--text-muted);
            background: var(--bg-sunken);
            padding: var(--space-1) var(--space-2);
            border-radius: 4px;
        }
        .status-indicator {
            width: 10px;
            height: 10px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .status-online { background: var(--success); box-shadow: 0 0 0 3px var(--success-light); }
        .status-stale { background: var(--warning); box-shadow: 0 0 0 3px var(--warning-light); }
        .status-offline { background: var(--danger); box-shadow: 0 0 0 3px var(--danger-light); }
        .header-updated {
            text-align: right;
            font-size: var(--font-size-sm);
            color: var(--text-muted);
        }
        .header-updated .label { display: block; font-size: var(--font-size-xs); color: var(--text-subtle); }

        /* Navigation */
        .main-nav {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: var(--space-3) var(--space-4);
            margin-bottom: var(--space-6);
            box-shadow: var(--shadow-sm);
            display: flex;
            align-items: center;
            gap: var(--space-2);
            flex-wrap: wrap;
        }
        .nav-group {
            display: flex;
            gap: var(--space-1);
        }
        .nav-separator {
            color: var(--border-strong);
            padding: 0 var(--space-2);
            user-select: none;
        }
        .nav-link {
            display: inline-flex;
            align-items: center;
            padding: var(--space-2) var(--space-4);
            border-radius: var(--radius);
            text-decoration: none;
            font-size: var(--font-size-sm);
            font-weight: 500;
            color: var(--text-muted);
            background: transparent;
            border: 1px solid transparent;
            transition: all 0.15s ease;
            min-height: 44px;
        }
        .nav-link:hover {
            color: var(--text);
            background: var(--bg-sunken);
        }
        .nav-link.active {
            color: var(--primary);
            background: var(--primary-light);
            border-color: var(--primary);
        }

        /* Focus styles */
        :focus-visible {
            outline: 2px solid var(--primary);
            outline-offset: 2px;
        }

        /* Metrics Bar */
        .metrics-bar {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
            gap: var(--space-4);
            margin-bottom: var(--space-6);
        }
        .metric {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            padding: var(--space-4) var(--space-5);
            text-align: center;
            box-shadow: var(--shadow-sm);
        }
        .metric-value {
            display: block;
            font-size: var(--font-size-2xl);
            font-weight: 700;
            color: var(--text);
            font-variant-numeric: tabular-nums;
        }
        .metric-label {
            display: block;
            font-size: var(--font-size-xs);
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-top: var(--space-1);
        }

        /* Dashboard Grid */
        .dashboard-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: var(--space-6);
            margin-bottom: var(--space-6);
        }

        /* Cards */
        .card {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            box-shadow: var(--shadow-sm);
            overflow: hidden;
        }
        .card-header {
            padding: var(--space-4) var(--space-6);
            border-bottom: 1px solid var(--border);
            background: var(--bg-sunken);
        }
        .card-title {
            font-size: var(--font-size-sm);
            font-weight: 600;
            color: var(--text);
            text-transform: uppercase;
            letter-spacing: 0.025em;
            margin: 0;
        }
        .card-body { padding: var(--space-5) var(--space-6); }
        .card-body p { color: var(--text-muted); line-height: 1.7; }

        /* Snapshot Table */
        .snapshot-table { width: 100%; border-collapse: collapse; }
        .snapshot-table tbody tr { border-bottom: 1px solid var(--border); }
        .snapshot-table tbody tr:last-child { border-bottom: none; }
        .snapshot-table th, .snapshot-table td { padding: var(--space-3) var(--space-2); }
        .snapshot-table th {
            text-align: left;
            font-size: var(--font-size-sm);
            font-weight: 500;
            color: var(--text-muted);
            width: 45%;
        }
        .snapshot-table td {
            text-align: right;
            font-size: var(--font-size-base);
            font-weight: 600;
            font-variant-numeric: tabular-nums;
            color: var(--text);
        }
        /* Tooltips - work on hover (desktop) and tap/focus (mobile) */
        .tooltip-trigger {
            cursor: help;
            border-bottom: 1px dotted var(--text-subtle);
            position: relative;
            display: inline-block;
        }
        .tooltip-trigger::after {
            content: attr(data-tooltip);
            position: absolute;
            left: 0;
            top: 100%;
            margin-top: var(--space-1);
            background: var(--text);
            color: white;
            padding: var(--space-2) var(--space-3);
            border-radius: var(--radius);
            font-size: var(--font-size-xs);
            font-weight: 400;
            white-space: normal;
            width: max-content;
            max-width: 250px;
            z-index: 100;
            opacity: 0;
            visibility: hidden;
            transition: opacity 0.15s ease, visibility 0.15s ease;
            pointer-events: none;
            box-shadow: var(--shadow);
            line-height: 1.4;
        }
        .tooltip-trigger:hover::after,
        .tooltip-trigger:focus::after {
            opacity: 1;
            visibility: visible;
        }
        .tooltip-trigger:focus {
            outline: none;
            border-bottom-color: var(--primary);
        }

        /* Charts */
        .charts-section { margin-bottom: var(--space-6); }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: var(--space-4);
        }
        .chart-card {
            background: var(--bg-elevated);
            border: 1px solid var(--border);
            border-radius: var(--radius-lg);
            overflow: hidden;
            box-shadow: var(--shadow-sm);
        }
        .chart-header {
            padding: var(--space-3) var(--space-4);
            background: var(--bg-sunken);
            border-bottom: 1px solid var(--border);
        }
        .chart-title {
            font-size: var(--font-size-sm);
            font-weight: 600;
            color: var(--text);
            margin: 0;
        }
        .chart-body { padding: var(--space-3); }
        .chart-body img {
            max-width: 100%;
            height: auto;
            display: block;
            border-radius: 4px;
        }

        /* Footer */
        .site-footer {
            margin-top: var(--space-8);
            padding: var(--space-5) var(--space-4);
            text-align: center;
            border-top: 1px solid var(--border);
        }
        .footer-contact-list {
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: var(--space-2) var(--space-4);
            list-style: none;
            padding: 0;
            margin: 0;
        }
        .footer-contact-link {
            display: inline-flex;
            align-items: center;
            gap: var(--space-2);
            padding: var(--space-2) var(--space-3);
            font-size: var(--font-size-sm);
            color: var(--text-muted);
            text-decoration: none;
            border-radius: var(--radius);
            transition: color 0.15s ease, background-color 0.15s ease;
            min-height: 44px;
            min-width: 44px;
        }
        .footer-contact-link:hover,
        .footer-contact-link:focus {
            color: var(--primary);
            background-color: var(--primary-light);
        }
        .footer-contact-link svg {
            width: 18px;
            height: 18px;
            flex-shrink: 0;
            fill: currentColor;
        }

        /* Responsive */
        @media (max-width: 900px) {
            .site-header {
                grid-template-columns: 1fr;
                text-align: center;
                gap: var(--space-3);
            }
            .header-node { justify-content: center; }
            .header-updated { text-align: center; }
            .dashboard-grid { grid-template-columns: 1fr; }
            .charts-grid { grid-template-columns: 1fr; }
        }

        @media (max-width: 600px) {
            html { font-size: 14px; }
            .container { padding: var(--space-3); }
            .main-nav {
                flex-direction: column;
                align-items: stretch;
            }
            .nav-group {
                overflow-x: auto;
                -webkit-overflow-scrolling: touch;
                padding-bottom: var(--space-1);
            }
            .nav-separator { display: none; }
            .metrics-bar { grid-template-columns: repeat(2, 1fr); }
            .card-body { padding: var(--space-4); }
            .snapshot-table th, .snapshot-table td {
                display: block;
                width: 100%;
                text-align: left;
                padding: var(--space-1) 0;
            }
            .snapshot-table th {
                font-size: var(--font-size-xs);
                padding-top: var(--space-3);
            }
            .snapshot-table td {
                font-size: var(--font-size-lg);
                padding-bottom: var(--space-3);
                border-bottom: 1px solid var(--border);
            }
            .snapshot-table tbody tr { border-bottom: none; }
            .snapshot-table tbody tr:last-child td { border-bottom: none; }
        }
    </style>
</head>
<body>
    <a href="#main-content" class="skip-link">Skip to main content</a>
    <div class="container">
        <header class="site-header">
            <div class="header-brand">MeshCore Stats</div>
            <div class="header-node">
                <h1>{{ node_name }}</h1>
                {% if pubkey_pre %}<code class="pubkey">{{ pubkey_pre }}</code>{% endif %}
                <span class="status-indicator status-{{ status_class }}" title="{{ status_text }}"></span>
            </div>
            <div class="header-updated">
                <span class="label">Last updated</span>
                {% if last_updated %}{{ last_updated }}{% else %}N/A{% endif %}
            </div>
        </header>

        <nav class="main-nav" aria-label="Main navigation">
            <div class="nav-group" aria-label="Node selection">
                <a href="/day.html" class="nav-link{% if role == 'repeater' %} active{% endif %}"{% if role == 'repeater' %} aria-current="page"{% endif %}>Repeater</a>
                <a href="/companion/day.html" class="nav-link{% if role == 'companion' %} active{% endif %}"{% if role == 'companion' %} aria-current="page"{% endif %}>Companion</a>
            </div>
            <span class="nav-separator" aria-hidden="true">|</span>
            <div class="nav-group" aria-label="Time period">
                <a href="{{ base_path }}/day.html" class="nav-link{% if period == 'day' %} active{% endif %}">Day</a>
                <a href="{{ base_path }}/week.html" class="nav-link{% if period == 'week' %} active{% endif %}">Week</a>
                <a href="{{ base_path }}/month.html" class="nav-link{% if period == 'month' %} active{% endif %}">Month</a>
                <a href="{{ base_path }}/year.html" class="nav-link{% if period == 'year' %} active{% endif %}">Year</a>
            </div>
        </nav>

        <main id="main-content">
        {% block content %}{% endblock %}
        </main>

        <footer class="site-footer">
            <nav class="footer-contact" aria-label="Contact links">
                <ul class="footer-contact-list">
                    <li>
                        <a href="mailto:jorijn@jorijn.com" class="footer-contact-link" aria-label="Send email to jorijn@jorijn.com">
                            <svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M20 4H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6c0-1.1-.9-2-2-2zm0 4-8 5-8-5V6l8 5 8-5v2z"/></svg>
                            <span>Email</span>
                        </a>
                    </li>
                    <li>
                        <a href="https://github.com/jorijn" class="footer-contact-link" rel="noopener" target="_blank" aria-label="GitHub profile (opens in new tab)">
                            <svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.477 2 2 6.477 2 12c0 4.42 2.865 8.17 6.839 9.49.5.092.682-.217.682-.482 0-.237-.008-.866-.013-1.7-2.782.604-3.369-1.341-3.369-1.341-.454-1.155-1.11-1.462-1.11-1.462-.908-.62.069-.608.069-.608 1.003.07 1.531 1.03 1.531 1.03.892 1.529 2.341 1.087 2.91.831.092-.646.35-1.086.636-1.336-2.22-.253-4.555-1.11-4.555-4.943 0-1.091.39-1.984 1.029-2.683-.103-.253-.446-1.27.098-2.647 0 0 .84-.269 2.75 1.025A9.578 9.578 0 0112 6.836c.85.004 1.705.114 2.504.336 1.909-1.294 2.747-1.025 2.747-1.025.546 1.377.203 2.394.1 2.647.64.699 1.028 1.592 1.028 2.683 0 3.842-2.339 4.687-4.566 4.935.359.309.678.919.678 1.852 0 1.336-.012 2.415-.012 2.743 0 .267.18.578.688.48C19.138 20.167 22 16.418 22 12c0-5.523-4.477-10-10-10z"/></svg>
                            <span>GitHub</span>
                        </a>
                    </li>
                    <li>
                        <a href="https://jorijn.com" class="footer-contact-link" rel="noopener" target="_blank" aria-label="Personal website (opens in new tab)">
                            <svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
                            <span>Website</span>
                        </a>
                    </li>
                    <li>
                        <a href="https://toot.community/@jorijn" class="footer-contact-link" rel="me noopener" target="_blank" aria-label="Mastodon profile (opens in new tab)">
                            <svg aria-hidden="true" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M21.327 8.566c0-4.339-2.843-5.61-2.843-5.61-1.433-.658-3.894-.935-6.451-.956h-.063c-2.557.021-5.016.298-6.45.956 0 0-2.843 1.272-2.843 5.61 0 .993-.019 2.181.012 3.441.103 4.243.778 8.425 4.701 9.463 1.809.479 3.362.579 4.612.51 2.268-.126 3.541-.809 3.541-.809l-.075-1.646s-1.621.511-3.441.449c-1.804-.062-3.707-.194-3.999-2.409a4.523 4.523 0 0 1-.04-.621s1.77.432 4.014.535c1.372.063 2.658-.08 3.965-.236 2.506-.299 4.688-1.843 4.962-3.254.434-2.223.398-5.424.398-5.424zm-3.353 5.59h-2.081V9.057c0-1.075-.452-1.62-1.357-1.62-1 0-1.501.647-1.501 1.927v2.791h-2.069V9.364c0-1.28-.501-1.927-1.502-1.927-.905 0-1.357.546-1.357 1.62v5.099H6.026V8.903c0-1.074.273-1.927.823-2.558.566-.631 1.307-.955 2.228-.955 1.065 0 1.872.409 2.405 1.228l.518.869.519-.869c.533-.819 1.34-1.228 2.405-1.228.92 0 1.662.324 2.228.955.549.631.822 1.484.822 2.558v5.253z"/></svg>
                            <span>Mastodon</span>
                        </a>
                    </li>
                </ul>
            </nav>
        </footer>
    </div>
</body>
</html>
"""

NODE_TEMPLATE = """
{% extends "base" %}
{% block content %}
{% if metrics_bar %}
<section class="metrics-bar" aria-label="Key metrics">
    {% for m in metrics_bar %}
    <div class="metric">
        <span class="metric-value">{{ m.value }}</span>
        <span class="metric-label">{{ m.label }}</span>
    </div>
    {% endfor %}
</section>
{% endif %}

<div class="dashboard-grid">
    {% if snapshot %}
    <section class="card" aria-labelledby="snapshot-heading">
        <div class="card-header">
            <h2 id="snapshot-heading" class="card-title">Latest Snapshot</h2>
        </div>
        <div class="card-body">
            <table class="snapshot-table">
                <tbody>
                {% for key, value, tooltip in snapshot_table %}
                <tr>
                        <th>{% if tooltip %}<span class="tooltip-trigger" tabindex="0" data-tooltip="{{ tooltip }}">{{ key }}</span>{% else %}{{ key }}{% endif %}</th>
                    <td>{{ value }}</td>
                </tr>
                {% endfor %}
                </tbody>
            </table>
        </div>
    </section>
    {% endif %}

    {% if about %}
    <section class="card" aria-labelledby="about-heading">
        <div class="card-header">
            <h2 id="about-heading" class="card-title">About this Node</h2>
        </div>
        <div class="card-body">
            <p>{{ about | safe }}</p>
        </div>
    </section>
    {% endif %}
</div>

<section class="charts-section card" aria-labelledby="charts-heading">
    <div class="card-header">
        <h2 id="charts-heading" class="card-title">Charts - {{ period | capitalize }}</h2>
    </div>
    <div class="card-body">
        <div class="charts-grid">
            {% for chart in charts %}
            <article class="chart-card">
                <div class="chart-header">
                    <h3 class="chart-title">{{ chart.label }}</h3>
                </div>
                <div class="chart-body">
                    <img src="{{ chart.src }}" alt="{{ chart.label }} over the last {{ period }}" loading="lazy">
                </div>
            </article>
            {% endfor %}
        </div>
    </div>
</section>
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


def extract_snapshot_table(snapshot: dict, role: str) -> list[tuple[str, str, str]]:
    """
    Extract key-value pairs from snapshot for display.

    Returns list of (label, formatted_value, tooltip) tuples.
    """
    table = []

    # Timestamp
    ts = snapshot.get("ts")
    if ts:
        table.append(("Timestamp", format_time(ts), "When this snapshot was captured"))

    if role == "companion":
        # Battery (from stats.core.battery_mv in millivolts)
        bat_mv = get_by_path(snapshot, "stats.core.battery_mv")
        if bat_mv is not None:
            bat_v = bat_mv / 1000.0
            bat_pct = voltage_to_percentage(bat_v)
            table.append(("Battery Voltage", f"{format_value(bat_v)} V ({bat_pct:.0f}%)",
                         "Current battery voltage (4.2V = full, 3.0V = empty)"))

        # Contacts
        contacts_count = get_by_path(snapshot, "derived.contacts_count")
        if contacts_count is not None:
            table.append(("Contacts", str(contacts_count),
                         "Number of known nodes in the mesh network"))

        # Packets (from stats.packets.recv/sent)
        rx = get_by_path(snapshot, "stats.packets.recv")
        if rx is not None:
            table.append(("RX Packets", format_number(rx),
                         "Total packets received since last reboot"))

        tx = get_by_path(snapshot, "stats.packets.sent")
        if tx is not None:
            table.append(("TX Packets", format_number(tx),
                         "Total packets transmitted since last reboot"))

        # Radio info (from self_info)
        freq = get_by_path(snapshot, "self_info.radio_freq")
        if freq is not None:
            table.append(("Frequency", f"{format_value(freq)} MHz",
                         "LoRa radio frequency"))

        sf = get_by_path(snapshot, "self_info.radio_sf")
        if sf is not None:
            table.append(("Spreading Factor", str(sf),
                         "LoRa spreading factor (higher = longer range, slower speed)"))

        bw = get_by_path(snapshot, "self_info.radio_bw")
        if bw is not None:
            table.append(("Bandwidth", f"{format_value(bw)} kHz",
                         "LoRa channel bandwidth"))

        tx_power = get_by_path(snapshot, "self_info.tx_power")
        if tx_power is not None:
            table.append(("TX Power", f"{tx_power} dBm",
                         "Transmit power in decibels relative to 1 milliwatt"))

        # Uptime
        uptime = get_by_path(snapshot, "stats.core.uptime_secs")
        if uptime is not None:
            table.append(("Uptime", format_uptime(uptime),
                         "Time since last device reboot"))

    elif role == "repeater":
        # Battery - status.bat is in millivolts
        bat_mv = get_by_path(snapshot, "status.bat")
        if bat_mv is not None:
            bat_v = bat_mv / 1000.0
            bat_pct = voltage_to_percentage(bat_v)
            table.append(("Battery Voltage", f"{format_value(bat_v)} V ({bat_pct:.0f}%)",
                         "Current battery voltage (4.2V = full, 3.0V = empty)"))

        # Also check telemetry array for voltage channel
        telemetry = snapshot.get("telemetry")
        if isinstance(telemetry, list):
            for item in telemetry:
                if isinstance(item, dict) and item.get("type") == "voltage":
                    table.append(("Battery (telemetry)", f"{format_value(item.get('value'))} V",
                                 "Battery voltage from telemetry channel"))
                    break

        # Neighbours
        neigh = get_by_path(snapshot, "derived.neighbours_count")
        if neigh is not None:
            table.append(("Neighbours", str(neigh),
                         "Number of directly reachable mesh nodes"))

        # Radio stats - actual field names from status
        rssi = get_by_path(snapshot, "status.last_rssi")
        if rssi is not None:
            table.append(("RSSI", f"{rssi} dBm",
                         "Received Signal Strength Indicator of last packet (closer to 0 = stronger)"))

        snr = get_by_path(snapshot, "status.last_snr")
        if snr is not None:
            table.append(("SNR", f"{format_value(snr)} dB",
                         "Signal-to-Noise Ratio of last packet (higher = cleaner signal)"))

        noise = get_by_path(snapshot, "status.noise_floor")
        if noise is not None:
            table.append(("Noise Floor", f"{noise} dBm",
                         "Background radio noise level (lower = quieter environment)"))

        # Packets - from status, not telemetry
        rx = get_by_path(snapshot, "status.nb_recv")
        if rx is not None:
            table.append(("RX Packets", format_number(rx),
                         "Total packets received since last reboot"))

        tx = get_by_path(snapshot, "status.nb_sent")
        if tx is not None:
            table.append(("TX Packets", format_number(tx),
                         "Total packets transmitted since last reboot"))

        # Uptime
        uptime = get_by_path(snapshot, "status.uptime")
        if uptime is not None:
            table.append(("Uptime", format_uptime(uptime),
                         "Time since last device reboot"))

        # Airtime
        airtime = get_by_path(snapshot, "status.airtime")
        if airtime is not None:
            table.append(("TX Airtime", format_duration(airtime),
                         "Total time spent transmitting (legal limit: 10% duty cycle)"))

        # Skip reason
        skip = get_by_path(snapshot, "skip_reason")
        if skip:
            table.append(("Status", f"Skipped: {skip}",
                         "Data collection was skipped for this snapshot"))

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
    # Metrics not in this list will appear at the end alphabetically
    chart_order = [
        # Battery & health
        "bat_v", "bat_pct", "uptime",
        # Signal quality
        "rssi", "snr", "noise",
        # Traffic overview
        "rx", "tx",
        # Airtime usage
        "airtime", "rx_air",
        # Packet breakdown
        "fl_rx", "fl_tx", "di_rx", "di_tx",
        # Duplicates & queue
        "fl_dups", "di_dups", "txq",
        # Companion-specific
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
            # Battery percentage
            bat_mv = get_by_path(snapshot, "status.bat")
            if bat_mv is not None:
                bat_pct = voltage_to_percentage(bat_mv / 1000)
                metrics_bar.append({"value": f"{bat_pct:.0f}%", "label": "Battery"})
            # Uptime
            uptime = get_by_path(snapshot, "status.uptime")
            if uptime is not None:
                metrics_bar.append({"value": format_uptime(uptime), "label": "Uptime"})
            # RSSI
            rssi = get_by_path(snapshot, "status.last_rssi")
            if rssi is not None:
                metrics_bar.append({"value": f"{rssi} dBm", "label": "RSSI"})
            # SNR
            snr = get_by_path(snapshot, "status.last_snr")
            if snr is not None:
                metrics_bar.append({"value": f"{snr:.1f} dB", "label": "SNR"})
        elif role == "companion":
            # Battery percentage
            bat_mv = get_by_path(snapshot, "stats.core.battery_mv")
            if bat_mv is not None:
                bat_pct = voltage_to_percentage(bat_mv / 1000)
                metrics_bar.append({"value": f"{bat_pct:.0f}%", "label": "Battery"})
            # Uptime
            uptime = get_by_path(snapshot, "stats.core.uptime_secs")
            if uptime is not None:
                metrics_bar.append({"value": format_uptime(uptime), "label": "Uptime"})
            # Contacts
            contacts = get_by_path(snapshot, "derived.contacts_count")
            if contacts is not None:
                metrics_bar.append({"value": str(contacts), "label": "Contacts"})
            # RX packets
            rx = get_by_path(snapshot, "stats.packets.recv")
            if rx is not None:
                metrics_bar.append({"value": f"{rx:,}", "label": "RX Packets"})

    # Base path for tab links: root pages use "", others use "/role"
    base_path = "" if at_root else f"/{role}"

    # Meta description for social sharing
    meta_descriptions = {
        "repeater": (
            f"Live stats for MeshCore LoRa repeater in Oosterhout, NL. "
            f"Battery, signal strength, packet counts, and uptime charts."
        ),
        "companion": (
            f"Live stats for MeshCore companion node. "
            f"Battery, contacts, packet counts, and uptime monitoring."
        ),
    }
    meta_description = meta_descriptions.get(role, "MeshCore mesh network statistics dashboard.")

    # Create combined template
    full_template = BASE_TEMPLATE.replace(
        "{% block content %}{% endblock %}",
        NODE_TEMPLATE.replace("{% extends \"base\" %}\n{% block content %}", "").replace("{% endblock %}", "")
    )

    template = env.from_string(full_template)
    return template.render(
        title=f"{node_name} - {period.capitalize()}",
        meta_description=meta_description,
        node_name=node_name,
        pubkey_pre=pubkey_pre,
        status_class=status_class,
        status_text=status_text,
        role=role,
        period=period,
        base_path=base_path,
        about=about_text.get(role),
        last_updated=last_updated,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        snapshot=snapshot,
        snapshot_table=snapshot_table,
        metrics_bar=metrics_bar,
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
