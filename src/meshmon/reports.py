"""Report generation (WeeWX-style).

This module provides functionality to generate monthly and yearly
reports from SQLite database metrics. Reports are generated in TXT (WeeWX-style
ASCII tables), JSON, and HTML formats.

Counter metrics (nb_recv, nb_sent, airtime, etc.) are aggregated using absolute
counter values from the database, summing positive deltas to handle device
reboots gracefully.

Metric names use firmware field names directly:
- Companion: battery_mv, uptime_secs, recv, sent, contacts
- Repeater: bat, uptime, last_rssi, last_snr, nb_recv, nb_sent, airtime, etc.
"""

import calendar
import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from .db import get_connection, get_metrics_for_period, VALID_ROLES
from .env import get_config
from .metrics import (
    is_counter_metric,
    get_chart_metrics,
    transform_value,
)
from . import log


def _validate_role(role: str) -> str:
    """Validate role parameter to prevent SQL injection."""
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of {VALID_ROLES}")
    return role


# Report metrics use firmware field names (subset of chart metrics for reports)
COMPANION_REPORT_METRICS = [
    "battery_mv", "bat_pct", "contacts", "uptime_secs", "recv", "sent"
]

REPEATER_REPORT_METRICS = [
    "bat", "bat_pct", "last_rssi", "last_snr", "uptime", "noise_floor", "tx_queue_len",
    "nb_recv", "nb_sent", "airtime", "rx_airtime", "flood_dups", "direct_dups",
    "sent_flood", "recv_flood", "sent_direct", "recv_direct"
]


def get_metrics_for_role(role: str) -> list[str]:
    """Get list of metric names for report aggregation (firmware field names)."""
    if role == "companion":
        return COMPANION_REPORT_METRICS
    elif role == "repeater":
        return REPEATER_REPORT_METRICS
    else:
        raise ValueError(f"Unknown role: {role}")


@dataclass
class MetricStats:
    """Statistics for a single metric over a period.

    For gauge metrics: mean, min_value, max_value with timestamps.
    For counter metrics: total (sum of positive deltas), reboot_count.
    """

    mean: Optional[float] = None
    min_value: Optional[float] = None
    min_time: Optional[datetime] = None
    max_value: Optional[float] = None
    max_time: Optional[datetime] = None
    total: Optional[int] = None  # For counters: sum of positive deltas
    count: int = 0
    reboot_count: int = 0  # Number of counter resets detected

    @property
    def has_data(self) -> bool:
        """Return True if any meaningful data was collected."""
        return self.count > 0


@dataclass
class DailyAggregate:
    """Aggregated metrics for a single day."""

    date: date
    metrics: dict[str, MetricStats] = field(default_factory=dict)
    snapshot_count: int = 0


@dataclass
class MonthlyAggregate:
    """Aggregated metrics for a single month."""

    year: int
    month: int
    role: str
    daily: list[DailyAggregate] = field(default_factory=list)
    summary: dict[str, MetricStats] = field(default_factory=dict)


@dataclass
class YearlyAggregate:
    """Aggregated metrics for a full year."""

    year: int
    role: str
    monthly: list[MonthlyAggregate] = field(default_factory=list)
    summary: dict[str, MetricStats] = field(default_factory=dict)


def get_rows_for_date(role: str, d: date) -> list[dict[str, Any]]:
    """Fetch all metric rows for a specific date from the database.

    Converts EAV data back to row-per-timestamp format for aggregation.

    Args:
        role: "companion" or "repeater"
        d: The date to load data for

    Returns:
        List of row dicts (one per timestamp), sorted by timestamp.
        Each dict has 'ts' and all metric values at that timestamp.
    """
    # Calculate timestamp range for the day
    start_dt = datetime.combine(d, datetime.min.time())
    end_dt = datetime.combine(d, datetime.max.time())
    start_ts = int(start_dt.timestamp())
    end_ts = int(end_dt.timestamp())

    # get_metrics_for_period returns dict[metric, list[(ts, value)]]
    metrics_data = get_metrics_for_period(role, start_ts, end_ts)

    # Pivot to row-per-timestamp format
    # Collect all unique timestamps
    all_timestamps: set[int] = set()
    for metric_values in metrics_data.values():
        for ts, _ in metric_values:
            all_timestamps.add(ts)

    if not all_timestamps:
        return []

    # Build row dicts
    rows: dict[int, dict[str, Any]] = {ts: {"ts": ts} for ts in all_timestamps}
    for metric, values in metrics_data.items():
        for ts, value in values:
            rows[ts][metric] = value

    # Return sorted by timestamp
    return [rows[ts] for ts in sorted(all_timestamps)]


def compute_counter_total(
    values: list[tuple[datetime, int]],
) -> tuple[Optional[int], int]:
    """Compute total for a counter metric, handling reboots.

    Sums positive deltas between consecutive readings. Negative deltas
    (indicating device reboot) are skipped, and the reboot count is tracked.

    Args:
        values: List of (timestamp, counter_value) tuples, must be sorted by time

    Returns:
        (total, reboot_count) - total is None if insufficient data (< 2 values)
    """
    if len(values) < 2:
        return (None, 0)

    total = 0
    reboot_count = 0

    for i in range(1, len(values)):
        delta = values[i][1] - values[i - 1][1]
        if delta >= 0:
            total += delta
        else:
            # Negative delta indicates counter reset (reboot)
            reboot_count += 1
            # Count from 0 to current value after reboot
            total += values[i][1]

    return (total, reboot_count)


def _compute_gauge_stats(values: list[tuple[datetime, float]]) -> MetricStats:
    """Compute statistics for a gauge metric.

    Args:
        values: List of (timestamp, value) tuples

    Returns:
        MetricStats with mean, min, max populated
    """
    if not values:
        return MetricStats()

    float_values = [v for _, v in values]
    min_idx = min(range(len(values)), key=lambda i: values[i][1])
    max_idx = max(range(len(values)), key=lambda i: values[i][1])

    return MetricStats(
        mean=sum(float_values) / len(float_values),
        min_value=values[min_idx][1],
        min_time=values[min_idx][0],
        max_value=values[max_idx][1],
        max_time=values[max_idx][0],
        count=len(values),
    )


def _compute_counter_stats(values: list[tuple[datetime, int]]) -> MetricStats:
    """Compute statistics for a counter metric.

    Args:
        values: List of (timestamp, counter_value) tuples

    Returns:
        MetricStats with total and reboot_count populated
    """
    if not values:
        return MetricStats()

    total, reboot_count = compute_counter_total(values)

    return MetricStats(
        total=total,
        count=len(values),
        reboot_count=reboot_count,
    )


def aggregate_daily(role: str, d: date) -> DailyAggregate:
    """Compute daily aggregates from database.

    Args:
        role: "companion" or "repeater"
        d: The date to aggregate

    Returns:
        DailyAggregate with statistics for all configured metrics
    """
    rows = get_rows_for_date(role, d)
    agg = DailyAggregate(date=d, snapshot_count=len(rows))

    if not rows:
        return agg

    metrics = get_metrics_for_role(role)

    # Collect values per metric
    metric_values: dict[str, list[tuple[datetime, Any]]] = {
        m: [] for m in metrics
    }

    for row in rows:
        ts = datetime.fromtimestamp(row["ts"])
        for metric in metrics:
            val = row.get(metric)
            if val is not None:
                metric_values[metric].append((ts, val))

    # Compute stats per metric
    for metric, values in metric_values.items():
        if not values:
            continue

        if is_counter_metric(metric):
            # Convert to int for counter processing
            int_values = [(ts, int(v)) for ts, v in values]
            agg.metrics[metric] = _compute_counter_stats(int_values)
        else:
            # Keep as float for gauge processing
            float_values = [(ts, float(v)) for ts, v in values]
            agg.metrics[metric] = _compute_gauge_stats(float_values)

    return agg


def _aggregate_daily_gauge_to_summary(
    daily_list: list[DailyAggregate], ds_name: str
) -> MetricStats:
    """Aggregate daily gauge stats into a period summary.

    Computes overall mean (weighted by count), min, and max across all days.
    """
    total_sum = 0.0
    total_count = 0
    overall_min: Optional[tuple[float, datetime]] = None
    overall_max: Optional[tuple[float, datetime]] = None

    for daily in daily_list:
        if ds_name not in daily.metrics or not daily.metrics[ds_name].has_data:
            continue

        stats = daily.metrics[ds_name]

        # Accumulate for weighted mean
        if stats.mean is not None and stats.count > 0:
            total_sum += stats.mean * stats.count
            total_count += stats.count

        # Track overall min
        if stats.min_value is not None and stats.min_time is not None:
            if overall_min is None or stats.min_value < overall_min[0]:
                overall_min = (stats.min_value, stats.min_time)

        # Track overall max
        if stats.max_value is not None and stats.max_time is not None:
            if overall_max is None or stats.max_value > overall_max[0]:
                overall_max = (stats.max_value, stats.max_time)

    if total_count == 0:
        return MetricStats()

    return MetricStats(
        mean=total_sum / total_count,
        min_value=overall_min[0] if overall_min else None,
        min_time=overall_min[1] if overall_min else None,
        max_value=overall_max[0] if overall_max else None,
        max_time=overall_max[1] if overall_max else None,
        count=total_count,
    )


def _aggregate_daily_counter_to_summary(
    daily_list: list[DailyAggregate], ds_name: str
) -> MetricStats:
    """Aggregate daily counter stats into a period summary.

    Sums totals and reboot counts across all days.
    """
    total = 0
    total_count = 0
    total_reboots = 0

    for daily in daily_list:
        if ds_name not in daily.metrics or not daily.metrics[ds_name].has_data:
            continue

        stats = daily.metrics[ds_name]
        if stats.total is not None:
            total += stats.total
            total_count += stats.count
            total_reboots += stats.reboot_count

    if total_count == 0:
        return MetricStats()

    return MetricStats(
        total=total,
        count=total_count,
        reboot_count=total_reboots,
    )


def aggregate_monthly(role: str, year: int, month: int) -> MonthlyAggregate:
    """Compute monthly aggregates from daily data.

    Args:
        role: "companion" or "repeater"
        year: Year to aggregate
        month: Month to aggregate (1-12)

    Returns:
        MonthlyAggregate with daily data and summary statistics
    """
    agg = MonthlyAggregate(year=year, month=month, role=role)
    metrics = get_metrics_for_role(role)

    # Iterate all days in month
    _, days_in_month = calendar.monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        # Don't aggregate future dates
        if d > date.today():
            break
        daily = aggregate_daily(role, d)
        if daily.snapshot_count > 0:
            agg.daily.append(daily)

    # Compute monthly summary from daily data
    for metric in metrics:
        if is_counter_metric(metric):
            agg.summary[metric] = _aggregate_daily_counter_to_summary(
                agg.daily, metric
            )
        else:
            agg.summary[metric] = _aggregate_daily_gauge_to_summary(agg.daily, metric)

    return agg


def _aggregate_monthly_gauge_to_summary(
    monthly_list: list[MonthlyAggregate], ds_name: str
) -> MetricStats:
    """Aggregate monthly gauge stats into a yearly summary."""
    total_sum = 0.0
    total_count = 0
    overall_min: Optional[tuple[float, datetime]] = None
    overall_max: Optional[tuple[float, datetime]] = None

    for monthly in monthly_list:
        if ds_name not in monthly.summary or not monthly.summary[ds_name].has_data:
            continue

        stats = monthly.summary[ds_name]

        if stats.mean is not None and stats.count > 0:
            total_sum += stats.mean * stats.count
            total_count += stats.count

        if stats.min_value is not None and stats.min_time is not None:
            if overall_min is None or stats.min_value < overall_min[0]:
                overall_min = (stats.min_value, stats.min_time)

        if stats.max_value is not None and stats.max_time is not None:
            if overall_max is None or stats.max_value > overall_max[0]:
                overall_max = (stats.max_value, stats.max_time)

    if total_count == 0:
        return MetricStats()

    return MetricStats(
        mean=total_sum / total_count,
        min_value=overall_min[0] if overall_min else None,
        min_time=overall_min[1] if overall_min else None,
        max_value=overall_max[0] if overall_max else None,
        max_time=overall_max[1] if overall_max else None,
        count=total_count,
    )


def _aggregate_monthly_counter_to_summary(
    monthly_list: list[MonthlyAggregate], ds_name: str
) -> MetricStats:
    """Aggregate monthly counter stats into a yearly summary."""
    total = 0
    total_count = 0
    total_reboots = 0

    for monthly in monthly_list:
        if ds_name not in monthly.summary or not monthly.summary[ds_name].has_data:
            continue

        stats = monthly.summary[ds_name]
        if stats.total is not None:
            total += stats.total
            total_count += stats.count
            total_reboots += stats.reboot_count

    if total_count == 0:
        return MetricStats()

    return MetricStats(
        total=total,
        count=total_count,
        reboot_count=total_reboots,
    )


def aggregate_yearly(role: str, year: int) -> YearlyAggregate:
    """Compute yearly aggregates from monthly data.

    Args:
        role: "companion" or "repeater"
        year: Year to aggregate

    Returns:
        YearlyAggregate with monthly data and summary statistics
    """
    agg = YearlyAggregate(year=year, role=role)
    metrics = get_metrics_for_role(role)

    # Process month by month to limit memory usage
    for month in range(1, 13):
        # Don't aggregate future months
        if date(year, month, 1) > date.today():
            break
        monthly = aggregate_monthly(role, year, month)
        if monthly.daily:  # Has data
            agg.monthly.append(monthly)

    # Compute yearly summary from monthly summaries
    for metric in metrics:
        if is_counter_metric(metric):
            agg.summary[metric] = _aggregate_monthly_counter_to_summary(
                agg.monthly, metric
            )
        else:
            agg.summary[metric] = _aggregate_monthly_gauge_to_summary(
                agg.monthly, metric
            )

    return agg


def get_available_periods(role: str) -> list[tuple[int, int]]:
    """Find all year/month combinations with data in the database.

    Args:
        role: "companion" or "repeater"

    Returns:
        Sorted list of (year, month) tuples

    Raises:
        ValueError: If role is not valid
    """
    role = _validate_role(role)

    with get_connection(readonly=True) as conn:
        cursor = conn.execute("""
            SELECT DISTINCT
                strftime('%Y', ts, 'unixepoch') as year,
                strftime('%m', ts, 'unixepoch') as month
            FROM metrics
            WHERE role = ?
            ORDER BY year, month
        """, (role,))
        return [(int(row[0]), int(row[1])) for row in cursor.fetchall()]


def format_lat_lon(lat: float, lon: float) -> tuple[str, str]:
    """Convert decimal degrees to degrees-minutes format for TXT reports.

    Args:
        lat: Latitude in decimal degrees (positive = North)
        lon: Longitude in decimal degrees (positive = East)

    Returns:
        (lat_str, lon_str) in format "DD-MM.MM N/S", "DDD-MM.MM E/W"
    """
    # Latitude
    lat_dir = "N" if lat >= 0 else "S"
    lat_abs = abs(lat)
    lat_deg = int(lat_abs)
    lat_min = (lat_abs - lat_deg) * 60
    lat_str = f"{lat_deg:02d}-{lat_min:05.2f} {lat_dir}"

    # Longitude
    lon_dir = "E" if lon >= 0 else "W"
    lon_abs = abs(lon)
    lon_deg = int(lon_abs)
    lon_min = (lon_abs - lon_deg) * 60
    lon_str = f"{lon_deg:03d}-{lon_min:05.2f} {lon_dir}"

    return (lat_str, lon_str)


def format_lat_lon_dms(lat: float, lon: float) -> str:
    """Convert decimal degrees to degrees-minutes-seconds format for HTML reports.

    Args:
        lat: Latitude in decimal degrees (positive = North)
        lon: Longitude in decimal degrees (positive = East)

    Returns:
        Combined string in format "DD°MM'SS\"N  DDD°MM'SS\"E"
    """
    def to_dms(coord: float, is_lat: bool) -> str:
        """Convert a single coordinate to DMS format."""
        if is_lat:
            direction = "N" if coord >= 0 else "S"
            deg_width = 2
        else:
            direction = "E" if coord >= 0 else "W"
            deg_width = 3

        coord_abs = abs(coord)
        degrees = int(coord_abs)
        minutes_float = (coord_abs - degrees) * 60
        minutes = int(minutes_float)
        seconds = int((minutes_float - minutes) * 60)

        return f"{degrees:0{deg_width}d}°{minutes:02d}'{seconds:02d}\"{direction}"

    lat_str = to_dms(lat, is_lat=True)
    lon_str = to_dms(lon, is_lat=False)

    return f"{lat_str}  {lon_str}"


@dataclass
class LocationInfo:
    """Location metadata for reports."""

    name: str
    lat: float
    lon: float
    elev: float  # meters

    def format_header(self) -> str:
        """Format location header for text reports."""
        coords_str = format_lat_lon_dms(self.lat, self.lon)
        return (
            f"NAME: {self.name}\n"
            f"COORDS: {coords_str}    ELEV: {self.elev:.0f} meters"
        )


def _fmt_val(val: Optional[float], width: int = 6, decimals: int = 1) -> str:
    """Format a value with fixed width, or dashes if None."""
    if val is None:
        return "-".center(width)
    return f"{val:>{width}.{decimals}f}"


def _fmt_int(val: Optional[int], width: int = 6) -> str:
    """Format an integer with fixed width and comma separators, or dashes if None."""
    if val is None:
        return "-".center(width)
    return f"{val:>{width},}"


def _fmt_time(dt: Optional[datetime], fmt: str = "%H:%M") -> str:
    """Format a datetime, or dashes if None."""
    if dt is None:
        return "--:--"
    return dt.strftime(fmt)


def _fmt_day(dt: Optional[datetime]) -> str:
    """Format datetime as day number, or dashes if None."""
    if dt is None:
        return "--"
    return f"{dt.day:02d}"


# --- Fixed-width column formatting for yearly reports ---


@dataclass
class Column:
    """Define a fixed-width column for ASCII table formatting."""

    width: int
    align: str = "right"  # "left", "right", or "center"
    decimals: int = 0  # For float formatting
    comma_sep: bool = False  # Use comma separators for large integers

    def format(self, value: Any) -> str:
        """Format a value to fit this column width."""
        if value is None:
            text = "-"
        elif isinstance(value, int):
            if self.comma_sep:
                text = f"{value:,}"
            else:
                text = str(value)
        elif isinstance(value, float):
            text = f"{value:.{self.decimals}f}"
        else:
            text = str(value)

        if self.align == "left":
            return text.ljust(self.width)
        elif self.align == "center":
            return text.center(self.width)
        else:  # right
            return text.rjust(self.width)


def _format_row(columns: list[Column], values: list[Any]) -> str:
    """Format a row of values using column specs."""
    return "".join(col.format(val) for col, val in zip(columns, values))


def _format_separator(columns: list[Column], char: str = "-") -> str:
    """Generate a separator line matching total width."""
    return char * sum(col.width for col in columns)


def _get_bat_v(m: dict[str, MetricStats], role: str) -> MetricStats:
    """Get battery voltage stats, converting from millivolts to volts.

    Args:
        m: Metrics dict
        role: 'companion' or 'repeater'

    Returns:
        MetricStats with values in volts
    """
    if role == "companion":
        bat = m.get("battery_mv", MetricStats())
    else:
        bat = m.get("bat", MetricStats())

    if not bat.has_data:
        return bat

    # Convert mV to V
    return MetricStats(
        mean=bat.mean / 1000.0 if bat.mean is not None else None,
        min_value=bat.min_value / 1000.0 if bat.min_value is not None else None,
        min_time=bat.min_time,
        max_value=bat.max_value / 1000.0 if bat.max_value is not None else None,
        max_time=bat.max_time,
        count=bat.count,
    )


def format_monthly_txt_repeater(
    agg: MonthlyAggregate, node_name: str, location: LocationInfo
) -> str:
    """Format monthly aggregate as WeeWX-style text report for repeater.

    Args:
        agg: Monthly aggregate data
        node_name: Name of the repeater node
        location: Location metadata

    Returns:
        Formatted text report string
    """
    month_name = calendar.month_name[agg.month]
    lines = []

    # Header
    lines.append(f"                   MONTHLY MESHCORE REPORT for {month_name} {agg.year}")
    lines.append("")
    lines.append(f"NODE: {node_name}")
    lines.append(location.format_header())
    lines.append("")

    # Table header
    lines.append("                   BATTERY (V)                    SIGNAL                PACKETS        AIR")
    lines.append("      MEAN              MIN              MAX      RSSI   SNR    NOISE    RX      TX    SECS")
    lines.append("DAY   VOLT   %     VOLT  TIME     VOLT  TIME      dBm    dB      dBm")
    lines.append("-" * 95)

    # Daily rows
    for daily in agg.daily:
        day_num = daily.date.day
        m = daily.metrics

        # Battery (firmware: bat in mV, bat_pct computed)
        bat_v = _get_bat_v(m, "repeater")
        bat_pct = m.get("bat_pct", MetricStats())

        # Signal (firmware: last_rssi, last_snr, noise_floor)
        rssi = m.get("last_rssi", MetricStats())
        snr = m.get("last_snr", MetricStats())
        noise = m.get("noise_floor", MetricStats())

        # Packets (firmware: nb_recv, nb_sent, airtime)
        rx = m.get("nb_recv", MetricStats())
        tx = m.get("nb_sent", MetricStats())
        airtime = m.get("airtime", MetricStats())

        line = (
            f"{day_num:3d}  "
            f"{_fmt_val(bat_v.mean, 5, 2)}  {_fmt_val(bat_pct.mean, 3, 0)}  "
            f"{_fmt_val(bat_v.min_value, 5, 2)}  {_fmt_time(bat_v.min_time)}  "
            f"{_fmt_val(bat_v.max_value, 5, 2)}  {_fmt_time(bat_v.max_time)}  "
            f"{_fmt_val(rssi.mean, 5, 0)}  {_fmt_val(snr.mean, 4, 1)}  {_fmt_val(noise.mean, 5, 0)}  "
            f"{_fmt_int(rx.total, 7)}  {_fmt_int(tx.total, 6)}  {_fmt_int(airtime.total, 5)}"
        )
        lines.append(line)

    # Summary row
    lines.append("-" * 95)
    s = agg.summary
    bat_v = _get_bat_v(s, "repeater")
    bat_pct = s.get("bat_pct", MetricStats())
    rssi = s.get("last_rssi", MetricStats())
    snr = s.get("last_snr", MetricStats())
    noise = s.get("noise_floor", MetricStats())
    rx = s.get("nb_recv", MetricStats())
    tx = s.get("nb_sent", MetricStats())
    airtime = s.get("airtime", MetricStats())

    summary_line = (
        f"AVG  "
        f"{_fmt_val(bat_v.mean, 5, 2)}  {_fmt_val(bat_pct.mean, 3, 0)}  "
        f"{_fmt_val(bat_v.min_value, 5, 2)}  {_fmt_day(bat_v.min_time)}     "
        f"{_fmt_val(bat_v.max_value, 5, 2)}  {_fmt_day(bat_v.max_time)}     "
        f"{_fmt_val(rssi.mean, 5, 0)}  {_fmt_val(snr.mean, 4, 1)}  {_fmt_val(noise.mean, 5, 0)}  "
        f"{_fmt_int(rx.total, 7)}  {_fmt_int(tx.total, 6)}  {_fmt_int(airtime.total, 5)}"
    )
    lines.append(summary_line)

    return "\n".join(lines)


def format_monthly_txt_companion(
    agg: MonthlyAggregate, node_name: str, location: LocationInfo
) -> str:
    """Format monthly aggregate as WeeWX-style text report for companion.

    Args:
        agg: Monthly aggregate data
        node_name: Name of the companion node
        location: Location metadata

    Returns:
        Formatted text report string
    """
    month_name = calendar.month_name[agg.month]
    lines = []

    # Header
    lines.append(f"                   MONTHLY MESHCORE REPORT for {month_name} {agg.year}")
    lines.append("")
    lines.append(f"NODE: {node_name}")
    lines.append(location.format_header())
    lines.append("")

    # Table header - companion has fewer metrics
    lines.append("                   BATTERY (V)                            PACKETS")
    lines.append("      MEAN              MIN              MAX      CONTACTS    RX      TX")
    lines.append("DAY   VOLT   %     VOLT  TIME     VOLT  TIME")
    lines.append("-" * 75)

    # Daily rows
    for daily in agg.daily:
        day_num = daily.date.day
        m = daily.metrics

        # Firmware: battery_mv, bat_pct (computed), contacts, recv, sent
        bat_v = _get_bat_v(m, "companion")
        bat_pct = m.get("bat_pct", MetricStats())
        contacts = m.get("contacts", MetricStats())
        rx = m.get("recv", MetricStats())
        tx = m.get("sent", MetricStats())

        line = (
            f"{day_num:3d}  "
            f"{_fmt_val(bat_v.mean, 5, 2)}  {_fmt_val(bat_pct.mean, 3, 0)}  "
            f"{_fmt_val(bat_v.min_value, 5, 2)}  {_fmt_time(bat_v.min_time)}  "
            f"{_fmt_val(bat_v.max_value, 5, 2)}  {_fmt_time(bat_v.max_time)}  "
            f"{_fmt_val(contacts.mean, 6, 0)}  "
            f"{_fmt_int(rx.total, 7)}  {_fmt_int(tx.total, 6)}"
        )
        lines.append(line)

    # Summary row
    lines.append("-" * 75)
    s = agg.summary
    bat_v = _get_bat_v(s, "companion")
    bat_pct = s.get("bat_pct", MetricStats())
    contacts = s.get("contacts", MetricStats())
    rx = s.get("recv", MetricStats())
    tx = s.get("sent", MetricStats())

    summary_line = (
        f"AVG  "
        f"{_fmt_val(bat_v.mean, 5, 2)}  {_fmt_val(bat_pct.mean, 3, 0)}  "
        f"{_fmt_val(bat_v.min_value, 5, 2)}  {_fmt_day(bat_v.min_time)}     "
        f"{_fmt_val(bat_v.max_value, 5, 2)}  {_fmt_day(bat_v.max_time)}     "
        f"{_fmt_val(contacts.mean, 6, 0)}  "
        f"{_fmt_int(rx.total, 7)}  {_fmt_int(tx.total, 6)}"
    )
    lines.append(summary_line)

    return "\n".join(lines)


def format_monthly_txt(
    agg: MonthlyAggregate, node_name: str, location: LocationInfo
) -> str:
    """Format monthly aggregate as WeeWX-style text report.

    Dispatches to role-specific formatter.

    Args:
        agg: Monthly aggregate data
        node_name: Name of the node
        location: Location metadata

    Returns:
        Formatted text report string
    """
    if agg.role == "repeater":
        return format_monthly_txt_repeater(agg, node_name, location)
    else:
        return format_monthly_txt_companion(agg, node_name, location)


def format_yearly_txt_repeater(
    agg: YearlyAggregate, node_name: str, location: LocationInfo
) -> str:
    """Format yearly aggregate as WeeWX-style text report for repeater.

    Args:
        agg: Yearly aggregate data
        node_name: Name of the repeater node
        location: Location metadata

    Returns:
        Formatted text report string
    """
    # Define column layout - all rows will use these exact widths
    # YR MO | VOLT % | HIGH DAY | LOW DAY | RSSI SNR | RX TX
    cols = [
        Column(4),                        # YR
        Column(4),                        # MO
        Column(6, decimals=2),            # VOLT (mean)
        Column(4),                        # % (bat_pct)
        Column(6, decimals=2),            # HIGH (max volt)
        Column(4),                        # DAY (max day)
        Column(6, decimals=2),            # LOW (min volt)
        Column(4),                        # DAY (min day)
        Column(6),                        # RSSI
        Column(6, decimals=1),            # SNR
        Column(11, comma_sep=True),       # RX
        Column(9, comma_sep=True),        # TX
    ]

    lines = []

    # Header
    title = f"YEARLY MESHCORE REPORT for {agg.year}"
    lines.append(title.center(sum(c.width for c in cols)))
    lines.append("")
    lines.append(f"NODE: {node_name}")
    lines.append(location.format_header())
    lines.append("")

    # Table headers - use same column widths
    lines.append(_format_row(cols, [
        "", "", "BATTERY", "", "", "", "", "", "SIGNAL", "", "PACKETS", ""
    ]))
    lines.append(_format_row(cols, [
        "YR", "MO", "VOLT", "%", "HIGH", "DAY", "LOW", "DAY", "RSSI", "SNR", "RX", "TX"
    ]))
    lines.append(_format_separator(cols))

    # Monthly rows
    for monthly in agg.monthly:
        s = monthly.summary
        # Firmware: bat (mV), bat_pct, last_rssi, last_snr, nb_recv, nb_sent
        bat_v = _get_bat_v(s, "repeater")
        bat_pct = s.get("bat_pct", MetricStats())
        rssi = s.get("last_rssi", MetricStats())
        snr = s.get("last_snr", MetricStats())
        rx = s.get("nb_recv", MetricStats())
        tx = s.get("nb_sent", MetricStats())

        # Format day as 2-digit number
        max_day = f"{bat_v.max_time.day:02d}" if bat_v.max_time else "--"
        min_day = f"{bat_v.min_time.day:02d}" if bat_v.min_time else "--"

        lines.append(_format_row(cols, [
            agg.year,
            f"{monthly.month:02d}",
            bat_v.mean,
            int(bat_pct.mean) if bat_pct.mean is not None else None,
            bat_v.max_value,
            max_day,
            bat_v.min_value,
            min_day,
            int(rssi.mean) if rssi.mean is not None else None,
            snr.mean,
            rx.total,
            tx.total,
        ]))

    # Summary row
    lines.append(_format_separator(cols))
    s = agg.summary
    bat_v = _get_bat_v(s, "repeater")
    bat_pct = s.get("bat_pct", MetricStats())
    rssi = s.get("last_rssi", MetricStats())
    snr = s.get("last_snr", MetricStats())
    rx = s.get("nb_recv", MetricStats())
    tx = s.get("nb_sent", MetricStats())

    max_month = calendar.month_abbr[bat_v.max_time.month] if bat_v.max_time else "---"
    min_month = calendar.month_abbr[bat_v.min_time.month] if bat_v.min_time else "---"

    lines.append(_format_row(cols, [
        "",
        "AVG",
        bat_v.mean,
        int(bat_pct.mean) if bat_pct.mean is not None else None,
        bat_v.max_value,
        max_month,
        bat_v.min_value,
        min_month,
        int(rssi.mean) if rssi.mean is not None else None,
        snr.mean,
        rx.total,
        tx.total,
    ]))

    return "\n".join(lines)


def format_yearly_txt_companion(
    agg: YearlyAggregate, node_name: str, location: LocationInfo
) -> str:
    """Format yearly aggregate as WeeWX-style text report for companion.

    Args:
        agg: Yearly aggregate data
        node_name: Name of the companion node
        location: Location metadata

    Returns:
        Formatted text report string
    """
    # Define column layout - all rows will use these exact widths
    # YR MO | VOLT % | HIGH DAY | LOW DAY | CNTS | RX TX
    cols = [
        Column(4),                        # YR
        Column(4),                        # MO
        Column(6, decimals=2),            # VOLT (mean)
        Column(4),                        # % (bat_pct)
        Column(6, decimals=2),            # HIGH (max volt)
        Column(4),                        # DAY (max day)
        Column(6, decimals=2),            # LOW (min volt)
        Column(4),                        # DAY (min day)
        Column(6),                        # CNTS (contacts)
        Column(11, comma_sep=True),       # RX
        Column(9, comma_sep=True),        # TX
    ]

    lines = []

    # Header
    title = f"YEARLY MESHCORE REPORT for {agg.year}"
    lines.append(title.center(sum(c.width for c in cols)))
    lines.append("")
    lines.append(f"NODE: {node_name}")
    lines.append(location.format_header())
    lines.append("")

    # Table headers - use same column widths
    lines.append(_format_row(cols, [
        "", "", "BATTERY", "", "", "", "", "", "", "PACKETS", ""
    ]))
    lines.append(_format_row(cols, [
        "YR", "MO", "VOLT", "%", "HIGH", "DAY", "LOW", "DAY", "CNTS", "RX", "TX"
    ]))
    lines.append(_format_separator(cols))

    # Monthly rows
    for monthly in agg.monthly:
        s = monthly.summary
        # Firmware: battery_mv, bat_pct, contacts, recv, sent
        bat_v = _get_bat_v(s, "companion")
        bat_pct = s.get("bat_pct", MetricStats())
        contacts = s.get("contacts", MetricStats())
        rx = s.get("recv", MetricStats())
        tx = s.get("sent", MetricStats())

        max_day = f"{bat_v.max_time.day:02d}" if bat_v.max_time else "--"
        min_day = f"{bat_v.min_time.day:02d}" if bat_v.min_time else "--"

        lines.append(_format_row(cols, [
            agg.year,
            f"{monthly.month:02d}",
            bat_v.mean,
            int(bat_pct.mean) if bat_pct.mean is not None else None,
            bat_v.max_value,
            max_day,
            bat_v.min_value,
            min_day,
            int(contacts.mean) if contacts.mean is not None else None,
            rx.total,
            tx.total,
        ]))

    # Summary row
    lines.append(_format_separator(cols))
    s = agg.summary
    bat_v = _get_bat_v(s, "companion")
    bat_pct = s.get("bat_pct", MetricStats())
    contacts = s.get("contacts", MetricStats())
    rx = s.get("recv", MetricStats())
    tx = s.get("sent", MetricStats())

    max_month = calendar.month_abbr[bat_v.max_time.month] if bat_v.max_time else "---"
    min_month = calendar.month_abbr[bat_v.min_time.month] if bat_v.min_time else "---"

    lines.append(_format_row(cols, [
        "",
        "AVG",
        bat_v.mean,
        int(bat_pct.mean) if bat_pct.mean is not None else None,
        bat_v.max_value,
        max_month,
        bat_v.min_value,
        min_month,
        int(contacts.mean) if contacts.mean is not None else None,
        rx.total,
        tx.total,
    ]))

    return "\n".join(lines)


def format_yearly_txt(
    agg: YearlyAggregate, node_name: str, location: LocationInfo
) -> str:
    """Format yearly aggregate as WeeWX-style text report.

    Dispatches to role-specific formatter.

    Args:
        agg: Yearly aggregate data
        node_name: Name of the node
        location: Location metadata

    Returns:
        Formatted text report string
    """
    if agg.role == "repeater":
        return format_yearly_txt_repeater(agg, node_name, location)
    else:
        return format_yearly_txt_companion(agg, node_name, location)


def _metric_stats_to_dict(stats: MetricStats) -> dict[str, Any]:
    """Convert MetricStats to JSON-serializable dict."""
    result: dict[str, Any] = {"count": stats.count}

    if stats.mean is not None:
        result["mean"] = round(stats.mean, 4)
    if stats.min_value is not None:
        result["min"] = round(stats.min_value, 4)
    if stats.min_time is not None:
        result["min_time"] = stats.min_time.isoformat()
    if stats.max_value is not None:
        result["max"] = round(stats.max_value, 4)
    if stats.max_time is not None:
        result["max_time"] = stats.max_time.isoformat()
    if stats.total is not None:
        result["total"] = stats.total
    if stats.reboot_count > 0:
        result["reboot_count"] = stats.reboot_count

    return result


def _daily_to_dict(daily: DailyAggregate) -> dict[str, Any]:
    """Convert DailyAggregate to JSON-serializable dict."""
    return {
        "date": daily.date.isoformat(),
        "snapshot_count": daily.snapshot_count,
        "metrics": {
            ds: _metric_stats_to_dict(stats)
            for ds, stats in daily.metrics.items()
            if stats.has_data
        },
    }


def monthly_to_json(agg: MonthlyAggregate) -> dict[str, Any]:
    """Convert MonthlyAggregate to JSON-serializable dict.

    Args:
        agg: Monthly aggregate data

    Returns:
        JSON-serializable dict
    """
    return {
        "report_type": "monthly",
        "year": agg.year,
        "month": agg.month,
        "role": agg.role,
        "days_with_data": len(agg.daily),
        "summary": {
            ds: _metric_stats_to_dict(stats)
            for ds, stats in agg.summary.items()
            if stats.has_data
        },
        "daily": [_daily_to_dict(d) for d in agg.daily],
    }


def yearly_to_json(agg: YearlyAggregate) -> dict[str, Any]:
    """Convert YearlyAggregate to JSON-serializable dict.

    Args:
        agg: Yearly aggregate data

    Returns:
        JSON-serializable dict
    """
    return {
        "report_type": "yearly",
        "year": agg.year,
        "role": agg.role,
        "months_with_data": len(agg.monthly),
        "summary": {
            ds: _metric_stats_to_dict(stats)
            for ds, stats in agg.summary.items()
            if stats.has_data
        },
        "monthly": [
            {
                "year": m.year,
                "month": m.month,
                "days_with_data": len(m.daily),
                "summary": {
                    ds: _metric_stats_to_dict(stats)
                    for ds, stats in m.summary.items()
                    if stats.has_data
                },
            }
            for m in agg.monthly
        ],
    }
