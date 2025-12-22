# CLAUDE.md - MeshCore Stats Project Guide

## Project Overview

This project monitors a MeshCore LoRa mesh network consisting of:
- **1 Companion node**: Connected via USB serial to a NUC (local device)
- **1 Remote repeater**: Reachable over LoRa from the companion

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
│   ├── index.html
│   ├── .htaccess          # Apache cache control
│   ├── companion/         # Companion pages (day/week/month/year.html)
│   ├── repeater/          # Repeater pages (day/week/month/year.html)
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
COMPANION_METRICS="bat_v=derived.bat_v,bat_pct=derived.bat_pct,contacts=derived.contacts_count,rx=stats.packets.recv,tx=stats.packets.sent"
REPEATER_METRICS="bat_v=derived.bat_v,bat_pct=derived.bat_pct,neigh=derived.neighbours_count,rx=derived.rx,tx=derived.tx,rssi=derived.rssi,snr=derived.snr"
```

## Key Dependencies

- **meshcore**: Python library for MeshCore device communication
  - Commands accessed via `mc.commands.method_name()`
  - Contacts returned as dict keyed by public key
  - Binary requests (`req_status_sync`, `req_telemetry_sync`) return payload directly
- **rrdtool-bindings**: RRD database operations

## RRD Data Source Types

The RRD uses different data source types depending on the metric:

- **GAUGE**: Instantaneous values (bat_v, bat_pct, contacts, neigh, rssi, snr)
- **DERIVE**: Counter values that show rate of change (rx, tx) - stored as packets/sec, displayed as packets/min

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

## Chart Configuration

Charts are generated at 800x300 pixels with the following layout:
- 2 charts per row on desktop
- 1 chart per row on mobile (< 900px)

Chart labels:
- `bat_v`: "Voltage (V)"
- `bat_pct`: "Battery (%)"
- `contacts`: "Count"
- `neigh`: "Count"
- `rx`: "Packets/min" (scaled from per-second DERIVE)
- `tx`: "Packets/min" (scaled from per-second DERIVE)
- `rssi`: "RSSI (dBm)"
- `snr`: "SNR (dB)"

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

```cron
# Companion: every minute
* * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase1_collect_companion.py && .direnv/python-3.12.3/bin/python scripts/phase2_rrd_update_companion.py

# Repeater: every 15 minutes
*/15 * * * * cd /home/jorijn/apps/meshcore-stats && .direnv/python-3.12.3/bin/python scripts/phase1_collect_repeater.py && .direnv/python-3.12.3/bin/python scripts/phase2_rrd_update_repeater.py

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

If you need to change a metric from GAUGE to DERIVE (or vice versa):

1. Update the `counter_metrics` set in `create_rrd()` function in `src/meshmon/rrd.py`
2. Update the `counter_metrics` set in `update_rrd()` function (for integer formatting)
3. Update the `counter_metrics` set in `graph_rrd()` function (for scaling)
4. Delete existing RRD files: `rm data/rrd/*.rrd`
5. Backfill: `python scripts/backfill_rrd.py all`
