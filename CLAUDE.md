# CLAUDE.md - MeshCore Stats Project Guide

> **Maintenance Note**: This file should always reflect the current state of the project. When making changes to the codebase (adding features, changing architecture, modifying configuration), update this document accordingly. Keep it accurate and comprehensive for future reference.

## Project Overview

This project monitors a MeshCore LoRa mesh network consisting of:
- **1 Companion node**: Connected via USB serial to a NUC (local device)
- **1 Remote repeater**: Reachable over LoRa from the companion
  - Hardware: **Seeed SenseCAP Solar Node P1-Pro**
  - Location: **Oosterhout, The Netherlands**
  - Preset: **MeshCore EU/UK Narrow** (869.618 MHz, 62.5 kHz BW, SF8, CR8)

The system collects metrics, stores them in RRD databases, and generates a static HTML dashboard with charts.

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
Phase 2: Update  → RRD databases
         Render  → PNG charts
Phase 3: Render  → Static HTML site
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
│   ├── rrd.py             # RRD database operations
│   └── html.py            # HTML/chart generation
├── scripts/               # Executable scripts (cron-friendly)
│   ├── phase1_collect_companion.py
│   ├── phase1_collect_repeater.py
│   ├── phase2_rrd_update_companion.py
│   ├── phase2_rrd_update_repeater.py
│   ├── phase2_render_charts.py
│   ├── phase3_render_site.py
│   ├── backfill_rrd.py    # Rebuild RRD from historical snapshots
│   └── rsync_output.sh    # Deploy to web server
├── data/
│   ├── snapshots/         # JSON snapshots by date
│   │   ├── companion/YYYY/MM/DD/HHMMSS.json
│   │   └── repeater/YYYY/MM/DD/HHMMSS.json
│   ├── rrd/               # RRD database files
│   │   ├── companion.rrd
│   │   └── repeater.rrd
│   └── state/             # Persistent state (circuit breaker)
│       └── repeater_circuit.json
├── out/                   # Generated static site
│   ├── day.html           # Repeater pages at root (entry point)
│   ├── week.html
│   ├── month.html
│   ├── year.html
│   ├── .htaccess          # Apache config (DirectoryIndex, cache control)
│   ├── companion/         # Companion pages (day/week/month/year.html)
│   └── assets/            # PNG chart images
│       ├── companion/
│       └── repeater/
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
- `REMOTE_RETRY_ATTEMPTS`: Number of retry attempts (default: 2)
- `REMOTE_RETRY_BACKOFF_S`: Seconds between retries (default: 4)
- `REMOTE_CB_FAILS`: Failures before circuit breaker opens (default: 6)
- `REMOTE_CB_COOLDOWN_S`: Circuit breaker cooldown (default: 3600)

### Intervals
- `COMPANION_STEP`: RRD step for companion (default: 60s)
- `REPEATER_STEP`: RRD step for repeater (default: 900s / 15min)

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
  - Binary requests (`req_status_sync`, `req_telemetry_sync`) return payload directly
- **rrdtool-bindings**: RRD database operations

## RRD Data Source Types

The RRD uses different data source types depending on the metric:

- **GAUGE**: Instantaneous values (bat_v, bat_pct, contacts, neigh, rssi, snr, uptime, noise, txq)
- **DERIVE**: Counter values that show rate of change - stored as per-second rate, displayed as per-minute:
  - `rx`, `tx` - Total packet counters
  - `airtime`, `rx_air` - TX/RX airtime in seconds
  - `fl_dups`, `di_dups` - Duplicate packet counters (flood/direct)
  - `fl_tx`, `fl_rx` - Flood packet counters
  - `di_tx`, `di_rx` - Direct packet counters

When changing DS types or adding new metrics, you must delete the RRD files and recreate them.

## Derived Fields

The phase2 update scripts calculate derived fields that aren't directly in the snapshots:

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
  "telemetry": [
    {"channel": 1, "type": "voltage", "value": 4.02}
  ]
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

### Phase 2: RRD Update & Chart Rendering

```bash
# Update companion RRD from latest snapshot
python scripts/phase2_rrd_update_companion.py

# Update repeater RRD from latest snapshot
python scripts/phase2_rrd_update_repeater.py

# Render all charts (day/week/month/year for all metrics)
python scripts/phase2_render_charts.py
```

### Phase 3: HTML Generation

```bash
# Generate static site pages
python scripts/phase3_render_site.py
```

### Backfill Historical Data

After recreating RRD files (e.g., after changing metrics), use backfill to import historical snapshots:

```bash
# Delete existing RRD files
rm data/rrd/*.rrd

# Backfill from all historical snapshots
python scripts/backfill_rrd.py all

# Or just one role
python scripts/backfill_rrd.py companion
python scripts/backfill_rrd.py repeater
```

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

### Tooltips
- CSS-only tooltips using `data-tooltip` attribute
- Work on desktop (hover) and mobile (tap via `tabindex="0"` + `:focus`)
- Show descriptions for technical metrics (RSSI, SNR, etc.)

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

Charts are generated at 800x280 pixels with the following features:
- 2 charts per row on desktop, 1 on mobile (< 900px)
- Design system colors matching the UI (primary blue #2563eb)
- Semi-transparent area fill with solid line on top
- Min/Avg/Max/Current statistics displayed below each chart
- Larger fonts (12-14pt) for readability when scaled down
- White background, no borders, slope mode for smooth lines

### Battery Smoothing

Battery voltage and percentage charts (`bat_v`, `bat_pct`) use RRD's TREND function to apply a 2-hour centered rolling average. This smoothing is applied at chart render time and does not affect the stored data.

**Why smoothing is needed:**
- Remote repeater queries over LoRa have variable response times due to mesh routing and airtime contention
- Battery readings can fluctuate slightly between measurements due to load variations
- Without smoothing, charts show noisy sawtooth patterns that obscure the actual discharge trend
- 2-hour window provides good balance between responsiveness and stability

The smoothing is implemented in `src/meshmon/rrd.py` by creating a TREND CDEF:
```
CDEF:bat_v=bat_v_scaled,7200,TREND
```

This applies a centered moving average over 7200 seconds (2 hours), effectively filtering out short-term noise while preserving the overall discharge pattern.

### Repeater Metrics Summary

| Metric | Source | RRD Type | Display Unit | Description |
|--------|--------|----------|--------------|-------------|
| `bat_v` | `derived.bat_v` | GAUGE | Voltage (V) | Battery voltage |
| `bat_pct` | `derived.bat_pct` | GAUGE | Battery (%) | Battery percentage |
| `rx` | `derived.rx` | DERIVE | Packets/min | Total packets received |
| `tx` | `derived.tx` | DERIVE | Packets/min | Total packets transmitted |
| `rssi` | `derived.rssi` | GAUGE | RSSI (dBm) | Signal strength of last packet |
| `snr` | `derived.snr` | GAUGE | SNR (dB) | Signal-to-noise ratio |
| `uptime` | `status.uptime` | GAUGE | Hours | Time since reboot (seconds ÷ 3600) |
| `noise` | `status.noise_floor` | GAUGE | dBm | Background RF noise |
| `airtime` | `status.airtime` | DERIVE | Seconds/min | TX airtime rate |
| `rx_air` | `status.rx_airtime` | DERIVE | Seconds/min | RX airtime rate |
| `fl_dups` | `status.flood_dups` | DERIVE | Packets/min | Flood duplicate packets |
| `di_dups` | `status.direct_dups` | DERIVE | Packets/min | Direct duplicate packets |
| `fl_tx` | `status.sent_flood` | DERIVE | Packets/min | Flood packets transmitted |
| `fl_rx` | `status.recv_flood` | DERIVE | Packets/min | Flood packets received |
| `di_tx` | `status.sent_direct` | DERIVE | Packets/min | Direct packets transmitted |
| `di_rx` | `status.recv_direct` | DERIVE | Packets/min | Direct packets received |
| `txq` | `status.tx_queue_len` | GAUGE | Queue depth | TX queue length |

### Companion Metrics Summary

| Metric | Source | RRD Type | Display Unit | Description |
|--------|--------|----------|--------------|-------------|
| `bat_v` | `derived.bat_v` | GAUGE | Voltage (V) | Battery voltage |
| `bat_pct` | `derived.bat_pct` | GAUGE | Battery (%) | Battery percentage |
| `contacts` | `derived.contacts_count` | GAUGE | Count | Known mesh nodes |
| `rx` | `stats.packets.recv` | DERIVE | Packets/min | Total packets received |
| `tx` | `stats.packets.sent` | DERIVE | Packets/min | Total packets transmitted |
| `uptime` | `stats.core.uptime_secs` | GAUGE | Hours | Time since reboot (seconds ÷ 3600) |

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

Check RRD data:
```bash
# View RRD info
rrdtool info data/rrd/companion.rrd

# Fetch recent data
rrdtool fetch data/rrd/companion.rrd AVERAGE --start -1h
```

Test with meshcore-cli:
```bash
meshcore-cli -s /dev/ttyACM0 contacts
meshcore-cli -s /dev/ttyACM0 req_status "repeater name"
meshcore-cli -s /dev/ttyACM0 reset_path "repeater name"
```

## Known Issues

1. **Repeater not responding**: If `req_status_sync` and `req_telemetry_sync` timeout, the repeater may:
   - Not support binary protocol requests
   - Have incorrect admin password configured
   - Have routing issues (asymmetric path)
   - Be offline or rebooted

2. **Environment variables not loaded**: Scripts must be run with direnv active or manually source `.envrc`

3. **RRD update errors**:
   - "not a simple signed integer" - DERIVE data sources require integer values for counter metrics
   - "illegal attempt to update" - timestamps must be strictly increasing; wait at least 1 second between updates

4. **Empty charts**: Need at least 2 data points for RRD to calculate averages. Use backfill script to populate historical data.

## Cron Setup (Example)

**Important**: Stagger companion and repeater collection to avoid USB serial conflicts.

```cron
# Companion: every minute at :00
* * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase1_collect_companion.py && .direnv/python-3.12.3/bin/python scripts/phase2_rrd_update_companion.py

# Repeater: every 15 minutes at :01, :16, :31, :46 (offset by 1 min to avoid USB conflict)
1,16,31,46 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase1_collect_repeater.py && .direnv/python-3.12.3/bin/python scripts/phase2_rrd_update_repeater.py

# Charts: every 5 minutes
*/5 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase2_render_charts.py

# HTML: every 5 minutes
*/5 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase3_render_site.py

# Deploy: every 5 minutes (after removing --dry-run from script)
*/5 * * * * cd /home/jorijn/apps/meshcore-stats && ./scripts/rsync_output.sh
```

## Adding New Metrics

1. Add the metric to `COMPANION_METRICS` or `REPEATER_METRICS` in `.envrc`
2. If the metric needs calculation, add it to `build_merged_view()` in the corresponding phase2 update script and backfill script
3. Delete existing RRD files: `rm data/rrd/*.rrd`
4. Reload direnv: `direnv allow`
5. Backfill historical data: `python scripts/backfill_rrd.py all`
6. Add label in `render_all_charts()` in `src/meshmon/rrd.py`
7. Regenerate charts and site

## Changing RRD Data Source Types

Metric type configuration is centralized in `src/meshmon/metrics.py`:

- `COUNTER_METRICS`: Set of metrics that use DERIVE (rate of change)
- `GRAPH_SCALING`: Dict of metric → scale factor for display

If you need to change a metric from GAUGE to DERIVE (or vice versa):

1. Update `COUNTER_METRICS` in `src/meshmon/metrics.py`
2. Update `GRAPH_SCALING` if the metric needs display scaling (e.g., ×60 for per-minute)
3. Delete existing RRD files: `rm data/rrd/*.rrd`
4. Backfill: `python scripts/backfill_rrd.py all`
