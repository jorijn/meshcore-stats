#!/usr/bin/env python3
"""Generate initial snapshot files for tests.

This script creates the initial SVG and TXT snapshots for snapshot testing.
Run this once to generate the baseline snapshots, then use pytest to verify them.

Usage:
    python scripts/generate_snapshots.py
"""

import re
import sys
from datetime import datetime, timedelta, date
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.charts import (
    render_chart_svg,
    CHART_THEMES,
    DataPoint,
    TimeSeries,
)
from meshmon.reports import (
    format_monthly_txt,
    format_yearly_txt,
    MonthlyAggregate,
    YearlyAggregate,
    DailyAggregate,
    MetricStats,
    LocationInfo,
)


def normalize_svg_for_snapshot(svg: str) -> str:
    """Normalize SVG for deterministic snapshot comparison."""
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


def generate_svg_snapshots():
    """Generate all SVG snapshot files."""
    print("Generating SVG snapshots...")

    svg_dir = Path(__file__).parent.parent / "tests" / "snapshots" / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)

    light_theme = CHART_THEMES["light"]
    dark_theme = CHART_THEMES["dark"]

    # Fixed base time for deterministic tests
    base_time = datetime(2024, 1, 15, 12, 0, 0)

    # Generate gauge timeseries (battery voltage)
    gauge_points = []
    for i in range(24):
        ts = base_time - timedelta(hours=23 - i)
        value = 3.7 + 0.3 * abs(12 - i) / 12
        gauge_points.append(DataPoint(timestamp=ts, value=value))

    gauge_ts = TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=gauge_points,
    )

    # Generate counter timeseries (packet rate)
    counter_points = []
    for i in range(24):
        ts = base_time - timedelta(hours=23 - i)
        hour = (i + 12) % 24
        if 6 <= hour <= 18:
            value = 2.0 + (hour - 6) * 0.3
        else:
            value = 0.5 + (hour % 6) * 0.1
        counter_points.append(DataPoint(timestamp=ts, value=value))

    counter_ts = TimeSeries(
        metric="nb_recv",
        role="repeater",
        period="day",
        points=counter_points,
    )

    # Empty timeseries
    empty_ts = TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=[],
    )

    # Single point timeseries
    single_point_ts = TimeSeries(
        metric="bat",
        role="repeater",
        period="day",
        points=[DataPoint(timestamp=base_time, value=3.85)],
    )

    # Generate snapshots
    snapshots = [
        ("bat_day_light.svg", gauge_ts, light_theme, 3.0, 4.2),
        ("bat_day_dark.svg", gauge_ts, dark_theme, 3.0, 4.2),
        ("nb_recv_day_light.svg", counter_ts, light_theme, None, None),
        ("nb_recv_day_dark.svg", counter_ts, dark_theme, None, None),
        ("empty_day_light.svg", empty_ts, light_theme, None, None),
        ("empty_day_dark.svg", empty_ts, dark_theme, None, None),
        ("single_point_day_light.svg", single_point_ts, light_theme, 3.0, 4.2),
    ]

    for filename, ts, theme, y_min, y_max in snapshots:
        svg = render_chart_svg(ts, theme, y_min=y_min, y_max=y_max)
        normalized = normalize_svg_for_snapshot(svg)

        output_path = svg_dir / filename
        output_path.write_text(normalized, encoding="utf-8")
        print(f"  Created: {output_path}")


def generate_txt_snapshots():
    """Generate all TXT report snapshot files."""
    print("Generating TXT snapshots...")

    txt_dir = Path(__file__).parent.parent / "tests" / "snapshots" / "txt"
    txt_dir.mkdir(parents=True, exist_ok=True)

    sample_location = LocationInfo(
        name="Test Observatory",
        lat=52.3676,
        lon=4.9041,
        elev=2.0,
    )

    # Repeater monthly aggregate
    repeater_daily_data = []
    for day in range(1, 6):
        repeater_daily_data.append(
            DailyAggregate(
                date=date(2024, 1, day),
                metrics={
                    "bat": MetricStats(
                        min_value=3600 + day * 10,
                        min_time=datetime(2024, 1, day, 4, 0),
                        max_value=3900 + day * 10,
                        max_time=datetime(2024, 1, day, 14, 0),
                        mean=3750 + day * 10,
                        count=96,
                    ),
                    "bat_pct": MetricStats(mean=65.0 + day * 2, count=96),
                    "last_rssi": MetricStats(mean=-85.0 - day, count=96),
                    "last_snr": MetricStats(mean=8.5 + day * 0.2, count=96),
                    "noise_floor": MetricStats(mean=-115.0, count=96),
                    "nb_recv": MetricStats(total=500 + day * 100, count=96),
                    "nb_sent": MetricStats(total=200 + day * 50, count=96),
                    "airtime": MetricStats(total=120 + day * 20, count=96),
                },
                snapshot_count=96,
            )
        )

    repeater_monthly = MonthlyAggregate(
        year=2024,
        month=1,
        role="repeater",
        daily=repeater_daily_data,
        summary={
            "bat": MetricStats(
                min_value=3610, min_time=datetime(2024, 1, 1, 4, 0),
                max_value=3950, max_time=datetime(2024, 1, 5, 14, 0),
                mean=3780, count=480,
            ),
            "bat_pct": MetricStats(mean=71.0, count=480),
            "last_rssi": MetricStats(mean=-88.0, count=480),
            "last_snr": MetricStats(mean=9.1, count=480),
            "noise_floor": MetricStats(mean=-115.0, count=480),
            "nb_recv": MetricStats(total=4000, count=480),
            "nb_sent": MetricStats(total=1750, count=480),
            "airtime": MetricStats(total=900, count=480),
        },
    )

    # Companion monthly aggregate
    companion_daily_data = []
    for day in range(1, 6):
        companion_daily_data.append(
            DailyAggregate(
                date=date(2024, 1, day),
                metrics={
                    "battery_mv": MetricStats(
                        min_value=3700 + day * 10,
                        min_time=datetime(2024, 1, day, 5, 0),
                        max_value=4000 + day * 10,
                        max_time=datetime(2024, 1, day, 12, 0),
                        mean=3850 + day * 10,
                        count=1440,
                    ),
                    "bat_pct": MetricStats(mean=75.0 + day * 2, count=1440),
                    "contacts": MetricStats(mean=8 + day, count=1440),
                    "recv": MetricStats(total=1000 + day * 200, count=1440),
                    "sent": MetricStats(total=500 + day * 100, count=1440),
                },
                snapshot_count=1440,
            )
        )

    companion_monthly = MonthlyAggregate(
        year=2024,
        month=1,
        role="companion",
        daily=companion_daily_data,
        summary={
            "battery_mv": MetricStats(
                min_value=3710, min_time=datetime(2024, 1, 1, 5, 0),
                max_value=4050, max_time=datetime(2024, 1, 5, 12, 0),
                mean=3880, count=7200,
            ),
            "bat_pct": MetricStats(mean=81.0, count=7200),
            "contacts": MetricStats(mean=11.0, count=7200),
            "recv": MetricStats(total=8000, count=7200),
            "sent": MetricStats(total=4000, count=7200),
        },
    )

    # Repeater yearly aggregate
    repeater_yearly_monthly = []
    for month in range(1, 4):
        repeater_yearly_monthly.append(
            MonthlyAggregate(
                year=2024,
                month=month,
                role="repeater",
                daily=[],
                summary={
                    "bat": MetricStats(
                        min_value=3500 + month * 50,
                        min_time=datetime(2024, month, 15, 4, 0),
                        max_value=3950 + month * 20,
                        max_time=datetime(2024, month, 20, 14, 0),
                        mean=3700 + month * 30,
                        count=2976,
                    ),
                    "bat_pct": MetricStats(mean=60.0 + month * 5, count=2976),
                    "last_rssi": MetricStats(mean=-90.0 + month, count=2976),
                    "last_snr": MetricStats(mean=7.5 + month * 0.5, count=2976),
                    "nb_recv": MetricStats(total=30000 + month * 5000, count=2976),
                    "nb_sent": MetricStats(total=15000 + month * 2500, count=2976),
                },
            )
        )

    repeater_yearly = YearlyAggregate(
        year=2024,
        role="repeater",
        monthly=repeater_yearly_monthly,
        summary={
            "bat": MetricStats(
                min_value=3550, min_time=datetime(2024, 1, 15, 4, 0),
                max_value=4010, max_time=datetime(2024, 3, 20, 14, 0),
                mean=3760, count=8928,
            ),
            "bat_pct": MetricStats(mean=70.0, count=8928),
            "last_rssi": MetricStats(mean=-88.0, count=8928),
            "last_snr": MetricStats(mean=8.5, count=8928),
            "nb_recv": MetricStats(total=120000, count=8928),
            "nb_sent": MetricStats(total=60000, count=8928),
        },
    )

    # Companion yearly aggregate
    companion_yearly_monthly = []
    for month in range(1, 4):
        companion_yearly_monthly.append(
            MonthlyAggregate(
                year=2024,
                month=month,
                role="companion",
                daily=[],
                summary={
                    "battery_mv": MetricStats(
                        min_value=3600 + month * 30,
                        min_time=datetime(2024, month, 10, 5, 0),
                        max_value=4100 + month * 20,
                        max_time=datetime(2024, month, 25, 12, 0),
                        mean=3850 + month * 25,
                        count=44640,
                    ),
                    "bat_pct": MetricStats(mean=70.0 + month * 3, count=44640),
                    "contacts": MetricStats(mean=10 + month, count=44640),
                    "recv": MetricStats(total=50000 + month * 10000, count=44640),
                    "sent": MetricStats(total=25000 + month * 5000, count=44640),
                },
            )
        )

    companion_yearly = YearlyAggregate(
        year=2024,
        role="companion",
        monthly=companion_yearly_monthly,
        summary={
            "battery_mv": MetricStats(
                min_value=3630, min_time=datetime(2024, 1, 10, 5, 0),
                max_value=4160, max_time=datetime(2024, 3, 25, 12, 0),
                mean=3900, count=133920,
            ),
            "bat_pct": MetricStats(mean=76.0, count=133920),
            "contacts": MetricStats(mean=12.0, count=133920),
            "recv": MetricStats(total=210000, count=133920),
            "sent": MetricStats(total=105000, count=133920),
        },
    )

    # Empty aggregates
    empty_monthly = MonthlyAggregate(year=2024, month=1, role="repeater", daily=[], summary={})
    empty_yearly = YearlyAggregate(year=2024, role="repeater", monthly=[], summary={})

    # Generate all TXT snapshots
    txt_snapshots = [
        ("monthly_report_repeater.txt", format_monthly_txt(repeater_monthly, "Test Repeater", sample_location)),
        ("monthly_report_companion.txt", format_monthly_txt(companion_monthly, "Test Companion", sample_location)),
        ("yearly_report_repeater.txt", format_yearly_txt(repeater_yearly, "Test Repeater", sample_location)),
        ("yearly_report_companion.txt", format_yearly_txt(companion_yearly, "Test Companion", sample_location)),
        ("empty_monthly_report.txt", format_monthly_txt(empty_monthly, "Test Repeater", sample_location)),
        ("empty_yearly_report.txt", format_yearly_txt(empty_yearly, "Test Repeater", sample_location)),
    ]

    for filename, content in txt_snapshots:
        output_path = txt_dir / filename
        output_path.write_text(content, encoding="utf-8")
        print(f"  Created: {output_path}")


if __name__ == "__main__":
    generate_svg_snapshots()
    generate_txt_snapshots()
    print("\nSnapshot generation complete!")
    print("Run pytest to verify the snapshots work correctly.")
