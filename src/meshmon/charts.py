"""Matplotlib-based chart generation from SQLite database.

This module generates SVG charts with CSS variable support for theming,
reading metrics directly from the SQLite database (EAV schema).
"""

import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import matplotlib

matplotlib.use('Agg')  # Non-interactive backend for server-side rendering
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

from . import log
from .db import get_metrics_for_period
from .env import get_config
from .metrics import (
    get_chart_metrics,
    get_graph_scale,
    is_counter_metric,
    transform_value,
)

# Type alias for theme names
ThemeName = Literal["light", "dark"]

# Bin size constants (in seconds)
# These control time aggregation to keep chart data points at reasonable density
BIN_30_MINUTES = 1800  # 30 minutes in seconds
BIN_2_HOURS = 7200  # 2 hours in seconds
BIN_1_DAY = 86400  # 1 day in seconds
MIN_COUNTER_INTERVAL_RATIO = 0.9  # Allow small scheduling jitter


@dataclass(frozen=True)
class PeriodConfig:
    """Configuration for a chart time period."""

    lookback: timedelta
    bin_seconds: int | None = None  # None = no binning (raw data)


# Period configuration for chart rendering
# Target: ~100-400 data points per chart for clean visualization
# Chart plot area is ~640px, so aim for 1.5-6px per point
PERIOD_CONFIG: dict[str, PeriodConfig] = {
    "day": PeriodConfig(
        lookback=timedelta(days=1),
        bin_seconds=None,  # No binning - raw data (~96 points at 15-min intervals)
    ),
    "week": PeriodConfig(
        lookback=timedelta(days=7),
        bin_seconds=BIN_30_MINUTES,  # 30-min bins (~336 points, ~2px per point)
    ),
    "month": PeriodConfig(
        lookback=timedelta(days=31),
        bin_seconds=BIN_2_HOURS,  # 2-hour bins (~372 points, ~1.7px per point)
    ),
    "year": PeriodConfig(
        lookback=timedelta(days=365),
        bin_seconds=BIN_1_DAY,  # 1-day bins (~365 points, ~1.8px per point)
    ),
}


@dataclass(frozen=True)
class ChartTheme:
    """Color palette for chart rendering with CSS variable names."""

    name: str
    # Colors as hex values (without #)
    background: str
    canvas: str
    text: str
    axis: str
    grid: str
    line: str
    area: str  # Includes alpha channel


# Chart themes matching the Radio Observatory design (from redesign/chart_colors.py)
CHART_THEMES: dict[ThemeName, ChartTheme] = {
    "light": ChartTheme(
        name="light",
        background="faf8f5",  # Warm cream paper
        canvas="ffffff",
        text="1a1915",  # Charcoal
        axis="8a857a",  # Muted text
        grid="e8e4dc",  # Subtle border
        line="b45309",  # Solar amber accent - burnt orange
        area="b4530926",  # 15% opacity fill
    ),
    "dark": ChartTheme(
        name="dark",
        background="0f1114",  # Deep observatory night
        canvas="161a1e",
        text="f0efe8",  # Light text
        axis="706d62",  # Muted text
        grid="252a30",  # Subtle border
        line="f59e0b",  # Bright amber accent
        area="f59e0b33",  # 20% opacity fill
    ),
}


@dataclass
class DataPoint:
    """A single data point with timestamp and value."""
    timestamp: datetime
    value: float


@dataclass
class TimeSeries:
    """Time series data for a single metric."""

    metric: str
    role: str
    period: str
    points: list[DataPoint] = field(default_factory=list)

    @property
    def timestamps(self) -> list[datetime]:
        return [p.timestamp for p in self.points]

    @property
    def values(self) -> list[float]:
        return [p.value for p in self.points]

    @property
    def is_empty(self) -> bool:
        return len(self.points) == 0


@dataclass
class ChartStatistics:
    """Statistics for a time series (min/avg/max/current)."""

    min_value: float | None = None
    avg_value: float | None = None
    max_value: float | None = None
    current_value: float | None = None

    def to_dict(self) -> dict[str, float | None]:
        """Convert to dict matching existing chart_stats.json format."""
        return {
            "min": self.min_value,
            "avg": self.avg_value,
            "max": self.max_value,
            "current": self.current_value,
        }


def _hex_to_rgba(hex_color: str) -> tuple[float, float, float, float]:
    """Convert hex color (without #) to RGBA tuple (0-1 range).

    Accepts 6-char (RGB) or 8-char (RGBA) hex strings.
    """
    r = int(hex_color[0:2], 16) / 255
    g = int(hex_color[2:4], 16) / 255
    b = int(hex_color[4:6], 16) / 255
    a = int(hex_color[6:8], 16) / 255 if len(hex_color) >= 8 else 1.0
    return (r, g, b, a)


def load_timeseries_from_db(
    role: str,
    metric: str,
    end_time: datetime,
    lookback: timedelta,
    period: str,
    all_metrics: dict[str, list[tuple[int, float]]] | None = None,
) -> TimeSeries:
    """Load time series data from SQLite database.

    Fetches metric data from EAV table, handles counter-to-rate conversion,
    applies transforms (e.g., mv_to_v), and applies time binning as needed.

    Args:
        role: "companion" or "repeater"
        metric: Metric name (firmware field name, e.g., "bat", "nb_recv")
        end_time: End of the time range (typically now)
        lookback: How far back to look
        period: Period name for binning config ("day", "week", etc.)
        all_metrics: Optional pre-fetched metrics dict for this period

    Returns:
        TimeSeries with extracted data points
    """
    start_time = end_time - lookback
    start_ts = int(start_time.timestamp())
    end_ts = int(end_time.timestamp())

    # Fetch all metrics for this role/period (returns pivoted dict)
    if all_metrics is None:
        all_metrics = get_metrics_for_period(role, start_ts, end_ts)

    # Get data for this specific metric
    metric_data = all_metrics.get(metric, [])

    if not metric_data:
        return TimeSeries(metric=metric, role=role, period=period)

    is_counter = is_counter_metric(metric)
    scale = get_graph_scale(metric)

    # Convert to (datetime, value) tuples with transform applied
    raw_points: list[tuple[datetime, float]] = []
    for ts, value in metric_data:
        # Apply any configured transform (e.g., mv_to_v for battery)
        transformed_value = transform_value(metric, value)
        raw_points.append((datetime.fromtimestamp(ts), transformed_value))

    if not raw_points:
        return TimeSeries(metric=metric, role=role, period=period)

    # For counter metrics, calculate rate of change
    if is_counter:
        rate_points: list[tuple[datetime, float]] = []
        cfg = get_config()
        min_interval = max(
            1.0,
            (cfg.companion_step if role == "companion" else cfg.repeater_step)
            * MIN_COUNTER_INTERVAL_RATIO,
        )

        prev_ts, prev_val = raw_points[0]
        for curr_ts, curr_val in raw_points[1:]:
            delta_secs = (curr_ts - prev_ts).total_seconds()

            if delta_secs <= 0:
                continue
            if delta_secs < min_interval:
                log.debug(
                    f"Skipping counter sample for {metric} at {curr_ts} "
                    f"({delta_secs:.1f}s < {min_interval:.1f}s)"
                )
                continue

            delta_val = curr_val - prev_val

            # Skip negative deltas (device reboot)
            if delta_val < 0:
                log.debug(f"Counter reset detected for {metric} at {curr_ts}")
                prev_ts, prev_val = curr_ts, curr_val
                continue

            # Calculate per-second rate, then apply scaling (typically x60 for per-minute)
            rate = (delta_val / delta_secs) * scale
            rate_points.append((curr_ts, rate))
            prev_ts, prev_val = curr_ts, curr_val

        raw_points = rate_points
    else:
        # For gauges, just apply scaling
        raw_points = [(ts, val * scale) for ts, val in raw_points]

    # Apply time binning if configured
    period_cfg = PERIOD_CONFIG.get(period)
    if period_cfg and period_cfg.bin_seconds and len(raw_points) > 1:
        raw_points = _aggregate_bins(raw_points, period_cfg.bin_seconds)

    # Convert to DataPoints
    points = [DataPoint(timestamp=ts, value=val) for ts, val in raw_points]

    return TimeSeries(metric=metric, role=role, period=period, points=points)


def _aggregate_bins(
    points: list[tuple[datetime, float]],
    bin_seconds: int,
) -> list[tuple[datetime, float]]:
    """Aggregate points into time bins using mean.

    Args:
        points: List of (timestamp, value) tuples, must be sorted
        bin_seconds: Size of each bin in seconds

    Returns:
        Aggregated points, one per bin
    """
    if not points:
        return []

    bins: dict[int, list[float]] = {}

    for ts, val in points:
        # Round timestamp down to bin boundary
        epoch = int(ts.timestamp())
        bin_key = (epoch // bin_seconds) * bin_seconds

        if bin_key not in bins:
            bins[bin_key] = []
        bins[bin_key].append(val)

    # Calculate mean for each bin
    result = []
    for bin_key in sorted(bins.keys()):
        values = bins[bin_key]
        mean_val = sum(values) / len(values)
        bin_ts = datetime.fromtimestamp(bin_key + bin_seconds // 2)  # Center of bin
        result.append((bin_ts, mean_val))

    return result


def calculate_statistics(ts: TimeSeries) -> ChartStatistics:
    """Calculate min/avg/max/current statistics from time series.

    Args:
        ts: Time series data

    Returns:
        ChartStatistics with calculated values
    """
    if ts.is_empty:
        return ChartStatistics()

    values = ts.values

    return ChartStatistics(
        min_value=min(values),
        avg_value=sum(values) / len(values),
        max_value=max(values),
        current_value=values[-1] if values else None,
    )


def render_chart_svg(
    ts: TimeSeries,
    theme: ChartTheme,
    width: int = 800,
    height: int = 280,
    y_min: float | None = None,
    y_max: float | None = None,
    x_start: datetime | None = None,
    x_end: datetime | None = None,
) -> str:
    """Render time series as SVG using matplotlib.

    Args:
        ts: Time series data to render
        theme: Color theme to apply
        width: Chart width in pixels
        height: Chart height in pixels
        y_min: Optional fixed Y-axis minimum
        y_max: Optional fixed Y-axis maximum
        x_start: Optional fixed X-axis start (for padding sparse data)
        x_end: Optional fixed X-axis end (for padding sparse data)

    Returns:
        SVG string with embedded data-points attribute for tooltips
    """
    # Create figure
    dpi = 100
    fig_width = width / dpi
    fig_height = height / dpi

    fig, ax = plt.subplots(figsize=(fig_width, fig_height), dpi=dpi)

    # Track actual Y-axis values for tooltip injection
    actual_y_min = y_min
    actual_y_max = y_max

    try:
        # Apply theme colors
        fig.patch.set_facecolor(f"#{theme.background}")
        ax.set_facecolor(f"#{theme.canvas}")

        # Configure axes
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color(f"#{theme.grid}")
        ax.spines['bottom'].set_color(f"#{theme.grid}")

        ax.tick_params(colors=f"#{theme.axis}", labelsize=10)
        ax.yaxis.label.set_color(f"#{theme.text}")

        # Grid
        ax.grid(True, linestyle='-', alpha=0.5, color=f"#{theme.grid}")
        ax.set_axisbelow(True)

        if ts.is_empty:
            # Empty chart - just show axes
            ax.text(
                0.5, 0.5, "No data available",
                transform=ax.transAxes,
                ha='center', va='center',
                fontsize=12,
                color=f"#{theme.axis}"
            )
        else:
            timestamps = ts.timestamps
            values = ts.values

            # Convert datetime to matplotlib date numbers for proper typing
            # and correct axis formatter behavior
            x_dates = mdates.date2num(timestamps)

            # Plot area fill
            area_color = _hex_to_rgba(theme.area)
            area = ax.fill_between(
                x_dates,
                values,
                alpha=area_color[3],
                color=f"#{theme.line}",
            )
            area.set_gid("chart-area")

            # Plot line
            (line,) = ax.plot(
                x_dates,
                values,
                color=f"#{theme.line}",
                linewidth=2,
            )
            line.set_gid("chart-line")

            # Set Y-axis limits and track actual values used
            if y_min is not None and y_max is not None:
                ax.set_ylim(y_min, y_max)
                actual_y_min, actual_y_max = y_min, y_max
            else:
                # Add some padding
                val_min, val_max = min(values), max(values)
                val_range = val_max - val_min if val_max != val_min else abs(val_max) * 0.1 or 1
                padding = val_range * 0.1
                actual_y_min = val_min - padding
                actual_y_max = val_max + padding
                ax.set_ylim(actual_y_min, actual_y_max)

            # Set X-axis limits first (before configuring ticks)
            if x_start is not None and x_end is not None:
                ax.set_xlim(mdates.date2num(x_start), mdates.date2num(x_end))
            else:
                # Compute sensible x-axis limits from data
                # For single point or sparse data, add padding based on period
                x_min_dt = min(timestamps)
                x_max_dt = max(timestamps)
                if x_min_dt == x_max_dt:
                    # Single point: use period lookback for range
                    period_cfg = PERIOD_CONFIG.get(ts.period, PERIOD_CONFIG["day"])
                    x_min_dt = x_max_dt - period_cfg.lookback
                ax.set_xlim(mdates.date2num(x_min_dt), mdates.date2num(x_max_dt))

            # Format X-axis based on period (after setting limits)
            _configure_x_axis(ax, ts.period)

        # Tight layout
        plt.tight_layout(pad=0.5)

        # Render to SVG
        svg_buffer = io.StringIO()
        fig.savefig(svg_buffer, format='svg', bbox_inches='tight', pad_inches=0.1)
        svg_content = svg_buffer.getvalue()

    finally:
        # Ensure figure is closed to prevent memory leaks
        plt.close(fig)

    # Inject data-points attribute for tooltip support
    if not ts.is_empty:
        svg_content = _inject_data_attributes(
            svg_content, ts, theme.name, x_start, x_end,
            actual_y_min, actual_y_max
        )

    return svg_content


def _configure_x_axis(ax, period: str) -> None:
    """Configure X-axis formatting based on period."""
    if period == "day":
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=4))
    elif period == "week":
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%a'))
        ax.xaxis.set_major_locator(mdates.DayLocator())
    elif period == "month":
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=5))
    else:  # year
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b'))
        ax.xaxis.set_major_locator(mdates.MonthLocator())

    # Rotate labels for readability
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=0, ha='center')


def _inject_data_attributes(
    svg: str,
    ts: TimeSeries,
    theme_name: str,
    x_start: datetime | None = None,
    x_end: datetime | None = None,
    y_min: float | None = None,
    y_max: float | None = None,
) -> str:
    """Inject data-* attributes into SVG for tooltip support.

    Adds:
    - data-metric, data-period, data-theme, data-x-start, data-x-end, data-y-min, data-y-max to root <svg>
    - data-points JSON array to the root <svg> and chart line path

    Args:
        svg: Raw SVG string
        ts: Time series data
        theme_name: Theme identifier
        x_start: X-axis start timestamp (for proper mouse-to-time mapping)
        x_end: X-axis end timestamp
        y_min: Y-axis minimum value
        y_max: Y-axis maximum value

    Returns:
        Modified SVG with data attributes
    """
    # Build data points array for tooltips
    data_points = [
        {"ts": int(p.timestamp.timestamp()), "v": round(p.value, 4)}
        for p in ts.points
    ]
    data_points_json = json.dumps(data_points)

    # Escape for HTML attribute (single quotes around JSON, escape internal quotes)
    data_points_attr = data_points_json.replace('"', '&quot;')

    # Build X-axis range attributes for proper tooltip positioning
    x_start_ts = int(x_start.timestamp()) if x_start else int(ts.points[0].timestamp.timestamp())
    x_end_ts = int(x_end.timestamp()) if x_end else int(ts.points[-1].timestamp.timestamp())

    # Build Y-axis range attributes
    y_min_val = y_min if y_min is not None else min(p.value for p in ts.points)
    y_max_val = y_max if y_max is not None else max(p.value for p in ts.points)

    # Add attributes to root <svg> element
    svg = re.sub(
        r'<svg\b',
        f'<svg data-metric="{ts.metric}" data-period="{ts.period}" data-theme="{theme_name}" '
        f'data-x-start="{x_start_ts}" data-x-end="{x_end_ts}" '
        f'data-y-min="{y_min_val}" data-y-max="{y_max_val}" '
        f'data-points="{data_points_attr}"',
        svg,
        count=1
    )

    # Add data-points to the line path inside the #chart-line group
    # matplotlib creates <g id="chart-line"><path d="..."></g>
    svg, count = re.subn(
        r'(<g[^>]*id="chart-line"[^>]*>\s*<path\b)',
        rf'\1 data-points="{data_points_attr}"',
        svg,
        count=1,
    )

    if count == 0:
        # Fallback: look for the second path element (first is usually the fill area)
        path_count = 0

        def add_data_to_path(match):
            nonlocal path_count
            path_count += 1
            if path_count == 2:  # The line path
                return f'<path data-points="{data_points_attr}"'
            return match.group(0)

        svg = re.sub(r'<path\b', add_data_to_path, svg)

    return svg


def render_all_charts(
    role: str,
    metrics: list[str] | None = None,
) -> tuple[list[Path], dict[str, dict[str, dict[str, Any]]]]:
    """Render all charts for a role in both light and dark themes.

    Also collects min/avg/max/current statistics for each metric/period.

    Args:
        role: "companion" or "repeater"
        metrics: Optional list of metric names to render (for testing)

    Returns:
        Tuple of (list of generated chart paths, stats dict)
        Stats dict structure: {metric_name: {period: {min, avg, max, current}}}
    """
    if metrics is None:
        metrics = get_chart_metrics(role)

    cfg = get_config()
    charts_dir = cfg.out_dir / "assets" / role
    charts_dir.mkdir(parents=True, exist_ok=True)

    periods = ["day", "week", "month", "year"]
    themes: list[ThemeName] = ["light", "dark"]

    generated: list[Path] = []
    all_stats: dict[str, dict[str, dict[str, Any]]] = {}

    # Current time for all lookbacks
    now = datetime.now()

    # Fixed Y-axis ranges for specific metrics
    # Battery metrics use transformed values (volts, not millivolts)
    y_ranges = {
        "bat": (3.0, 4.2),          # Repeater battery (V)
        "battery_mv": (3.0, 4.2),   # Companion battery (V after transform)
        "bat_pct": (0, 100),        # Battery percentage
    }

    for metric in metrics:
        all_stats[metric] = {}

    for period in periods:
        period_cfg = PERIOD_CONFIG[period]
        x_end = now
        x_start = now - period_cfg.lookback

        start_ts = int(x_start.timestamp())
        end_ts = int(x_end.timestamp())
        all_metrics = get_metrics_for_period(role, start_ts, end_ts)

        for metric in metrics:
            # Load time series from database
            ts = load_timeseries_from_db(
                role=role,
                metric=metric,
                end_time=now,
                lookback=period_cfg.lookback,
                period=period,
                all_metrics=all_metrics,
            )

            # Calculate and store statistics
            stats = calculate_statistics(ts)
            all_stats[metric][period] = stats.to_dict()

            # Get Y-axis range for this metric
            y_range = y_ranges.get(metric)
            y_min = y_range[0] if y_range else None
            y_max = y_range[1] if y_range else None

            # Render chart for each theme
            for theme_name in themes:
                theme = CHART_THEMES[theme_name]

                svg_content = render_chart_svg(
                    ts=ts,
                    theme=theme,
                    y_min=y_min,
                    y_max=y_max,
                    x_start=x_start,
                    x_end=x_end,
                )

                # Save to file
                output_path = charts_dir / f"{metric}_{period}_{theme_name}.svg"
                output_path.write_text(svg_content, encoding="utf-8")
                generated.append(output_path)

                log.debug(f"Generated chart: {output_path}")

    log.info(f"Rendered {len(generated)} charts for {role}")
    return generated, all_stats


def save_chart_stats(role: str, stats: dict[str, dict[str, dict[str, Any]]]) -> Path:
    """Save chart statistics to JSON file.

    Args:
        role: "companion" or "repeater"
        stats: Stats dict from render_all_charts

    Returns:
        Path to saved JSON file
    """
    cfg = get_config()
    stats_path = cfg.out_dir / "assets" / role / "chart_stats.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)

    with open(stats_path, "w") as f:
        json.dump(stats, f, indent=2)

    log.debug(f"Saved chart stats to {stats_path}")
    return stats_path


def load_chart_stats(role: str) -> dict[str, dict[str, dict[str, Any]]]:
    """Load chart statistics from JSON file.

    Args:
        role: "companion" or "repeater"

    Returns:
        Stats dict, or empty dict if file doesn't exist
    """
    cfg = get_config()
    stats_path = cfg.out_dir / "assets" / role / "chart_stats.json"

    if not stats_path.exists():
        return {}

    try:
        with open(stats_path) as f:
            data: dict[str, dict[str, dict[str, Any]]] = json.load(f)
            return data
    except Exception as e:
        log.debug(f"Failed to load chart stats: {e}")
        return {}
