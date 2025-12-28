"""RRDtool chart color palette matching the Radio Observatory design.

This module provides color definitions for RRD chart generation that
match the MeshCore Stats dashboard design system. Colors are designed
to integrate seamlessly with both light and dark themes.

Design Philosophy:
- Light theme: Warm cream paper background with amber accent (solar energy)
- Dark theme: Deep observatory night sky with amber accent (radio glow)
- Data line uses amber/burnt orange to evoke solar power and radio warmth
"""

from dataclasses import dataclass
from typing import Literal

ThemeName = Literal["light", "dark"]


@dataclass(frozen=True, slots=True)
class ChartTheme:
    """Color palette for RRD chart rendering.

    All colors are hex values WITHOUT the # prefix, as required by rrdtool.
    """
    back: str       # Background color
    canvas: str     # Chart area background
    font: str       # Text/label color
    axis: str       # Axis line/label color
    frame: str      # Chart frame/border
    arrow: str      # Axis arrows
    grid: str       # Minor grid lines
    mgrid: str      # Major grid lines
    line: str       # Data line color
    area: str       # Area fill (includes alpha, e.g., "b4530918")


# Chart themes matching the CSS design system
CHART_THEMES: dict[ThemeName, ChartTheme] = {
    "light": ChartTheme(
        # Warm cream paper background (#faf8f5)
        back="faf8f5",
        canvas="ffffff",
        # Charcoal text (#1a1915)
        font="1a1915",
        # Muted text for axes (#8a857a)
        axis="8a857a",
        # Subtle border (#e8e4dc)
        frame="e8e4dc",
        arrow="8a857a",
        # Grid lines
        grid="e8e4dc",
        mgrid="d4cfc4",
        # Solar amber accent - burnt orange (#b45309)
        line="b45309",
        # Semi-transparent amber fill (15% opacity)
        area="b4530926",
    ),
    "dark": ChartTheme(
        # Deep observatory night (#0f1114)
        back="0f1114",
        canvas="161a1e",
        # Light text (#f0efe8)
        font="f0efe8",
        # Muted text for axes (#706d62)
        axis="706d62",
        # Subtle border (#252a30)
        frame="252a30",
        arrow="706d62",
        # Grid lines
        grid="252a30",
        mgrid="2d333a",
        # Bright amber accent (#f59e0b)
        line="f59e0b",
        # Semi-transparent amber fill (20% opacity)
        area="f59e0b33",
    ),
}


def get_theme(name: ThemeName) -> ChartTheme:
    """Get chart theme by name.

    Args:
        name: "light" or "dark"

    Returns:
        ChartTheme instance

    Raises:
        KeyError: If theme name is invalid
    """
    return CHART_THEMES[name]


def get_rrdgraph_colors(theme: ThemeName) -> list[str]:
    """Generate rrdtool color arguments for a theme.

    Returns a list of --color arguments ready to be passed to rrdtool.graph().

    Args:
        theme: "light" or "dark"

    Returns:
        List of color arguments, e.g., ["--color", "BACK#faf8f5", ...]
    """
    t = CHART_THEMES[theme]
    args = []

    color_map = {
        "BACK": t.back,
        "CANVAS": t.canvas,
        "FONT": t.font,
        "AXIS": t.axis,
        "FRAME": t.frame,
        "ARROW": t.arrow,
        "GRID": t.grid,
        "MGRID": t.mgrid,
    }

    for key, value in color_map.items():
        args.extend(["--color", f"{key}#{value}"])

    return args


# For backwards compatibility with existing code that expects this structure
# (can be removed once integration is complete)
LEGACY_CHART_THEMES = {
    "light": {
        "back": CHART_THEMES["light"].back,
        "canvas": CHART_THEMES["light"].canvas,
        "font": CHART_THEMES["light"].font,
        "axis": CHART_THEMES["light"].axis,
        "frame": CHART_THEMES["light"].frame,
        "arrow": CHART_THEMES["light"].arrow,
        "grid": CHART_THEMES["light"].grid,
        "mgrid": CHART_THEMES["light"].mgrid,
        "line": CHART_THEMES["light"].line,
        "area": CHART_THEMES["light"].area,
    },
    "dark": {
        "back": CHART_THEMES["dark"].back,
        "canvas": CHART_THEMES["dark"].canvas,
        "font": CHART_THEMES["dark"].font,
        "axis": CHART_THEMES["dark"].axis,
        "frame": CHART_THEMES["dark"].frame,
        "arrow": CHART_THEMES["dark"].arrow,
        "grid": CHART_THEMES["dark"].grid,
        "mgrid": CHART_THEMES["dark"].mgrid,
        "line": CHART_THEMES["dark"].line,
        "area": CHART_THEMES["dark"].area,
    },
}
