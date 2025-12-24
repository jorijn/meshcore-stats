# MeshCore Stats

A Python-based monitoring system for MeshCore networks. Collects metrics from companion and repeater nodes, stores them in RRD databases, and generates a static website with charts and statistics.

## Features

- **Phase 1: Data Collection** - Collect metrics from companion (local) and repeater (remote) nodes
- **Phase 2: RRD Storage & Charts** - Store time-series data in RRD files and generate PNG charts
- **Phase 3: Static Site** - Generate a static HTML website with day/week/month/year views

## Requirements

### System Dependencies

Install these before setting up the Python environment:

```bash
# Debian/Ubuntu
sudo apt-get install gcc librrd-dev python3-dev

# Fedora/RHEL
sudo dnf install gcc rrdtool-devel python3-devel

# Arch Linux
sudo pacman -S gcc rrdtool python
```

### Python Dependencies

- Python 3.10+
- meshcore >= 2.2.3
- rrdtool-bindings >= 0.5.0
- pyserial >= 3.5
- jinja2 >= 3.1.0

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
export SNAPSHOT_DIR=./data/snapshots
export RRD_DIR=./data/rrd
export STATE_DIR=./data/state
export OUT_DIR=./out

# Metric mappings (ds_name=dotted.path)
export COMPANION_METRICS="bat_v=bat.voltage_v,contacts=derived.contacts_count,rx=stats.rx_packets,tx=stats.tx_packets"
export REPEATER_METRICS="bat_v=telemetry.bat,bat_pct=telemetry.bat_pct,neigh=derived.neighbours_count,rx=telemetry.rx_packets,tx=telemetry.tx_packets,rssi=status.rssi,snr=status.snr"

# Optional: fetch ACL from repeater
export REPEATER_FETCH_ACL=0
```

If using direnv:
```bash
direnv allow
```

### 3. Initialize RRD Files

```bash
python scripts/phase2_rrd_init.py
```

## Usage

### Manual Execution

```bash
# Collect companion data
python scripts/phase1_collect_companion.py

# Collect repeater data
python scripts/phase1_collect_repeater.py

# Update RRDs with latest snapshots
python scripts/phase2_rrd_update_companion.py
python scripts/phase2_rrd_update_repeater.py

# Generate charts
python scripts/phase2_render_charts.py

# Generate static site
python scripts/phase3_render_site.py
```

### Cron Setup

Add these entries to your crontab (`crontab -e`):

```cron
# MeshCore Stats - adjust paths as needed
SHELL=/bin/bash
MESHCORE_STATS=/home/user/meshcore-stats
DIRENV=/usr/bin/direnv

# Every minute: collect companion data and update RRD
* * * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase1_collect_companion.py && $DIRENV exec . python scripts/phase2_rrd_update_companion.py

# Every 15 minutes: collect repeater data and update RRD
*/15 * * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase1_collect_repeater.py && $DIRENV exec . python scripts/phase2_rrd_update_repeater.py

# Every 5 minutes: render charts and site
*/5 * * * * cd $MESHCORE_STATS && $DIRENV exec . python scripts/phase2_render_charts.py && $DIRENV exec . python scripts/phase3_render_site.py
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
│   ├── jsondump.py             # JSON snapshot I/O
│   ├── retry.py                # Retry logic and circuit breaker
│   ├── extract.py              # Metric extraction from payloads
│   ├── rrd.py                  # RRD create/update/graph
│   └── html.py                 # HTML rendering
├── scripts/
│   ├── phase1_collect_companion.py
│   ├── phase1_collect_repeater.py
│   ├── phase2_rrd_init.py
│   ├── phase2_rrd_update_companion.py
│   ├── phase2_rrd_update_repeater.py
│   ├── phase2_render_charts.py
│   └── phase3_render_site.py
├── data/
│   ├── snapshots/
│   │   ├── companion/          # YYYY/MM/DD/HHMMSS.json
│   │   └── repeater/
│   ├── rrd/
│   │   ├── companion.rrd
│   │   └── repeater.rrd
│   └── state/
│       └── repeater_circuit.json
└── out/                        # Generated site
    ├── index.html
    ├── assets/
    │   ├── companion/          # Chart PNGs
    │   └── repeater/
    ├── companion/
    │   ├── day.html
    │   ├── week.html
    │   ├── month.html
    │   └── year.html
    └── repeater/
        ├── day.html
        ├── week.html
        ├── month.html
        └── year.html
```

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

### RRD Update Errors

If RRD updates fail:

1. Check timestamp is not in the past (RRD rejects old updates)
2. Verify the RRD was created with correct DS names
3. Delete and recreate RRD if schema changed:
   ```bash
   rm data/rrd/*.rrd
   python scripts/phase2_rrd_init.py
   ```

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
| `COMPANION_STEP` | 60 | Companion RRD step (seconds) |
| `REPEATER_STEP` | 900 | Repeater RRD step (seconds) |
| `REMOTE_TIMEOUT_S` | 10 | Remote request timeout |
| `REMOTE_RETRY_ATTEMPTS` | 2 | Max retry attempts |
| `REMOTE_RETRY_BACKOFF_S` | 4 | Retry backoff delay |
| `REMOTE_CB_FAILS` | 6 | Failures before circuit opens |
| `REMOTE_CB_COOLDOWN_S` | 3600 | Circuit breaker cooldown |
| `SNAPSHOT_DIR` | ./data/snapshots | Snapshot storage path |
| `RRD_DIR` | ./data/rrd | RRD file path |
| `STATE_DIR` | ./data/state | State file path |
| `OUT_DIR` | ./out | Output site path |
| `COMPANION_METRICS` | (see code) | Companion metric mappings |
| `REPEATER_METRICS` | (see code) | Repeater metric mappings |

## Metrics Reference

### Repeater Metrics

| Metric | Source Path | RRD Type | Display Unit | Description |
|--------|-------------|----------|--------------|-------------|
| `bat_v` | `derived.bat_v` | GAUGE | Voltage (V) | Battery voltage (from status.bat / 1000) |
| `bat_pct` | `derived.bat_pct` | GAUGE | Battery (%) | Battery percentage (calculated from voltage) |
| `rx` | `derived.rx` | DERIVE | Packets/min | Total packets received (from status.nb_recv) |
| `tx` | `derived.tx` | DERIVE | Packets/min | Total packets sent (from status.nb_sent) |
| `rssi` | `derived.rssi` | GAUGE | RSSI (dBm) | Last received signal strength |
| `snr` | `derived.snr` | GAUGE | SNR (dB) | Last signal-to-noise ratio |
| `uptime` | `status.uptime` | GAUGE | Hours | Device uptime (seconds ÷ 3600) |
| `noise` | `status.noise_floor` | GAUGE | dBm | Background RF noise floor |
| `airtime` | `status.airtime` | DERIVE | Seconds/min | Transmit airtime rate |
| `rx_air` | `status.rx_airtime` | DERIVE | Seconds/min | Receive airtime rate |
| `fl_dups` | `status.flood_dups` | DERIVE | Packets/min | Duplicate flood packets received |
| `di_dups` | `status.direct_dups` | DERIVE | Packets/min | Duplicate direct packets received |
| `fl_tx` | `status.sent_flood` | DERIVE | Packets/min | Flood packets transmitted |
| `fl_rx` | `status.recv_flood` | DERIVE | Packets/min | Flood packets received |
| `di_tx` | `status.sent_direct` | DERIVE | Packets/min | Direct packets transmitted |
| `di_rx` | `status.recv_direct` | DERIVE | Packets/min | Direct packets received |
| `txq` | `status.tx_queue_len` | GAUGE | Queue depth | Current transmit queue length |

### Companion Metrics

| Metric | Source Path | RRD Type | Display Unit | Description |
|--------|-------------|----------|--------------|-------------|
| `bat_v` | `derived.bat_v` | GAUGE | Voltage (V) | Battery voltage |
| `bat_pct` | `derived.bat_pct` | GAUGE | Battery (%) | Battery percentage (calculated from voltage) |
| `contacts` | `derived.contacts_count` | GAUGE | Count | Number of known contacts |
| `rx` | `stats.packets.recv` | DERIVE | Packets/min | Packets received |
| `tx` | `stats.packets.sent` | DERIVE | Packets/min | Packets sent |
| `uptime` | `stats.core.uptime_secs` | GAUGE | Hours | Device uptime (seconds ÷ 3600) |

### RRD Data Source Types

- **GAUGE**: Instantaneous values stored as-is (battery voltage, RSSI, queue depth)
- **DERIVE**: Counter values that compute rate of change (packets, airtime). RRD stores the per-second rate; charts multiply by 60 to display per-minute values.

### Battery Smoothing

Battery voltage (`bat_v`) and percentage (`bat_pct`) charts use a 2-hour rolling average (TREND function) to smooth out short-term fluctuations. This is necessary because:

- **LoRa query timing variability**: Remote status requests can have unpredictable delays due to mesh routing and airtime contention
- **Measurement noise**: Battery voltage readings can fluctuate slightly between measurements
- **Better trend visibility**: Smoothing reveals the actual battery discharge pattern without visual noise

The underlying data in the RRD remains unmodified - only the chart display applies the TREND smoothing.

## License

MIT
