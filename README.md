# MeshCore Stats

A Python-based monitoring system for MeshCore networks. Collects metrics from companion and repeater nodes, stores them in a SQLite database, and generates a static website with interactive SVG charts and statistics.

## Features

- **Phase 1: Data Collection** - Collect metrics from companion (local) and repeater (remote) nodes
- **Phase 2: Chart Rendering** - Generate interactive SVG charts from database using matplotlib
- **Phase 3: Static Site** - Generate a static HTML website with day/week/month/year views
- **Phase 4: Reports** - Generate monthly and yearly statistics reports

## Requirements

### Python Dependencies

- Python 3.10+
- meshcore >= 2.2.3
- pyserial >= 3.5
- jinja2 >= 3.1.0
- matplotlib >= 3.8.0

## Setup

### 1. Create Virtual Environment

```bash
cd /path/to/meshcore-stats
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.envrc` file (for direnv) or export variables manually:

```bash
# .envrc example

# Connection settings
export MESH_TRANSPORT=serial
export MESH_SERIAL_PORT=/dev/ttyUSB0  # Optional: auto-detects if not set
export MESH_SERIAL_BAUD=115200
export MESH_DEBUG=0

# Remote repeater identity
export REPEATER_NAME="my-repeater"
# export REPEATER_KEY_PREFIX="a1b2c3"  # Alternative to name
# export REPEATER_PASSWORD="secret"   # Optional login password

# Intervals
export COMPANION_STEP=60
export REPEATER_STEP=900
export REMOTE_TIMEOUT_S=10
export REMOTE_RETRY_ATTEMPTS=2
export REMOTE_RETRY_BACKOFF_S=4
export REMOTE_CB_FAILS=6
export REMOTE_CB_COOLDOWN_S=3600

# Paths (relative to project root)
export DATA_DIR=./data
export STATE_DIR=./data/state
export OUT_DIR=./out

# Optional: fetch ACL from repeater
export REPEATER_FETCH_ACL=0
```

If using direnv:
```bash
direnv allow
```

## Usage

### Manual Execution

```bash
# Collect companion data
python scripts/phase1_collect_companion.py

# Collect repeater data
python scripts/phase1_collect_repeater.py

# Generate static site (includes chart rendering)
python scripts/phase3_render_site.py

# Generate reports
python scripts/phase4_render_reports.py
```

### Cron Setup

Add these entries to your crontab (`crontab -e`):

```cron
# MeshCore Stats - adjust paths as needed
SHELL=/bin/bash
MESHCORE_STATS=/home/user/meshcore-stats
DIRENV=/usr/bin/direnv

# Every minute: collect companion data
* * * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase1_collect_companion.py

# Every 15 minutes: collect repeater data
*/15 * * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase1_collect_repeater.py

# Every 5 minutes: render site
*/5 * * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase3_render_site.py

# Daily at midnight: generate reports
0 0 * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase4_render_reports.py
```

### Serving the Site

The static site is generated in the `out/` directory. You can serve it with any web server:

```bash
# Simple Python server for testing
cd out && python3 -m http.server 8080

# Or configure nginx/caddy to serve the out/ directory
```

## Project Structure

```
meshcore-stats/
├── requirements.txt
├── README.md
├── .envrc                      # Environment variables (create this)
├── src/meshmon/
│   ├── __init__.py
│   ├── env.py                  # Environment variable parsing
│   ├── log.py                  # Logging helper
│   ├── meshcore_client.py      # MeshCore connection and commands
│   ├── db.py                   # SQLite database module
│   ├── retry.py                # Retry logic and circuit breaker
│   ├── charts.py               # Matplotlib SVG chart generation
│   ├── html.py                 # HTML rendering
│   ├── reports.py              # Report generation
│   ├── migrations/             # SQL schema migrations
│   │   └── 001_initial_schema.sql
│   └── templates/              # Jinja2 HTML templates
├── scripts/
│   ├── phase1_collect_companion.py
│   ├── phase1_collect_repeater.py
│   ├── phase2_render_charts.py
│   ├── phase3_render_site.py
│   ├── phase4_render_reports.py
│   └── migrate_json_to_db.py   # One-time migration from JSON
├── data/
│   └── state/
│       ├── metrics.db          # SQLite database (WAL mode)
│       └── repeater_circuit.json
└── out/                        # Generated site
    ├── day.html                # Repeater pages (entry point)
    ├── week.html
    ├── month.html
    ├── year.html
    ├── companion/
    │   ├── day.html
    │   ├── week.html
    │   ├── month.html
    │   └── year.html
    └── reports/
        ├── index.html
        ├── repeater/           # YYYY/MM reports
        └── companion/
```

## Chart Features

Charts are rendered as inline SVG using matplotlib with the following features:

- **Theme Support**: Automatic light/dark mode via CSS `prefers-color-scheme`
- **Interactive Tooltips**: Hover to see exact values and timestamps
- **Data Point Indicator**: Visual marker shows position on the chart line
- **Mobile Support**: Touch-friendly tooltips
- **Statistics**: Min/Avg/Max values displayed below each chart
- **Period Views**: Day, week, month, and year time ranges

## Troubleshooting

### Serial Device Not Found

If you see "No serial ports found" or connection fails:

1. Check that your device is connected:
   ```bash
   ls -la /dev/ttyUSB* /dev/ttyACM*
   ```

2. Check permissions (add user to dialout group):
   ```bash
   sudo usermod -a -G dialout $USER
   # Log out and back in for changes to take effect
   ```

3. Try specifying the port explicitly:
   ```bash
   export MESH_SERIAL_PORT=/dev/ttyACM0
   ```

4. Check dmesg for device detection:
   ```bash
   dmesg | tail -20
   ```

### Repeater Not Found

If the script cannot find the repeater contact:

1. The script will print all discovered contacts - check for the correct name
2. Verify REPEATER_NAME matches exactly (case-sensitive)
3. Try using REPEATER_KEY_PREFIX instead with the first 6-12 hex chars of the public key

### Circuit Breaker

If repeater collection shows "cooldown active":

1. This is normal after multiple failed remote requests
2. Wait for the cooldown period (default 1 hour) or reset manually:
   ```bash
   rm data/state/repeater_circuit.json
   ```

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `MESH_TRANSPORT` | serial | Connection type: serial, tcp, ble |
| `MESH_SERIAL_PORT` | (auto) | Serial port path |
| `MESH_SERIAL_BAUD` | 115200 | Baud rate |
| `MESH_TCP_HOST` | localhost | TCP host |
| `MESH_TCP_PORT` | 5000 | TCP port |
| `MESH_BLE_ADDR` | - | BLE device address |
| `MESH_BLE_PIN` | - | BLE PIN |
| `MESH_DEBUG` | 0 | Enable debug output |
| `REPEATER_NAME` | - | Repeater advertised name |
| `REPEATER_KEY_PREFIX` | - | Repeater public key prefix |
| `REPEATER_PASSWORD` | - | Repeater login password |
| `REPEATER_FETCH_ACL` | 0 | Also fetch ACL from repeater |
| `COMPANION_STEP` | 60 | Companion data collection interval (seconds) |
| `REPEATER_STEP` | 900 | Repeater data collection interval (seconds) |
| `REMOTE_TIMEOUT_S` | 10 | Remote request timeout |
| `REMOTE_RETRY_ATTEMPTS` | 2 | Max retry attempts |
| `REMOTE_RETRY_BACKOFF_S` | 4 | Retry backoff delay |
| `REMOTE_CB_FAILS` | 6 | Failures before circuit opens |
| `REMOTE_CB_COOLDOWN_S` | 3600 | Circuit breaker cooldown |
| `DATA_DIR` | ./data | Data directory (contains metrics.db) |
| `STATE_DIR` | ./data/state | State file path |
| `OUT_DIR` | ./out | Output site path |

## Metrics Reference

### Repeater Metrics

| Metric | Source Path | Type | Display Unit | Description |
|--------|-------------|------|--------------|-------------|
| `bat_v` | `derived.bat_v` | Gauge | Voltage (V) | Battery voltage (from status.bat / 1000) |
| `bat_pct` | `derived.bat_pct` | Gauge | Battery (%) | Battery percentage (calculated from voltage) |
| `rx` | `derived.rx` | Counter | Packets/min | Total packets received (from status.nb_recv) |
| `tx` | `derived.tx` | Counter | Packets/min | Total packets sent (from status.nb_sent) |
| `rssi` | `derived.rssi` | Gauge | RSSI (dBm) | Last received signal strength |
| `snr` | `derived.snr` | Gauge | SNR (dB) | Last signal-to-noise ratio |
| `uptime` | `status.uptime` | Gauge | Days | Device uptime (seconds / 86400) |
| `noise` | `status.noise_floor` | Gauge | dBm | Background RF noise floor |
| `airtime` | `status.airtime` | Counter | Seconds/min | Transmit airtime rate |
| `rx_air` | `status.rx_airtime` | Counter | Seconds/min | Receive airtime rate |
| `fl_dups` | `status.flood_dups` | Counter | Packets/min | Duplicate flood packets received |
| `di_dups` | `status.direct_dups` | Counter | Packets/min | Duplicate direct packets received |
| `fl_tx` | `status.sent_flood` | Counter | Packets/min | Flood packets transmitted |
| `fl_rx` | `status.recv_flood` | Counter | Packets/min | Flood packets received |
| `di_tx` | `status.sent_direct` | Counter | Packets/min | Direct packets transmitted |
| `di_rx` | `status.recv_direct` | Counter | Packets/min | Direct packets received |
| `txq` | `status.tx_queue_len` | Gauge | Queue depth | Current transmit queue length |

### Companion Metrics

| Metric | Source Path | Type | Display Unit | Description |
|--------|-------------|------|--------------|-------------|
| `bat_v` | `derived.bat_v` | Gauge | Voltage (V) | Battery voltage |
| `bat_pct` | `derived.bat_pct` | Gauge | Battery (%) | Battery percentage (calculated from voltage) |
| `contacts` | `derived.contacts_count` | Gauge | Count | Number of known contacts |
| `rx` | `stats.packets.recv` | Counter | Packets/min | Packets received |
| `tx` | `stats.packets.sent` | Counter | Packets/min | Packets sent |
| `uptime` | `stats.core.uptime_secs` | Gauge | Days | Device uptime (seconds / 86400) |

### Metric Types

- **Gauge**: Instantaneous values stored as-is (battery voltage, RSSI, queue depth)
- **Counter**: Cumulative values where the rate of change is calculated (packets, airtime). Charts display per-minute rates.

## Database

Metrics are stored in a SQLite database at `data/state/metrics.db` with WAL mode enabled for concurrent read/write access.

### Schema Migrations

Database migrations are stored as SQL files in `src/meshmon/migrations/` and are applied automatically when the database is initialized. Migration files follow the naming convention `NNN_description.sql` (e.g., `001_initial_schema.sql`).

### Migrating from JSON Snapshots

If you have existing JSON snapshots, you can migrate them to the SQLite database:

```bash
python scripts/migrate_json_to_db.py
```

This will scan all JSON snapshots in `data/snapshots/` and import them into the database, computing derived fields (like battery percentage) along the way.

## License

MIT
