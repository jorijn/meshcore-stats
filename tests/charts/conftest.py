"""Fixtures for chart tests."""

import pytest
import re
import json
from datetime import datetime, timedelta
from pathlib import Path

from meshmon.charts import (
    DataPoint,
    TimeSeries,
    ChartTheme,
    CHART_THEMES,
)


@pytest.fixture
def light_theme():
    """Light chart theme."""
    return CHART_THEMES["light"]


@pytest.fixture
def dark_theme():
    """Dark chart theme."""
    return CHART_THEMES["dark"]


@pytest.fixture
def sample_timeseries():
    """Sample time series with 24 hours of data."""
    now = datetime.now()
    points = []
    for i in range(24):
        ts = now - timedelta(hours=23 - i)
        # Simulate battery voltage pattern (higher during day, lower at night)
        value = 3.7 + 0.3 * abs(12 - i) / 12
        points.append(DataPoint(timestamp=ts, value=value))

    return TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=points,
    )


@pytest.fixture
def empty_timeseries():
    """Empty time series (no data)."""
    return TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=[],
    )


@pytest.fixture
def single_point_timeseries():
    """Time series with single data point."""
    now = datetime.now()
    return TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=[DataPoint(timestamp=now, value=3.85)],
    )


@pytest.fixture
def counter_timeseries():
    """Sample counter time series (for rate calculation testing)."""
    now = datetime.now()
    points = []
    for i in range(24):
        ts = now - timedelta(hours=23 - i)
        # Simulate increasing counter
        value = float(i * 100)
        points.append(DataPoint(timestamp=ts, value=value))

    return TimeSeries(
        metric="nb_recv",
        role="repeater",
        period="day",
        points=points,
    )


@pytest.fixture
def week_timeseries():
    """Sample week time series for binning tests."""
    now = datetime.now()
    points = []
    # One point per hour for 7 days = 168 points
    for i in range(168):
        ts = now - timedelta(hours=167 - i)
        value = 3.7 + 0.2 * (i % 24) / 24
        points.append(DataPoint(timestamp=ts, value=value))

    return TimeSeries(
        metric="bat",
        role="repeater",
        period="week",
        points=points,
    )


def normalize_svg_for_snapshot(svg: str) -> str:
    """Normalize SVG for deterministic snapshot comparison.

    Handles matplotlib's dynamic ID generation while preserving
    semantic content that affects chart appearance.
    """
    # 1. Normalize matplotlib-generated IDs (prefixed with random hex)
    svg = re.sub(r'id="[a-zA-Z0-9]+-[0-9a-f]+"', 'id="normalized"', svg)
    svg = re.sub(r'id="m[0-9a-f]{8,}"', 'id="normalized"', svg)

    # 2. Normalize url(#...) references to match
    svg = re.sub(r'url\(#[a-zA-Z0-9]+-[0-9a-f]+\)', 'url(#normalized)', svg)
    svg = re.sub(r'url\(#m[0-9a-f]{8,}\)', 'url(#normalized)', svg)

    # 3. Normalize clip-path IDs
    svg = re.sub(r'clip-path="url\(#[^)]+\)"', 'clip-path="url(#clip)"', svg)

    # 4. Normalize xlink:href="#..." references
    svg = re.sub(r'xlink:href="#[a-zA-Z0-9]+-[0-9a-f]+"', 'xlink:href="#normalized"', svg)
    svg = re.sub(r'xlink:href="#m[0-9a-f]{8,}"', 'xlink:href="#normalized"', svg)

    # 5. Remove matplotlib version comment (changes between versions)
    svg = re.sub(r'<!-- Created with matplotlib.*?-->', '', svg)

    # 6. Normalize whitespace (but preserve newlines for readability)
    svg = re.sub(r'[ \t]+', ' ', svg)
    svg = re.sub(r' ?\n ?', '\n', svg)

    return svg.strip()


def extract_svg_data_attributes(svg: str) -> dict:
    """Extract data-* attributes from SVG for validation.

    Args:
        svg: SVG string

    Returns:
        Dict with extracted data attributes
    """
    data = {}

    # Extract data-points JSON
    points_match = re.search(r'data-points="([^"]+)"', svg)
    if points_match:
        points_str = points_match.group(1).replace('&quot;', '"')
        try:
            data["points"] = json.loads(points_str)
        except json.JSONDecodeError:
            data["points_raw"] = points_str

    # Extract other data attributes
    for attr in ["data-metric", "data-period", "data-theme",
                 "data-x-start", "data-x-end", "data-y-min", "data-y-max"]:
        match = re.search(rf'{attr}="([^"]+)"', svg)
        if match:
            key = attr.replace("data-", "").replace("-", "_")
            data[key] = match.group(1)

    return data


@pytest.fixture
def snapshots_dir():
    """Path to snapshots directory."""
    return Path(__file__).parent.parent / "snapshots" / "svg"


@pytest.fixture
def sample_raw_points():
    """Raw points for aggregation testing."""
    now = datetime.now()
    return [
        (now - timedelta(hours=2), 3.7),
        (now - timedelta(hours=1, minutes=45), 3.72),
        (now - timedelta(hours=1, minutes=30), 3.75),
        (now - timedelta(hours=1), 3.8),
        (now - timedelta(minutes=30), 3.82),
        (now, 3.85),
    ]
