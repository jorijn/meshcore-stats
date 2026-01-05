# MeshCore Stats

A Python-based monitoring system for a MeshCore repeater node and its companion. Collects metrics from both devices, stores them in a SQLite database, and generates a static website with interactive SVG charts and statistics.

**Live demo:** [meshcore.jorijn.com](https://meshcore.jorijn.com)

<p>
  <img src="docs/screenshot-1.png" width="49%" alt="MeshCore Stats Dashboard">
  <img src="docs/screenshot-2.png" width="49%" alt="MeshCore Stats Reports">
</p>

## Features

- **Data Collection** - Collect metrics from companion (local) and repeater (remote) nodes
- **Chart Rendering** - Generate interactive SVG charts from the database using matplotlib
- **Static Site** - Generate a static HTML website with day/week/month/year views
- **Reports** - Generate monthly and yearly statistics reports

## Requirements

### Python Dependencies

- Python 3.10+
- meshcore >= 2.2.3
- pyserial >= 3.5
- jinja2 >= 3.1.0
- matplotlib >= 3.8.0

### System Dependencies

- sqlite3 (for database maintenance script)

## Setup

### 1. Create Virtual Environment

```bash
cd /path/to/meshcore-stats
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Copy the example configuration file and customize it:

```bash
cp meshcore.conf.example meshcore.conf
# Edit meshcore.conf with your settings
```

The configuration file is automatically loaded by the scripts. Key settings to configure:

- **Connection**: `MESH_SERIAL_PORT`, `MESH_TRANSPORT`
- **Repeater Identity**: `REPEATER_NAME`, `REPEATER_PASSWORD`
- **Display Names**: `REPEATER_DISPLAY_NAME`, `COMPANION_DISPLAY_NAME`
- **Location**: `REPORT_LOCATION_NAME`, `REPORT_LAT`, `REPORT_LON`, `REPORT_ELEV`
- **Hardware Info**: `REPEATER_HARDWARE`, `COMPANION_HARDWARE`
- **Radio Config**: `RADIO_FREQUENCY`, `RADIO_BANDWIDTH`, etc. (includes presets for different regions)

See `meshcore.conf.example` for all available options with documentation.

## Usage

### Manual Execution

```bash
cd /path/to/meshcore-stats
source .venv/bin/activate

# Collect companion data
python scripts/collect_companion.py

# Collect repeater data
python scripts/collect_repeater.py

# Generate static site (includes chart rendering)
python scripts/render_site.py

# Generate reports
python scripts/render_reports.py
```

The configuration is automatically loaded from `meshcore.conf`.

### Cron Setup

Add these entries to your crontab (`crontab -e`):

```cron
# MeshCore Stats - adjust path as needed
MESHCORE=/home/user/meshcore-stats

# Every minute: collect companion data
* * * * * cd $MESHCORE && flock -w 60 /tmp/meshcore.lock .venv/bin/python scripts/collect_companion.py

# Every 15 minutes: collect repeater data
1,16,31,46 * * * * cd $MESHCORE && flock -w 60 /tmp/meshcore.lock .venv/bin/python scripts/collect_repeater.py

# Every 5 minutes: render site
*/5 * * * * cd $MESHCORE && .venv/bin/python scripts/render_site.py

# Daily at midnight: generate reports
0 0 * * * cd $MESHCORE && .venv/bin/python scripts/render_reports.py

# Monthly at 3 AM on the 1st: database maintenance
0 3 1 * * $MESHCORE/scripts/db_maintenance.sh
```

**Notes:**
- `cd $MESHCORE` is required because paths in the config are relative to the project root
- `flock` prevents USB serial conflicts when companion and repeater collection overlap

### Docker Installation

The recommended way to run MeshCore Stats is with Docker Compose. This provides automatic scheduling of all collection and rendering tasks.

#### Quick Start

```bash
# Clone the repository
git clone https://github.com/jorijn/meshcore-stats.git
cd meshcore-stats

# Create configuration
cp meshcore.conf.example meshcore.conf
# Edit meshcore.conf with your settings

# Create data directories with correct ownership for container (UID 1000)
mkdir -p data/state out
sudo chown -R 1000:1000 data out
# Alternative: chmod -R 777 data out (less secure, use chown if possible)

# Start the containers
docker compose up -d

# View logs
docker compose logs -f
```

The web interface will be available at `http://localhost:8080`.

#### Architecture

The Docker setup uses two containers:

| Container | Purpose |
|-----------|---------|
| `meshcore-stats` | Runs Ofelia scheduler for data collection and rendering |
| `nginx` | Serves the static website |

#### Configuration

Configuration is loaded from `meshcore.conf` via the `env_file` directive. Key settings:

```bash
# Required: Serial device for companion node
MESH_SERIAL_PORT=/dev/ttyUSB0  # Adjust for your system

# Required: Repeater identity
REPEATER_NAME="Your Repeater Name"
REPEATER_PASSWORD="your-password"

# Display names (shown in UI)
REPEATER_DISPLAY_NAME="My Repeater"
COMPANION_DISPLAY_NAME="My Companion"
```

See `meshcore.conf.example` for all available options.

#### Serial Device Access

The container needs access to your USB serial device. To customize the device path without modifying the tracked `docker-compose.yml`, create a `docker-compose.override.yml` file (gitignored):

```yaml
# docker-compose.override.yml - Local overrides (not tracked in git)
services:
  meshcore-stats:
    devices:
      - /dev/ttyACM0:/dev/ttyACM0:rw  # Your device path
```

This file is automatically merged with `docker-compose.yml` when running `docker compose up`.

On the host, ensure the device is accessible:

```bash
# Add user to dialout group (Linux)
sudo usermod -a -G dialout $USER
# Log out and back in for changes to take effect
```

#### Development Mode

For local development with live code changes:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

This mounts `src/` and `scripts/` into the container, so changes take effect immediately without rebuilding.

#### Image Tags

Images are published to `ghcr.io/jorijn/meshcore-stats`:

| Tag | Description |
|-----|-------------|
| `X.Y.Z` | Specific version (e.g., `0.3.0`) |
| `latest` | Latest release |
| `nightly` | Latest release rebuilt with OS patches |
| `nightly-YYYYMMDD` | Dated nightly build |

Version tags are rebuilt nightly to include OS security patches. For reproducible deployments, pin by SHA digest:

```yaml
image: ghcr.io/jorijn/meshcore-stats@sha256:abc123...
```

#### Volumes

| Path | Purpose |
|------|---------|
| `./data/state` | SQLite database and circuit breaker state |
| `./out` | Generated static site (served by nginx) |

Both directories must be writable by UID 1000 (the container user). See Quick Start for setup.

#### Resource Limits

Default resource limits in `docker-compose.yml`:

| Container | CPU | Memory |
|-----------|-----|--------|
| meshcore-stats | 1.0 | 512MB |
| nginx | 0.5 | 64MB |

Adjust in `docker-compose.yml` if needed.

#### Important Notes

- **Single instance only**: SQLite uses WAL mode which requires exclusive access. Do not run multiple container instances.
- **Persistent storage**: Mount `./data/state` to preserve your database across container restarts.
- **Health checks**: Both containers have health checks. Use `docker compose ps` to verify status.

Environment variables always take precedence over `meshcore.conf`.

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
├── meshcore.conf.example       # Example configuration
├── meshcore.conf               # Your configuration (create this)
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
│   ├── metrics.py              # Metric type definitions
│   ├── battery.py              # Battery voltage to percentage conversion
│   ├── migrations/             # SQL schema migrations
│   │   ├── 001_initial_schema.sql
│   │   └── 002_eav_schema.sql
│   └── templates/              # Jinja2 HTML templates
├── scripts/
│   ├── collect_companion.py    # Collect metrics from companion node
│   ├── collect_repeater.py     # Collect metrics from repeater node
│   ├── render_charts.py        # Generate SVG charts from database
│   ├── render_site.py          # Generate static HTML site
│   ├── render_reports.py       # Generate monthly/yearly reports
│   └── db_maintenance.sh       # Database VACUUM/ANALYZE
├── data/
│   └── state/
│       ├── metrics.db          # SQLite database (WAL mode)
│       └── repeater_circuit.json
└── out/                        # Generated site
    ├── .htaccess               # Apache config (DirectoryIndex, caching)
    ├── styles.css              # Stylesheet
    ├── chart-tooltip.js        # Chart tooltip enhancement
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

### Docker on macOS: Serial Devices Not Available

Docker on macOS (including Docker Desktop and OrbStack) runs containers inside a Linux virtual machine. USB and serial devices connected to the Mac host cannot be passed through to this VM, so the `devices:` section in docker-compose.yml will fail with:

```
error gathering device information while adding custom device "/dev/cu.usbserial-0001": no such file or directory
```

**Workarounds:**

1. **Use TCP transport**: Run a serial-to-TCP bridge on the host and configure the container to connect via TCP:
   ```bash
   # On macOS host, expose serial port over TCP (install socat via Homebrew)
   socat TCP-LISTEN:5000,fork,reuseaddr OPEN:/dev/cu.usbserial-0001,rawer,nonblock,ispeed=115200,ospeed=115200
   ```
   Then configure in meshcore.conf:
   ```bash
   MESH_TRANSPORT=tcp
   MESH_TCP_HOST=host.docker.internal
   MESH_TCP_PORT=5000
   ```

2. **Run natively on macOS**: Use the cron-based setup instead of Docker (see "Cron Setup" section).

3. **Use a Linux host**: Docker on Linux can pass through USB devices directly.

Note: OrbStack has [USB passthrough on their roadmap](https://github.com/orbstack/orbstack/issues/89) but it is not yet available.

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| **Connection** | | |
| `MESH_TRANSPORT` | serial | Connection type: serial, tcp, ble |
| `MESH_SERIAL_PORT` | (auto) | Serial port path |
| `MESH_SERIAL_BAUD` | 115200 | Baud rate |
| `MESH_TCP_HOST` | localhost | TCP host |
| `MESH_TCP_PORT` | 5000 | TCP port |
| `MESH_BLE_ADDR` | - | BLE device address |
| `MESH_BLE_PIN` | - | BLE PIN |
| `MESH_DEBUG` | 0 | Enable debug output |
| **Repeater Identity** | | |
| `REPEATER_NAME` | - | Repeater advertised name |
| `REPEATER_KEY_PREFIX` | - | Repeater public key prefix |
| `REPEATER_PASSWORD` | - | Repeater login password |
| **Display Names** | | |
| `REPEATER_DISPLAY_NAME` | Repeater Node | Display name for repeater in UI |
| `COMPANION_DISPLAY_NAME` | Companion Node | Display name for companion in UI |
| **Location** | | |
| `REPORT_LOCATION_NAME` | Your Location | Full location name for reports |
| `REPORT_LOCATION_SHORT` | Your Location | Short location for sidebar/meta |
| `REPORT_LAT` | 0.0 | Latitude in decimal degrees |
| `REPORT_LON` | 0.0 | Longitude in decimal degrees |
| `REPORT_ELEV` | 0.0 | Elevation |
| `REPORT_ELEV_UNIT` | m | Elevation unit: "m" or "ft" |
| **Hardware Info** | | |
| `REPEATER_HARDWARE` | LoRa Repeater | Repeater hardware model for sidebar |
| `COMPANION_HARDWARE` | LoRa Node | Companion hardware model for sidebar |
| **Radio Config** | | |
| `RADIO_FREQUENCY` | 869.618 MHz | Radio frequency for display |
| `RADIO_BANDWIDTH` | 62.5 kHz | Radio bandwidth for display |
| `RADIO_SPREAD_FACTOR` | SF8 | Spread factor for display |
| `RADIO_CODING_RATE` | CR8 | Coding rate for display |
| **Intervals** | | |
| `COMPANION_STEP` | 60 | Companion data collection interval (seconds) |
| `REPEATER_STEP` | 900 | Repeater data collection interval (seconds) |
| `REMOTE_TIMEOUT_S` | 10 | Remote request timeout |
| `REMOTE_RETRY_ATTEMPTS` | 2 | Max retry attempts |
| `REMOTE_RETRY_BACKOFF_S` | 4 | Retry backoff delay |
| `REMOTE_CB_FAILS` | 6 | Failures before circuit opens |
| `REMOTE_CB_COOLDOWN_S` | 3600 | Circuit breaker cooldown |
| **Paths** | | |
| `STATE_DIR` | ./data/state | State file path |
| `OUT_DIR` | ./out | Output site path |

## Metrics Reference

The system uses an EAV (Entity-Attribute-Value) schema where firmware field names are stored directly in the database. This allows new metrics to be captured automatically without schema changes.

### Repeater Metrics

| Metric | Type | Display Unit | Description |
|--------|------|--------------|-------------|
| `bat` | Gauge | Voltage (V) | Battery voltage (stored in mV, displayed as V) |
| `bat_pct` | Gauge | Battery (%) | Battery percentage (computed from voltage) |
| `last_rssi` | Gauge | RSSI (dBm) | Signal strength of last packet |
| `last_snr` | Gauge | SNR (dB) | Signal-to-noise ratio |
| `noise_floor` | Gauge | dBm | Background RF noise |
| `uptime` | Gauge | Days | Time since reboot (seconds ÷ 86400) |
| `tx_queue_len` | Gauge | Queue depth | TX queue length |
| `nb_recv` | Counter | Packets/min | Total packets received |
| `nb_sent` | Counter | Packets/min | Total packets transmitted |
| `airtime` | Counter | Seconds/min | TX airtime rate |
| `rx_airtime` | Counter | Seconds/min | RX airtime rate |
| `flood_dups` | Counter | Packets/min | Flood duplicate packets |
| `direct_dups` | Counter | Packets/min | Direct duplicate packets |
| `sent_flood` | Counter | Packets/min | Flood packets transmitted |
| `recv_flood` | Counter | Packets/min | Flood packets received |
| `sent_direct` | Counter | Packets/min | Direct packets transmitted |
| `recv_direct` | Counter | Packets/min | Direct packets received |

### Companion Metrics

| Metric | Type | Display Unit | Description |
|--------|------|--------------|-------------|
| `battery_mv` | Gauge | Voltage (V) | Battery voltage (stored in mV, displayed as V) |
| `bat_pct` | Gauge | Battery (%) | Battery percentage (computed from voltage) |
| `contacts` | Gauge | Count | Known mesh nodes |
| `uptime_secs` | Gauge | Days | Time since reboot (seconds ÷ 86400) |
| `recv` | Counter | Packets/min | Total packets received |
| `sent` | Counter | Packets/min | Total packets transmitted |

### Metric Types

- **Gauge**: Instantaneous values stored as-is (battery voltage, RSSI, queue depth)
- **Counter**: Cumulative values where the rate of change is calculated (packets, airtime). Charts display per-minute rates.

## Database

Metrics are stored in a SQLite database at `data/state/metrics.db` with WAL mode enabled for concurrent read/write access.

### Schema Migrations

Database migrations are stored as SQL files in `src/meshmon/migrations/` and are applied automatically when the database is initialized. Migration files follow the naming convention `NNN_description.sql` (e.g., `001_initial_schema.sql`).

## Public Instances

A list of publicly accessible MeshCore Stats installations. Want to add yours? [Open a pull request](https://github.com/jorijn/meshcore-stats/pulls)!

| URL | Hardware | Location |
|-----|----------|----------|
| [meshcore.jorijn.com](https://meshcore.jorijn.com) | SenseCAP Solar Node P1 Pro + 6.5dBi Mikrotik antenna | Oosterhout, The Netherlands |

## License

MIT
