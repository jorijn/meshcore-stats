"""Fixtures for HTML tests."""

from pathlib import Path

import pytest


@pytest.fixture
def sample_chart_stats():
    """Sample chart statistics for template rendering."""
    return {
        "bat": {
            "day": {"min": 3.5, "avg": 3.7, "max": 3.9, "current": 3.85},
            "week": {"min": 3.4, "avg": 3.65, "max": 3.95, "current": 3.8},
            "month": {"min": 3.3, "avg": 3.6, "max": 4.0, "current": 3.75},
            "year": {"min": 3.2, "avg": 3.55, "max": 4.1, "current": 3.7},
        },
        "bat_pct": {
            "day": {"min": 50, "avg": 70, "max": 90, "current": 85},
            "week": {"min": 45, "avg": 65, "max": 95, "current": 80},
        },
        "nb_recv": {
            "day": {"min": 0, "avg": 50.5, "max": 100, "current": 75},
            "week": {"min": 0, "avg": 48.2, "max": 150, "current": 60},
        },
    }


@pytest.fixture
def sample_latest_metrics():
    """Sample latest metrics for page rendering."""
    return {
        "ts": 1704067200,  # 2024-01-01 00:00:00 UTC
        "bat": 3850.0,
        "bat_pct": 75.0,
        "uptime": 86400,
        "last_rssi": -85,
        "last_snr": 7.5,
        "noise_floor": -115,
        "nb_recv": 1234,
        "nb_sent": 567,
        "tx_queue_len": 0,
    }


@pytest.fixture
def sample_companion_latest():
    """Sample companion latest metrics."""
    return {
        "ts": 1704067200,
        "battery_mv": 3850.0,
        "bat_pct": 75.0,
        "uptime_secs": 86400,
        "contacts": 5,
        "recv": 1234,
        "sent": 567,
    }


@pytest.fixture
def templates_dir():
    """Path to templates directory."""
    return Path(__file__).parent.parent.parent / "src" / "meshmon" / "templates"


@pytest.fixture
def sample_svg_content():
    """Sample SVG content for testing."""
    return """<?xml version="1.0" encoding="utf-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="280"
     data-metric="bat" data-period="day" data-theme="light">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <path d="M0,0 L100,100"/>
</svg>"""
