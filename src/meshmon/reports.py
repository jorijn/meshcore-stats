"""Report generation (WeeWX-style).

This module provides functionality to generate monthly and yearly
reports from snapshot data. Reports are generated in TXT (WeeWX-style
ASCII tables), JSON, and HTML formats.

Counter metrics (rx, tx, airtime, etc.) are aggregated using absolute
counter values from snapshots, summing positive deltas to handle device
reboots gracefully.
"""

import calendar
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .env import get_config
from .extract import get_by_path
from .jsondump import load_snapshot
from .metrics import is_counter_metric
from .snapshot import build_companion_merged_view, build_repeater_merged_view
from . import log


# Role-specific merged view builders
ROLE_BUILDERS = {
    "companion": build_companion_merged_view,
    "repeater": build_repeater_merged_view,
}


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


def get_merged_view_builder(role: str):
    """Get the appropriate merged view builder for a role.

    Args:
        role: "companion" or "repeater"

    Returns:
        Function that builds merged view from snapshot

    Raises:
        ValueError: If role is unknown
    """
    if role not in ROLE_BUILDERS:
        raise ValueError(f"Unknown role: {role}")
    return ROLE_BUILDERS[role]


def get_snapshots_for_date(role: str, d: date) -> list[tuple[Path, dict[str, Any]]]:
    """Load all valid snapshots for a specific date.

    Skips snapshots with skip_reason (circuit breaker, etc.) and
    snapshots that fail to load.

    Args:
        role: "companion" or "repeater"
        d: The date to load snapshots for

    Returns:
        List of (path, snapshot_data) tuples, sorted by timestamp
    """
    cfg = get_config()
    day_dir = cfg.snapshot_dir / role / f"{d.year}" / f"{d.month:02d}" / f"{d.day:02d}"

    if not day_dir.exists():
        return []

    snapshots = []
    skipped_count = 0

    for json_file in sorted(day_dir.glob("*.json")):
        data = load_snapshot(json_file)
        if data is None:
            skipped_count += 1
            continue
        if data.get("skip_reason"):
            # Circuit breaker skip - expected, don't count as error
            continue
        if not data.get("ts"):
            log.debug(f"Snapshot missing timestamp: {json_file}")
            skipped_count += 1
            continue
        snapshots.append((json_file, data))

    if skipped_count > 0:
        log.debug(f"Skipped {skipped_count} invalid snapshots for {role}/{d}")

    return snapshots


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


def aggregate_daily(
    role: str, d: date, metrics_config: dict[str, str]
) -> DailyAggregate:
    """Compute daily aggregates from snapshots.

    Args:
        role: "companion" or "repeater"
        d: The date to aggregate
        metrics_config: Mapping of ds_name -> dotted_path

    Returns:
        DailyAggregate with statistics for all configured metrics
    """
    snapshots = get_snapshots_for_date(role, d)
    agg = DailyAggregate(date=d, snapshot_count=len(snapshots))

    if not snapshots:
        return agg

    # Get the appropriate builder for this role
    build_fn = get_merged_view_builder(role)
    merged_snapshots = [(path, build_fn(data)) for path, data in snapshots]

    # Collect values per metric
    metric_values: dict[str, list[tuple[datetime, Any]]] = {
        ds: [] for ds in metrics_config
    }

    for path, merged in merged_snapshots:
        ts = datetime.fromtimestamp(merged["ts"])
        for ds_name, dotted_path in metrics_config.items():
            val = get_by_path(merged, dotted_path)
            if val is not None:
                metric_values[ds_name].append((ts, val))

    # Compute stats per metric
    for ds_name, values in metric_values.items():
        if not values:
            continue

        if is_counter_metric(ds_name):
            # Convert to int for counter processing
            int_values = [(ts, int(v)) for ts, v in values]
            agg.metrics[ds_name] = _compute_counter_stats(int_values)
        else:
            # Keep as float for gauge processing
            float_values = [(ts, float(v)) for ts, v in values]
            agg.metrics[ds_name] = _compute_gauge_stats(float_values)

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


def aggregate_monthly(
    role: str, year: int, month: int, metrics_config: dict[str, str]
) -> MonthlyAggregate:
    """Compute monthly aggregates from daily data.

    Args:
        role: "companion" or "repeater"
        year: Year to aggregate
        month: Month to aggregate (1-12)
        metrics_config: Mapping of ds_name -> dotted_path

    Returns:
        MonthlyAggregate with daily data and summary statistics
    """
    agg = MonthlyAggregate(year=year, month=month, role=role)

    # Iterate all days in month
    _, days_in_month = calendar.monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        # Don't aggregate future dates
        if d > date.today():
            break
        daily = aggregate_daily(role, d, metrics_config)
        if daily.snapshot_count > 0:
            agg.daily.append(daily)

    # Compute monthly summary from daily data
    for ds_name in metrics_config:
        if is_counter_metric(ds_name):
            agg.summary[ds_name] = _aggregate_daily_counter_to_summary(
                agg.daily, ds_name
            )
        else:
            agg.summary[ds_name] = _aggregate_daily_gauge_to_summary(agg.daily, ds_name)

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


def aggregate_yearly(
    role: str, year: int, metrics_config: dict[str, str]
) -> YearlyAggregate:
    """Compute yearly aggregates from monthly data.

    Args:
        role: "companion" or "repeater"
        year: Year to aggregate
        metrics_config: Mapping of ds_name -> dotted_path

    Returns:
        YearlyAggregate with monthly data and summary statistics
    """
    agg = YearlyAggregate(year=year, role=role)

    # Process month by month to limit memory usage
    for month in range(1, 13):
        # Don't aggregate future months
        if date(year, month, 1) > date.today():
            break
        monthly = aggregate_monthly(role, year, month, metrics_config)
        if monthly.daily:  # Has data
            agg.monthly.append(monthly)

    # Compute yearly summary from monthly summaries
    for ds_name in metrics_config:
        if is_counter_metric(ds_name):
            agg.summary[ds_name] = _aggregate_monthly_counter_to_summary(
                agg.monthly, ds_name
            )
        else:
            agg.summary[ds_name] = _aggregate_monthly_gauge_to_summary(
                agg.monthly, ds_name
            )

    return agg


def get_available_periods(role: str) -> list[tuple[int, int]]:
    """Find all year/month combinations with snapshot data.

    Args:
        role: "companion" or "repeater"

    Returns:
        Sorted list of (year, month) tuples
    """
    cfg = get_config()
    base = cfg.snapshot_dir / role

    if not base.exists():
        return []

    periods = set()
    for year_dir in base.glob("*"):
        if not year_dir.is_dir() or not year_dir.name.isdigit():
            continue
        year = int(year_dir.name)
        for month_dir in year_dir.glob("*"):
            if not month_dir.is_dir() or not month_dir.name.isdigit():
                continue
            month = int(month_dir.name)
            if 1 <= month <= 12:
                periods.add((year, month))

    return sorted(periods)


def format_lat_lon(lat: float, lon: float) -> tuple[str, str]:
    """Convert decimal degrees to degrees-minutes format.

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


@dataclass
class LocationInfo:
    """Location metadata for reports."""

    name: str
    lat: float
    lon: float
    elev: float  # meters

    def format_header(self) -> str:
        """Format location header for text reports."""
        lat_str, lon_str = format_lat_lon(self.lat, self.lon)
        return (
            f"NAME: {self.name}\n"
            f"ELEV: {self.elev:.0f} meters    LAT: {lat_str}    LONG: {lon_str}"
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

        # Battery
        bat_v = m.get("bat_v", MetricStats())
        bat_pct = m.get("bat_pct", MetricStats())

        # Signal
        rssi = m.get("rssi", MetricStats())
        snr = m.get("snr", MetricStats())
        noise = m.get("noise", MetricStats())

        # Packets (counters)
        rx = m.get("rx", MetricStats())
        tx = m.get("tx", MetricStats())
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
    bat_v = s.get("bat_v", MetricStats())
    bat_pct = s.get("bat_pct", MetricStats())
    rssi = s.get("rssi", MetricStats())
    snr = s.get("snr", MetricStats())
    noise = s.get("noise", MetricStats())
    rx = s.get("rx", MetricStats())
    tx = s.get("tx", MetricStats())
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

        bat_v = m.get("bat_v", MetricStats())
        bat_pct = m.get("bat_pct", MetricStats())
        contacts = m.get("contacts", MetricStats())
        rx = m.get("rx", MetricStats())
        tx = m.get("tx", MetricStats())

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
    bat_v = s.get("bat_v", MetricStats())
    bat_pct = s.get("bat_pct", MetricStats())
    contacts = s.get("contacts", MetricStats())
    rx = s.get("rx", MetricStats())
    tx = s.get("tx", MetricStats())

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
        bat_v = s.get("bat_v", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        rssi = s.get("rssi", MetricStats())
        snr = s.get("snr", MetricStats())
        rx = s.get("rx", MetricStats())
        tx = s.get("tx", MetricStats())

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
    bat_v = s.get("bat_v", MetricStats())
    bat_pct = s.get("bat_pct", MetricStats())
    rssi = s.get("rssi", MetricStats())
    snr = s.get("snr", MetricStats())
    rx = s.get("rx", MetricStats())
    tx = s.get("tx", MetricStats())

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
        bat_v = s.get("bat_v", MetricStats())
        bat_pct = s.get("bat_pct", MetricStats())
        contacts = s.get("contacts", MetricStats())
        rx = s.get("rx", MetricStats())
        tx = s.get("tx", MetricStats())

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
    bat_v = s.get("bat_v", MetricStats())
    bat_pct = s.get("bat_pct", MetricStats())
    contacts = s.get("contacts", MetricStats())
    rx = s.get("rx", MetricStats())
    tx = s.get("tx", MetricStats())

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
