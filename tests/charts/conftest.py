"""Fixtures for chart tests."""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from meshmon.charts import (
    CHART_THEMES,
    DataPoint,
    TimeSeries,
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
    semantic content that affects chart appearance. Uses sequential
    normalized IDs to preserve relationships between definitions
    and references.

    IMPORTANT: Each ID type gets its own prefix to maintain uniqueness:
    - tick_N: matplotlib tick marks (m[0-9a-f]{8,})
    - clip_N: clipPath definitions (p[0-9a-f]{8,})
    - glyph_N: font glyph definitions (DejaVuSans-XX)

    This ensures that:
    1. All IDs remain unique (no duplicates)
    2. References (xlink:href, url(#...)) correctly resolve
    3. SVG renders identically to the original
    """
    # Patterns for matplotlib's random IDs, each with its own prefix
    # to maintain uniqueness across different ID types
    id_type_patterns = [
        (r'm[0-9a-f]{8,}', 'tick'),      # matplotlib tick marks
        (r'p[0-9a-f]{8,}', 'clip'),      # matplotlib clipPaths
        (r'DejaVuSans-[0-9a-f]+', 'glyph'),  # font glyphs (hex-named)
    ]

    # Find all IDs in the document
    all_ids = re.findall(r'id="([^"]+)"', svg)

    # Create mapping for IDs that match random patterns
    # Use separate counters per type to ensure predictable naming
    id_mapping = {}
    type_counters = {prefix: 0 for _, prefix in id_type_patterns}

    for id_val in all_ids:
        if id_val in id_mapping:
            continue
        for pattern, prefix in id_type_patterns:
            if re.fullmatch(pattern, id_val):
                new_id = f"{prefix}_{type_counters[prefix]}"
                id_mapping[id_val] = new_id
                type_counters[prefix] += 1
                break

    # Replace all occurrences of mapped IDs (definitions and references)
    # Process in a deterministic order (sorted by original ID) for consistency
    for old_id, new_id in sorted(id_mapping.items()):
        # Replace id definitions
        svg = svg.replace(f'id="{old_id}"', f'id="{new_id}"')
        # Replace url(#...) references
        svg = svg.replace(f'url(#{old_id})', f'url(#{new_id})')
        # Replace xlink:href references
        svg = svg.replace(f'xlink:href="#{old_id}"', f'xlink:href="#{new_id}"')
        # Replace href references (SVG 2.0 style without xlink prefix)
        svg = svg.replace(f'href="#{old_id}"', f'href="#{new_id}"')

    # Remove matplotlib version comment (changes between versions)
    svg = re.sub(r'<!-- Created with matplotlib.*?-->', '', svg)

    # Normalize dc:date timestamp (changes on each render)
    svg = re.sub(r'<dc:date>[^<]+</dc:date>', '<dc:date>NORMALIZED</dc:date>', svg)

    # Normalize whitespace (but preserve newlines for readability)
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


# --- Deterministic fixtures for snapshot testing ---
# These use fixed timestamps to produce consistent SVG output


@pytest.fixture
def snapshot_base_time():
    """Fixed base time for deterministic snapshot tests.

    Uses 2024-01-15 12:00:00 UTC as a stable reference point.
    """
    return datetime(2024, 1, 15, 12, 0, 0)


@pytest.fixture
def snapshot_gauge_timeseries(snapshot_base_time):
    """Deterministic gauge time series for snapshot testing.

    Creates a battery voltage pattern over 24 hours with fixed timestamps.
    """
    points = []
    for i in range(24):
        ts = snapshot_base_time - timedelta(hours=23 - i)
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
def snapshot_counter_timeseries(snapshot_base_time):
    """Deterministic counter time series for snapshot testing.

    Creates a packet rate pattern over 24 hours with fixed timestamps.
    This represents rate values (already converted from counter deltas).
    """
    points = []
    for i in range(24):
        ts = snapshot_base_time - timedelta(hours=23 - i)
        # Simulate packet rate - higher during day hours (6-18)
        hour = (i + 12) % 24  # Convert to actual hour of day
        value = (
            2.0 + (hour - 6) * 0.3  # 2.0 to 5.6 packets/min
            if 6 <= hour <= 18
            else 0.5 + (hour % 6) * 0.1  # 0.5 to 1.1 packets/min (night)
        )
        points.append(DataPoint(timestamp=ts, value=value))

    return TimeSeries(
        metric="nb_recv",
        role="repeater",
        period="day",
        points=points,
    )


@pytest.fixture
def snapshot_empty_timeseries():
    """Empty time series for snapshot testing."""
    return TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=[],
    )


@pytest.fixture
def snapshot_single_point_timeseries(snapshot_base_time):
    """Time series with single data point for snapshot testing."""
    return TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=[DataPoint(timestamp=snapshot_base_time, value=3.85)],
    )


def normalize_svg_for_snapshot_full(svg: str) -> str:
    """Extended SVG normalization for full snapshot comparison.

    In addition to standard normalization, this also:
    - Removes timestamps from data-points to allow content-only comparison
    - Normalizes floating point precision

    Used when you want to compare the visual structure but not exact data values.
    """
    # Apply standard normalization first
    svg = normalize_svg_for_snapshot(svg)

    # Normalize data-points timestamps (keep structure, normalize values)
    # This allows charts with different base times to still match structure
    svg = re.sub(r'"ts":\s*\d+', '"ts":0', svg)

    # Normalize floating point values to 2 decimal places in attributes
    def normalize_float(match):
        try:
            val = float(match.group(1))
            return f'{val:.2f}'
        except ValueError:
            return match.group(0)

    svg = re.sub(r'(\d+\.\d{3,})', normalize_float, svg)

    return svg
