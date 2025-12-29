# CLAUDE.md - MeshCore Stats Project Guide

> **Maintenance Note**: This file should always reflect the current state of the project. When making changes to the codebase (adding features, changing architecture, modifying configuration), update this document accordingly. Keep it accurate and comprehensive for future reference.

## Running Commands

**IMPORTANT**: Always use `direnv exec .` to run Python scripts in this project. This ensures the correct virtualenv and environment variables are loaded.

```bash
# Correct way to run scripts
direnv exec . python scripts/phase3_render_site.py

# NEVER use these (virtualenv won't be loaded correctly):
# source .envrc && python ...
# .direnv/python-3.12/bin/python ...
```

## Project Overview

This project monitors a MeshCore LoRa mesh network consisting of:
- **1 Companion node**: Connected via USB serial to a NUC (local device)
- **1 Remote repeater**: Reachable over LoRa from the companion
  - Hardware: **Seeed SenseCAP Solar Node P1-Pro**
  - Location: **Oosterhout, The Netherlands**
  - Preset: **MeshCore EU/UK Narrow** (869.618 MHz, 62.5 kHz BW, SF8, CR8)

The system collects metrics, stores them as JSON snapshots, and generates a static HTML dashboard with SVG charts.

## Architecture

```
┌─────────────────┐     LoRa      ┌─────────────────┐
│   Companion     │◄────────────►│    Repeater     │
│  (USB Serial)   │               │   (Remote)      │
└────────┬────────┘               └─────────────────┘
         │
         │ Serial
         ▼
┌─────────────────┐
│      NUC        │
│  (This System)  │
└─────────────────┘

Data Flow:
Phase 1: Collect → JSON snapshots
Phase 2: Render  → SVG charts (from snapshots, using matplotlib)
Phase 3: Render  → Static HTML site (inline SVG)
Phase 4: Render  → Reports (monthly/yearly statistics)
```

## Directory Structure

```
meshcore-stats/
├── src/meshmon/           # Core library
│   ├── __init__.py
│   ├── env.py             # Environment config parsing
│   ├── log.py             # Logging utilities
│   ├── meshcore_client.py # MeshCore connection wrapper
│   ├── jsondump.py        # Snapshot JSON writer
│   ├── extract.py         # Metric extraction from snapshots
│   ├── retry.py           # Retry logic & circuit breaker
│   ├── charts.py          # SVG chart rendering (matplotlib)
│   ├── html.py            # HTML site generation
│   ├── metrics.py         # Metric type definitions (counter vs gauge)
│   ├── snapshot.py        # Snapshot data merging/derived fields
│   └── reports.py         # Report generation (WeeWX-style)
├── scripts/               # Executable scripts (cron-friendly)
│   ├── phase1_collect_companion.py
│   ├── phase1_collect_repeater.py
│   ├── phase2_render_charts.py   # Generate SVG charts from snapshots
│   ├── phase3_render_site.py
│   ├── phase4_render_reports.py  # Monthly/yearly reports
│   └── rsync_output.sh    # Deploy to web server
├── data/
│   ├── snapshots/         # JSON snapshots by date
│   │   ├── companion/YYYY/MM/DD/HHMMSS.json
│   │   └── repeater/YYYY/MM/DD/HHMMSS.json
│   └── state/             # Persistent state (circuit breaker)
│       └── repeater_circuit.json
├── out/                   # Generated static site
│   ├── day.html           # Repeater pages at root (entry point)
│   ├── week.html
│   ├── month.html
│   ├── year.html
│   ├── .htaccess          # Apache config (DirectoryIndex, cache control)
│   ├── styles.css         # CSS stylesheet
│   ├── chart-tooltip.js   # Progressive enhancement for chart tooltips
│   ├── companion/         # Companion pages (day/week/month/year.html)
│   ├── assets/            # SVG chart files and statistics
│   │   ├── companion/     # {metric}_{period}_{theme}.svg, chart_stats.json
│   │   └── repeater/      # {metric}_{period}_{theme}.svg, chart_stats.json
│   └── reports/           # Monthly/yearly statistics reports
│       ├── index.html     # Reports listing page
│       ├── repeater/      # Repeater reports by year/month
│       │   └── YYYY/
│       │       ├── index.html, report.txt, report.json  # Yearly
│       │       └── MM/
│       │           └── index.html, report.txt, report.json  # Monthly
│       └── companion/     # Same structure as repeater
└── .envrc                 # Environment configuration
```

## Configuration

All configuration via environment variables (see `.envrc`):

### Connection Settings
- `MESH_TRANSPORT`: "serial" (default), "tcp", or "ble"
- `MESH_SERIAL_PORT`: Serial port path (auto-detects if unset)
- `MESH_SERIAL_BAUD`: Baud rate (default: 115200)
- `MESH_DEBUG`: Enable meshcore debug logging (0/1)

### Repeater Identity
- `REPEATER_NAME`: Advertised name to find in contacts
- `REPEATER_KEY_PREFIX`: Alternative: hex prefix of public key
- `REPEATER_PASSWORD`: Admin password for login

### Timeouts & Retry
- `REMOTE_TIMEOUT_S`: Minimum timeout for LoRa requests (default: 10)
- `REMOTE_RETRY_ATTEMPTS`: Number of retry attempts (default: 5)
- `REMOTE_RETRY_BACKOFF_S`: Seconds between retries (default: 4)
- `REMOTE_CB_FAILS`: Failures before circuit breaker opens (default: 6)
- `REMOTE_CB_COOLDOWN_S`: Circuit breaker cooldown (default: 3600)

### Intervals
- `COMPANION_STEP`: Collection interval for companion (default: 60s)
- `REPEATER_STEP`: Collection interval for repeater (default: 900s / 15min)

### Report Location Metadata
- `REPORT_LOCATION_NAME`: Location name for report headers (default: "Oosterhout, The Netherlands")
- `REPORT_LAT`: Latitude in decimal degrees (default: 51.6674308)
- `REPORT_LON`: Longitude in decimal degrees (default: 4.8596901)
- `REPORT_ELEV`: Elevation in meters (default: 10.0)

### Metric Mappings

Format: `ds_name=dotted.path,ds_name2=other.path`

- `COMPANION_METRICS`: Metrics to extract from companion snapshots
- `REPEATER_METRICS`: Metrics to extract from repeater snapshots

**Current configuration:**
```bash
COMPANION_METRICS="bat_v=derived.bat_v,bat_pct=derived.bat_pct,contacts=derived.contacts_count,rx=stats.packets.recv,tx=stats.packets.sent,uptime=stats.core.uptime_secs"

REPEATER_METRICS="bat_v=derived.bat_v,bat_pct=derived.bat_pct,rx=derived.rx,tx=derived.tx,rssi=derived.rssi,snr=derived.snr,uptime=status.uptime,noise=status.noise_floor,airtime=status.airtime,rx_air=status.rx_airtime,fl_dups=status.flood_dups,di_dups=status.direct_dups,fl_tx=status.sent_flood,fl_rx=status.recv_flood,di_tx=status.sent_direct,di_rx=status.recv_direct,txq=status.tx_queue_len"
```

## Key Dependencies

- **meshcore**: Python library for MeshCore device communication
  - Commands accessed via `mc.commands.method_name()`
  - Contacts returned as dict keyed by public key
  - Binary request `req_status_sync` returns payload directly
- **matplotlib**: SVG chart generation
- **jinja2**: HTML template rendering

## Metric Types

Metrics are classified as either **gauge** or **counter** in `src/meshmon/metrics.py`:

- **GAUGE**: Instantaneous values (bat_v, bat_pct, contacts, neigh, rssi, snr, uptime, noise)
- **COUNTER**: Cumulative values that show rate of change - displayed as per-minute:
  - `rx`, `tx` - Total packet counters
  - `airtime`, `rx_air` - TX/RX airtime in seconds
  - `fl_dups`, `di_dups` - Duplicate packet counters (flood/direct)
  - `fl_tx`, `fl_rx` - Flood packet counters
  - `di_tx`, `di_rx` - Direct packet counters
  - `txq` - TX queue length (bar chart for discrete samples)

Counter metrics are converted to rates during chart rendering by calculating deltas between consecutive snapshots.

## Derived Fields

The snapshot module (`src/meshmon/snapshot.py`) calculates derived fields that aren't directly in the raw snapshots:

### Battery Voltage (`derived.bat_v`)
- Companion: `stats.core.battery_mv / 1000` or `bat.level / 1000`
- Repeater: `status.bat / 1000`

### Battery Percentage (`derived.bat_pct`)
Calculated from voltage using 18650 Li-ion discharge curve:

| Voltage | Percentage |
|---------|------------|
| 4.20V   | 100%       |
| 4.06V   | 90%        |
| 3.98V   | 80%        |
| 3.92V   | 70%        |
| 3.87V   | 60%        |
| 3.82V   | 50%        |
| 3.79V   | 40%        |
| 3.77V   | 30%        |
| 3.74V   | 20%        |
| 3.68V   | 10%        |
| 3.45V   | 5%         |
| 3.00V   | 0%         |

Uses piecewise linear interpolation between points.

### Repeater-specific derived fields
- `derived.rssi`: from `status.last_rssi`
- `derived.snr`: from `status.last_snr`
- `derived.rx`: from `status.nb_recv`
- `derived.tx`: from `status.nb_sent`

## Data Paths in Snapshots

### Companion Snapshot Structure
```json
{
  "ts": 1766397234,
  "node": {"role": "companion"},
  "device_info": {...},
  "self_info": {
    "radio_freq": 869.618,
    "radio_bw": 62.5,
    "radio_sf": 8,
    "tx_power": 22,
    "name": "..."
  },
  "bat": {
    "level": 4145  // millivolts
  },
  "stats": {
    "core": {
      "battery_mv": 4148,
      "uptime_secs": 1776
    },
    "packets": {
      "recv": 160,
      "sent": 0
    }
  },
  "derived": {
    "contacts_count": 3
  }
}
```

### Repeater Snapshot Structure
```json
{
  "ts": 1766410160,
  "node": {"role": "repeater", "name": "..."},
  "status": {
    "bat": 4049,           // millivolts
    "noise_floor": -116,
    "last_rssi": -30,
    "last_snr": 12.0,
    "nb_recv": 104945,
    "nb_sent": 46697,
    "uptime": 842491,
    "airtime": 32817
  },
  "telemetry": null,       // No longer fetched (all data comes from status)
  "acl": null,
  "derived": {}
}
```

## Running the Scripts

Always source the environment first:

```bash
# Using direnv (automatic)
cd /path/to/meshcore-stats

# Or manually
source .envrc 2>/dev/null
```

### Phase 1: Data Collection

```bash
# Collect companion data (run every 60s)
python scripts/phase1_collect_companion.py

# Collect repeater data (run every 15min)
python scripts/phase1_collect_repeater.py
```

### Phase 2: Chart Rendering

```bash
# Render all SVG charts from snapshots (day/week/month/year for all metrics)
python scripts/phase2_render_charts.py
```

Charts are rendered using matplotlib, reading directly from JSON snapshots. Each chart is generated in both light and dark theme variants.

### Phase 3: HTML Generation

```bash
# Generate static site pages
python scripts/phase3_render_site.py
```

### Phase 4: Reports

Generates monthly and yearly statistics reports in HTML, TXT (WeeWX-style ASCII), and JSON formats:

```bash
# Generate all reports
python scripts/phase4_render_reports.py
```

Reports are generated for all available months/years based on snapshot data. Output structure:
- `/reports/` - Index page listing all available reports
- `/reports/{role}/{year}/` - Yearly report (HTML, TXT, JSON)
- `/reports/{role}/{year}/{month}/` - Monthly report (HTML, TXT, JSON)

Counter metrics (rx, tx, airtime) are aggregated from absolute counter values in snapshots, with proper handling of device reboots (negative deltas).

### Deploy to Web Server

```bash
# Dry run first (edit script to remove --dry-run for actual sync)
./scripts/rsync_output.sh
```

## Web Dashboard UI

The static site uses a modern, responsive design with the following features:

### Site Structure
- **Repeater pages at root**: `/day.html`, `/week.html`, etc. (entry point)
- **Companion pages**: `/companion/day.html`, `/companion/week.html`, etc.
- **`.htaccess`**: Sets `DirectoryIndex day.html` so `/` loads repeater day view

### Page Layout
1. **Header**: Site branding, node name, pubkey prefix, status indicator, last updated time
2. **Navigation**: Node switcher (Repeater/Companion) + period tabs (Day/Week/Month/Year)
3. **Metrics Bar**: Key values at a glance (Battery, Uptime, RSSI, SNR for repeater)
4. **Dashboard Grid**: Two-column layout with Snapshot table and About section
5. **Charts Grid**: Two charts per row on desktop, one on mobile

### Status Indicator
Color-coded based on data freshness:
- **Green (online)**: Data less than 30 minutes old
- **Yellow (stale)**: Data 30 minutes to 2 hours old
- **Red (offline)**: Data more than 2 hours old

### Chart Tooltips
- Progressive enhancement via `chart-tooltip.js`
- Shows datetime and value when hovering over chart data
- Works without JavaScript (charts still display, just no tooltips)
- Uses `data-points`, `data-x-start`, `data-x-end` attributes embedded in SVG

### Social Sharing
Open Graph and Twitter Card meta tags for link previews:
- `og:title`, `og:description`, `og:site_name`
- `twitter:card` (summary_large_image format)
- Role-specific descriptions

### Design System (CSS Variables)
```css
--primary: #2563eb;        /* Brand blue */
--bg: #f8fafc;             /* Page background */
--bg-elevated: #ffffff;    /* Card background */
--text: #1e293b;           /* Primary text */
--text-muted: #64748b;     /* Secondary text */
--border: #e2e8f0;         /* Borders */
--success: #16a34a;        /* Online status */
--warning: #ca8a04;        /* Stale status */
--danger: #dc2626;         /* Offline status */
```

### Responsive Breakpoints
- **< 900px**: Single column layout, stacked header
- **< 600px**: Smaller fonts, stacked table cells, horizontal scroll nav

## Chart Configuration

Charts are generated as inline SVGs using matplotlib (`src/meshmon/charts.py`).

### Rendering
- **Output**: SVG files at 800x280 pixels
- **Themes**: Light and dark variants (CSS `prefers-color-scheme` switches between them)
- **Inline**: SVGs are embedded directly in HTML for zero additional requests
- **Tooltips**: Data points embedded as JSON in SVG `data-points` attribute
- **Chart Type Selection**:
  - **Bar charts**: Used for counter metrics (rx, tx, airtime, etc.) to visualize discrete time buckets for rate-based data
  - **Line charts**: Used for gauge metrics (bat_v, rssi, uptime, etc.) to show continuous measurements over time
  - Determined by `is_counter_metric()` in `src/meshmon/metrics.py`

### Time Aggregation (Binning)
Data points are aggregated into bins to keep chart file sizes reasonable and lines clean:

| Period | Bin Size | ~Data Points | Pixels/Point |
|--------|----------|--------------|--------------|
| Day | Raw (no binning) | ~96 | ~6.7px |
| Week | 30 minutes | ~336 | ~2px |
| Month | 2 hours | ~372 | ~1.7px |
| Year | 1 day | ~365 | ~1.8px |

### Visual Style
- 2 charts per row on desktop, 1 on mobile (< 900px)
- Amber/orange color scheme (#b45309 light, #f59e0b dark)
- **Line charts** (gauges): Semi-transparent area fill with solid line on top
- **Bar charts** (counters): Solid bars with 90% opacity, auto-calculated width based on data intervals
- Min/Avg/Max statistics displayed in chart footer
- Current value displayed in chart header

### Repeater Metrics Summary

| Metric | Source | Type | Display Unit | Description |
|--------|--------|------|--------------|-------------|
| `bat_v` | `derived.bat_v` | gauge | Voltage (V) | Battery voltage |
| `bat_pct` | `derived.bat_pct` | gauge | Battery (%) | Battery percentage |
| `rx` | `derived.rx` | counter | Packets/min | Total packets received |
| `tx` | `derived.tx` | counter | Packets/min | Total packets transmitted |
| `rssi` | `derived.rssi` | gauge | RSSI (dBm) | Signal strength of last packet |
| `snr` | `derived.snr` | gauge | SNR (dB) | Signal-to-noise ratio |
| `uptime` | `status.uptime` | gauge | Days | Time since reboot (seconds ÷ 86400) |
| `noise` | `status.noise_floor` | gauge | dBm | Background RF noise |
| `airtime` | `status.airtime` | counter | Seconds/min | TX airtime rate |
| `rx_air` | `status.rx_airtime` | counter | Seconds/min | RX airtime rate |
| `fl_dups` | `status.flood_dups` | counter | Packets/min | Flood duplicate packets |
| `di_dups` | `status.direct_dups` | counter | Packets/min | Direct duplicate packets |
| `fl_tx` | `status.sent_flood` | counter | Packets/min | Flood packets transmitted |
| `fl_rx` | `status.recv_flood` | counter | Packets/min | Flood packets received |
| `di_tx` | `status.sent_direct` | counter | Packets/min | Direct packets transmitted |
| `di_rx` | `status.recv_direct` | counter | Packets/min | Direct packets received |
| `txq` | `status.tx_queue_len` | counter | Queue depth | TX queue length |

### Companion Metrics Summary

| Metric | Source | Type | Display Unit | Description |
|--------|--------|------|--------------|-------------|
| `bat_v` | `derived.bat_v` | gauge | Voltage (V) | Battery voltage |
| `bat_pct` | `derived.bat_pct` | gauge | Battery (%) | Battery percentage |
| `contacts` | `derived.contacts_count` | gauge | Count | Known mesh nodes |
| `rx` | `stats.packets.recv` | counter | Packets/min | Total packets received |
| `tx` | `stats.packets.sent` | counter | Packets/min | Total packets transmitted |
| `uptime` | `stats.core.uptime_secs` | gauge | Days | Time since reboot (seconds ÷ 86400) |

## Circuit Breaker

The repeater collector uses a circuit breaker to avoid spamming LoRa when the repeater is unreachable:

- State stored in `data/state/repeater_circuit.json`
- After N consecutive failures, enters cooldown
- During cooldown, writes skip snapshot instead of attempting request
- Resets on successful response

## Debugging

Enable debug logging:
```bash
MESH_DEBUG=1 python scripts/phase1_collect_companion.py
```

Check circuit breaker state:
```bash
cat data/state/repeater_circuit.json
```

Test with meshcore-cli:
```bash
meshcore-cli -s /dev/ttyACM0 contacts
meshcore-cli -s /dev/ttyACM0 req_status "repeater name"
meshcore-cli -s /dev/ttyACM0 reset_path "repeater name"
```

## Known Issues

1. **Repeater not responding**: If `req_status_sync` times out after all retry attempts, the repeater may:
   - Not support binary protocol requests
   - Have incorrect admin password configured
   - Have routing issues (asymmetric path)
   - Be offline or rebooted

2. **Environment variables not loaded**: Scripts must be run with direnv active or manually source `.envrc`

3. **Empty charts**: Need at least 2 data points (snapshots) to display meaningful data.

## Cron Setup (Example)

**Important**: Stagger companion and repeater collection to avoid USB serial conflicts.

```cron
# Companion: every minute at :00
* * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase1_collect_companion.py

# Repeater: every 15 minutes at :01, :16, :31, :46 (offset by 1 min to avoid USB conflict)
1,16,31,46 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase1_collect_repeater.py

# Charts: every 5 minutes (generates SVG charts from snapshots)
*/5 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase2_render_charts.py

# HTML: every 5 minutes
*/5 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase3_render_site.py

# Reports: daily at midnight (historical stats don't change often)
0 0 * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase4_render_reports.py

# Deploy: every 5 minutes (after removing --dry-run from script)
*/5 * * * * cd /home/jorijn/apps/meshcore-stats && ./scripts/rsync_output.sh
```

## Adding New Metrics

1. Add the metric to `COMPANION_METRICS` or `REPEATER_METRICS` in `.envrc`
2. If the metric needs calculation, add it to `build_merged_view()` in `src/meshmon/snapshot.py`
3. If it's a counter metric (rate of change), add it to `COUNTER_METRICS` in `src/meshmon/metrics.py`
4. Add a label in `METRIC_LABELS` in `src/meshmon/charts.py`
5. Reload direnv: `direnv allow`
6. Regenerate charts and site

## Changing Metric Types

Metric type configuration is centralized in `src/meshmon/metrics.py`:

- `COUNTER_METRICS`: Set of metrics that show rate of change (displayed as per-minute)
- `GRAPH_SCALING`: Dict of metric → scale factor for display (e.g., ×60 for per-minute)

If you need to change a metric from gauge to counter (or vice versa):

1. Update `COUNTER_METRICS` in `src/meshmon/metrics.py`
2. Update `GRAPH_SCALING` if the metric needs display scaling
3. Regenerate charts: `python scripts/phase2_render_charts.py`
