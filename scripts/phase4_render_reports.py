#!/usr/bin/env python3
"""
Phase 4: Render reports from SQLite database.

Generates monthly and yearly statistics reports in HTML, TXT, and JSON
formats for both repeater and companion nodes.

Output structure:
    out/reports/
        index.html                 # Reports listing
        repeater/
            2025/
                index.html         # Yearly report (HTML)
                report.txt         # Yearly report (TXT)
                report.json        # Yearly report (JSON)
                12/
                    index.html     # Monthly report (HTML)
                    report.txt     # Monthly report (TXT)
                    report.json    # Monthly report (JSON)
        companion/
            ...                    # Same structure
"""

import calendar
import json
import sys
from pathlib import Path
from typing import Optional

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from meshmon.db import init_db
from meshmon.env import get_config
from meshmon import log


def safe_write(path: Path, content: str) -> bool:
    """Write content to file with error handling.

    Args:
        path: File path to write to
        content: Content to write

    Returns:
        True if write succeeded, False otherwise
    """
    try:
        path.write_text(content)
        return True
    except IOError as e:
        log.error(f"Failed to write {path}: {e}")
        return False


from meshmon.reports import (
    LocationInfo,
    aggregate_monthly,
    aggregate_yearly,
    format_monthly_txt,
    format_yearly_txt,
    get_available_periods,
    monthly_to_json,
    yearly_to_json,
)
from meshmon.html import render_report_page, render_reports_index


def get_node_name(role: str) -> str:
    """Get display name for a node role from configuration."""
    cfg = get_config()
    if role == "repeater":
        return cfg.repeater_display_name
    elif role == "companion":
        return cfg.companion_display_name
    return role.capitalize()


def get_location() -> LocationInfo:
    """Get location info from config."""
    cfg = get_config()
    return LocationInfo(
        name=cfg.report_location_name,
        lat=cfg.report_lat,
        lon=cfg.report_lon,
        elev=cfg.report_elev,
    )


def render_monthly_report(
    role: str,
    year: int,
    month: int,
    prev_period: Optional[tuple[int, int]] = None,
    next_period: Optional[tuple[int, int]] = None,
) -> None:
    """Render monthly report in all formats.

    Args:
        role: "companion" or "repeater"
        year: Report year
        month: Report month (1-12)
        prev_period: (year, month) of previous report, or None
        next_period: (year, month) of next report, or None
    """
    cfg = get_config()
    node_name = get_node_name(role)
    location = get_location()

    log.info(f"Aggregating {role} monthly report for {year}-{month:02d}...")
    agg = aggregate_monthly(role, year, month)

    if not agg.daily:
        log.warn(f"No data for {role} {year}-{month:02d}, skipping")
        return

    # Create output directory
    out_dir = cfg.out_dir / "reports" / role / str(year) / f"{month:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build prev/next navigation
    prev_report = None
    next_report = None
    if prev_period:
        py, pm = prev_period
        prev_report = {
            "url": f"/reports/{role}/{py}/{pm:02d}/",
            "label": f"{calendar.month_abbr[pm]} {py}",
        }
    if next_period:
        ny, nm = next_period
        next_report = {
            "url": f"/reports/{role}/{ny}/{nm:02d}/",
            "label": f"{calendar.month_abbr[nm]} {ny}",
        }

    # HTML
    html = render_report_page(agg, node_name, "monthly", prev_report, next_report)
    safe_write(out_dir / "index.html", html)

    # TXT (WeeWX-style)
    txt = format_monthly_txt(agg, node_name, location)
    safe_write(out_dir / "report.txt", txt)

    # JSON
    json_data = monthly_to_json(agg)
    safe_write(out_dir / "report.json", json.dumps(json_data, indent=2))

    log.debug(f"Wrote monthly report: {out_dir}")


def render_yearly_report(
    role: str,
    year: int,
    prev_year: Optional[int] = None,
    next_year: Optional[int] = None,
) -> None:
    """Render yearly report in all formats.

    Args:
        role: "companion" or "repeater"
        year: Report year
        prev_year: Previous year with data, or None
        next_year: Next year with data, or None
    """
    cfg = get_config()
    node_name = get_node_name(role)
    location = get_location()

    log.info(f"Aggregating {role} yearly report for {year}...")
    agg = aggregate_yearly(role, year)

    if not agg.monthly:
        log.warn(f"No data for {role} {year}, skipping")
        return

    # Create output directory
    out_dir = cfg.out_dir / "reports" / role / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Build prev/next navigation
    prev_report = None
    next_report = None
    if prev_year:
        prev_report = {
            "url": f"/reports/{role}/{prev_year}/",
            "label": str(prev_year),
        }
    if next_year:
        next_report = {
            "url": f"/reports/{role}/{next_year}/",
            "label": str(next_year),
        }

    # HTML
    html = render_report_page(agg, node_name, "yearly", prev_report, next_report)
    safe_write(out_dir / "index.html", html)

    # TXT (WeeWX-style)
    txt = format_yearly_txt(agg, node_name, location)
    safe_write(out_dir / "report.txt", txt)

    # JSON
    json_data = yearly_to_json(agg)
    safe_write(out_dir / "report.json", json.dumps(json_data, indent=2))

    log.debug(f"Wrote yearly report: {out_dir}")


def build_reports_index_data() -> list[dict]:
    """Build data structure for reports index page.

    Returns:
        List of section dicts with 'role' and 'years' keys
    """
    sections = []

    for role in ["repeater", "companion"]:
        periods = get_available_periods(role)
        if not periods:
            sections.append({"role": role, "years": []})
            continue

        # Group by year
        years_data = {}
        for year, month in periods:
            if year not in years_data:
                years_data[year] = []
            years_data[year].append({
                "month": month,
                "name": calendar.month_name[month],
            })

        # Build years list, sorted descending
        years = []
        for year in sorted(years_data.keys(), reverse=True):
            years.append({
                "year": year,
                "months": sorted(years_data[year], key=lambda m: m["month"]),
            })

        sections.append({"role": role, "years": years})

    return sections


def main():
    """Generate all statistics reports."""
    # Ensure database is initialized
    init_db()

    cfg = get_config()

    log.info("Generating reports from database...")

    # Ensure base reports directory exists
    (cfg.out_dir / "reports").mkdir(parents=True, exist_ok=True)

    total_monthly = 0
    total_yearly = 0

    for role in ["repeater", "companion"]:
        periods = get_available_periods(role)
        if not periods:
            log.info(f"No data found for {role}")
            continue

        log.info(f"Found {len(periods)} months of data for {role}")

        # Sort periods chronologically for prev/next navigation
        sorted_periods = sorted(periods)

        # Render monthly reports with prev/next links
        for i, (year, month) in enumerate(sorted_periods):
            prev_period = sorted_periods[i - 1] if i > 0 else None
            next_period = sorted_periods[i + 1] if i < len(sorted_periods) - 1 else None
            render_monthly_report(role, year, month, prev_period, next_period)
            total_monthly += 1

        # Get unique years
        years = sorted(set(y for y, m in periods))

        # Render yearly reports with prev/next links
        for i, year in enumerate(years):
            prev_year = years[i - 1] if i > 0 else None
            next_year = years[i + 1] if i < len(years) - 1 else None
            render_yearly_report(role, year, prev_year, next_year)
            total_yearly += 1

    # Render reports index
    log.info("Rendering reports index...")
    sections = build_reports_index_data()
    index_html = render_reports_index(sections)
    safe_write(cfg.out_dir / "reports" / "index.html", index_html)

    log.info(
        f"Generated {total_monthly} monthly + {total_yearly} yearly reports "
        f"to {cfg.out_dir / 'reports'}"
    )
    log.info("Report generation complete")


if __name__ == "__main__":
    main()
