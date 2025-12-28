# TODO - MeshCore Stats Chart Migration

## Bugs Fixed

### 1. ~~Both light and dark mode charts showing simultaneously~~
**Status**: Fixed (browser cache issue)

The CSS theme switching was working correctly, but browser cache was showing stale styles.

### 2. ~~Year charts don't pad to full year~~
**Status**: Fixed

Year charts only showed data from the available period (e.g., just December) instead of padding the X-axis to show the full year. This made trend visualization difficult compared to the old RRDtool charts.

**Fix**: Added `x_start` and `x_end` parameters to `render_chart_svg()` to force axis limits for the full period range.

### 3. ~~Tooltips not working~~
**Status**: Fixed (browser cache issue)

The tooltip JavaScript was working correctly, but browser cache was serving stale JS.

## Future Enhancements

### Single SVG with CSS Variables (Phase 2)
Currently rendering two separate SVGs (light/dark theme). Could optimize to:
- Render single SVG using CSS custom properties for colors
- Reduce HTML size by ~50% for chart content
- Requires matplotlib SVG post-processing to replace hardcoded colors with `var(--chart-line)` etc.

### Zoom/Pan Controls
Add optional JavaScript enhancement for:
- Click-drag to zoom into time range
- Reset button to return to full view
- Touch gesture support for mobile

### Performance Optimization
- Year view loads all snapshots for 365 days - could be slow
- Consider pre-aggregated data cache for longer periods
- Lazy loading for charts below the fold

### ~~Remove RRD Dependencies~~
**Status**: Completed

Migration to matplotlib SVG charts is complete. RRD-related files have been removed:
- Removed `phase2_rrd_update_*.py` scripts
- Removed `phase2_rrd_init.py` and `backfill_rrd.py`
- Removed `src/meshmon/rrd.py`
- Removed `rrdtool-bindings` from requirements.txt
- Updated CLAUDE.md to remove RRD references

Note: RRD database files in `data/rrd/` can be archived/deleted manually if no longer needed.

### Tooltip Improvements
- Show metric units in tooltip (V, %, dBm, etc.)
- Snap to nearest data point
- Mobile-friendly tap behavior
