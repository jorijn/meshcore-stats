# AGENTS.md - MeshCore Stats Project Guide

> **Maintenance Note**: This file should always reflect the current state of the project. When making changes to the codebase (adding features, changing architecture, modifying configuration), update this document accordingly. Keep it accurate and comprehensive for future reference.

## Important: Source Files vs Generated Output

**NEVER edit files in `out/` directly** - they are generated and will be overwritten.

| Type | Source Location | Generated Output |
|------|-----------------|------------------|
| CSS | `src/meshmon/templates/styles.css` | `out/styles.css` |
| HTML templates | `src/meshmon/templates/*.html` | `out/*.html` |
| JavaScript | `src/meshmon/templates/*.js` | `out/*.js` |

Always edit the source templates, then regenerate with `python scripts/render_site.py`.

## Running Commands

**IMPORTANT: Always activate the virtual environment before running any Python commands.**

```bash
cd /path/to/meshcore-stats
source .venv/bin/activate
python scripts/render_site.py
```

Configuration is automatically loaded from `meshcore.conf` (if it exists). Environment variables always take precedence over the config file.

## Development Workflow

### Test-Driven Development (TDD)

**MANDATORY: Always write tests BEFORE implementing functionality.**

When implementing new features or fixing bugs, follow this workflow:

1. **Write the test first**
   - Create test cases that define the expected behavior
   - Tests should fail initially (red phase)
   - Cover happy path, edge cases, and error conditions

2. **Implement the minimum code to pass**
   - Write only enough code to make tests pass (green phase)
   - Don't over-engineer or add unrequested features

3. **Refactor if needed**
   - Clean up code while keeping tests green
   - Extract common patterns, improve naming

Example workflow for adding a new function:

```python
# Step 1: Write the test first (tests/unit/test_battery.py)
def test_voltage_to_percentage_at_full_charge():
    """4.20V should return 100%."""
    assert voltage_to_percentage(4.20) == 100.0

def test_voltage_to_percentage_at_empty():
    """3.00V should return 0%."""
    assert voltage_to_percentage(3.00) == 0.0

# Step 2: Run tests - they should FAIL
# Step 3: Implement the function to make tests pass
# Step 4: Run tests again - they should PASS
```

### Pre-Commit Requirements

**MANDATORY: Before committing ANY changes, run lint, type check, and tests.**

```bash
# Always run these commands before committing:
source .venv/bin/activate

# 1. Run linter (must pass with no errors)
ruff check src/ tests/ scripts/

# 2. Run type checker (must pass with no errors)
python -m mypy src/meshmon --ignore-missing-imports

# 3. Run test suite (must pass)
python -m pytest tests/ -q

# 4. Only then commit
git add . && git commit -m "..."
```

If lint, type check, or tests fail:
1. Fix all lint errors before committing
2. Fix all type errors before committing - use proper fixes, not `# type: ignore`
3. Fix all failing tests before committing
4. Never commit with `--no-verify` or skip checks

### Running Tests

```bash
# Run all tests
python -m pytest tests/

# Run with coverage report
python -m pytest tests/ --cov=src/meshmon --cov-report=term-missing

# Run specific test file
python -m pytest tests/unit/test_battery.py

# Run specific test
python -m pytest tests/unit/test_battery.py::test_voltage_to_percentage_at_full_charge

# Run tests matching a pattern
python -m pytest tests/ -k "battery"

# Run with verbose output
python -m pytest tests/ -v
```

### Test Organization

```
tests/
├── conftest.py              # Root fixtures (clean_env, tmp dirs, sample data)
├── unit/                    # Unit tests (isolated, fast)
│   ├── test_battery.py
│   ├── test_metrics.py
│   └── ...
├── database/                # Database tests (use temp SQLite)
│   ├── conftest.py          # DB-specific fixtures
│   └── test_db_*.py
├── integration/             # Integration tests (multiple components)
│   └── test_*_pipeline.py
├── charts/                  # Chart rendering tests
│   ├── conftest.py          # SVG normalization, themes
│   └── test_chart_*.py
└── snapshots/               # Golden files for snapshot testing
    ├── svg/                 # Reference SVG charts
    └── txt/                 # Reference TXT reports
```

### Coverage Requirements

- **Minimum coverage: 95%** (enforced in CI)
- Coverage is measured against `src/meshmon/`
- Run `python -m pytest tests/ --cov=src/meshmon --cov-fail-under=95`

## Commit Message Guidelines

This project uses [Conventional Commits](https://www.conventionalcommits.org/) with [release-please](https://github.com/googleapis/release-please) for automated releases. **Commit messages directly control versioning and changelog generation.**

### Format

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

### Commit Types

| Type | Description | Version Bump | Changelog Section |
|------|-------------|--------------|-------------------|
| `feat` | New feature or capability | Minor (0.1.0 → 0.2.0) | Features |
| `fix` | Bug fix | Patch (0.1.0 → 0.1.1) | Bug Fixes |
| `perf` | Performance improvement | Patch | Performance Improvements |
| `docs` | Documentation only | None | Documentation |
| `style` | Code style (formatting, whitespace) | None | Styles |
| `refactor` | Code change that neither fixes nor adds | None | Code Refactoring |
| `test` | Adding or correcting tests | None | Tests |
| `chore` | Maintenance tasks, dependencies | None | Miscellaneous Chores |
| `build` | Build system or dependencies | None | Build System |
| `ci` | CI/CD configuration | None | Continuous Integration |
| `revert` | Reverts a previous commit | Varies | Reverts |

### Breaking Changes (CRITICAL)

Breaking changes trigger a **major version bump** (0.x.x → 1.0.0 or 1.x.x → 2.0.0).

**Before marking a change as breaking, carefully consider:**

1. **Does this change the database schema?**
   - Schema changes are NOT breaking - migrations are applied automatically
   - Data loss scenarios (dropping columns with important data) should be documented but are typically NOT breaking since migrations handle them

2. **Does this change the configuration (environment variables)?**
   - Adding new optional variables is NOT breaking
   - Removing or renaming required variables IS breaking
   - Changing default behavior that users depend on IS breaking

3. **Does this change the output format?**
   - Adding new fields to JSON output is NOT breaking
   - Removing fields or changing structure IS breaking
   - Changing HTML structure that external tools parse IS breaking

4. **Does this require users to take action after upgrading?**
   - If users must run migrations, update configs, or modify their setup → likely breaking

**How to mark breaking changes:**

```bash
# Option 1: Add ! after the type
feat!: remove support for legacy database schema

# Option 2: Add BREAKING CHANGE footer
feat: migrate to new metrics format

BREAKING CHANGE: The old wide-table schema is no longer supported.
Run the migration script before upgrading.
```

### Examples

```bash
# Feature (minor bump)
feat: add noise floor metric to repeater charts

# Bug fix (patch bump)
fix: correct battery percentage calculation below 3.5V

# Performance (patch bump)
perf: reduce chart rendering time with data point caching

# Documentation (no bump, in changelog)
docs: add troubleshooting section for serial connection issues

# Refactor (no bump, in changelog)
refactor: extract chart rendering logic into separate module

# Chore (no bump, in changelog)
chore: update matplotlib to 3.9.0

# Breaking change (major bump)
feat!: change metrics database schema to EAV format

BREAKING CHANGE: Existing databases must be migrated using
scripts/migrate_to_eav.py before running the new version.
```

### Scopes (Optional)

Use scopes to clarify what part of the codebase is affected:

- `charts` - Chart rendering (`src/meshmon/charts.py`)
- `db` - Database operations (`src/meshmon/db.py`)
- `html` - HTML generation (`src/meshmon/html.py`)
- `reports` - Report generation (`src/meshmon/reports.py`)
- `collector` - Data collection scripts
- `deps` - Dependencies

Example: `fix(charts): prevent crash when no data points available`

### Release Process

1. Commits to `main` with conventional prefixes are analyzed automatically
2. release-please creates/updates a "Release PR" with:
   - Updated `CHANGELOG.md`
   - Updated version in `src/meshmon/__init__.py`
   - Updated `uv.lock` (project version entry)
3. When the Release PR is merged:
   - A GitHub Release is created
   - A git tag (e.g., `v0.2.0`) is created

## Project Overview

This project monitors a MeshCore LoRa mesh network consisting of:
- **1 Companion node**: Connected via USB serial to a local machine
- **1 Remote repeater**: Reachable over LoRa from the companion

The system collects metrics, stores them in a SQLite database, and generates a static HTML dashboard with SVG charts.

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
│   Local Host    │
│  (This System)  │
└─────────────────┘

Data Flow:
Phase 1: Collect → SQLite database
Phase 2: Render  → SVG charts (from database, using matplotlib)
Phase 3: Render  → Static HTML site (inline SVG)
Phase 4: Render  → Reports (monthly/yearly statistics)
```

## Docker Architecture

The project provides Docker containerization for easy deployment. Two containers work together:

```
┌─────────────────────────────────────────────────────────────────┐
│                     Docker Compose                               │
│  ┌─────────────────────┐    ┌─────────────────────────────────┐ │
│  │   meshcore-stats    │    │           nginx                  │ │
│  │  ┌───────────────┐  │    │                                  │ │
│  │  │    Ofelia     │  │    │   Serves static site on :8080   │ │
│  │  │  (scheduler)  │  │    │                                  │ │
│  │  └───────┬───────┘  │    └──────────────▲──────────────────┘ │
│  │          │          │                    │                    │
│  │   ┌──────▼──────┐   │         ┌─────────┴─────────┐          │
│  │   │   Python    │   │         │   output_data     │          │
│  │   │   Scripts   │───┼────────►│   (named volume)  │          │
│  │   └─────────────┘   │         └───────────────────┘          │
│  │          │          │                                         │
│  └──────────┼──────────┘                                         │
│             │                                                     │
│    ┌────────▼────────┐                                           │
│    │  ./data/state   │                                           │
│    │  (bind mount)   │                                           │
│    └─────────────────┘                                           │
└─────────────────────────────────────────────────────────────────┘
```

### Container Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build: Python + Ofelia scheduler |
| `docker-compose.yml` | Production deployment using published ghcr.io image |
| `docker-compose.dev.yml` | Development override for local builds |
| `docker-compose.override.yml` | Local overrides (gitignored) |
| `docker/ofelia.ini` | Scheduler configuration (cron jobs) |
| `docker/nginx.conf` | nginx configuration for static site serving |
| `.dockerignore` | Files excluded from Docker build context |

### Docker Compose Files

**Production** (`docker-compose.yml`):
- Uses published image from `ghcr.io/jorijn/meshcore-stats`
- Image version managed by release-please via `x-release-please-version` placeholder
- Suitable for end users

**Development** (`docker-compose.dev.yml`):
- Override file that builds locally instead of pulling from registry
- Mounts `src/` and `scripts/` for live code changes
- Usage: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`

**Local overrides** (`docker-compose.override.yml`):
- Gitignored file for local customizations (e.g., device paths, env_file)
- Automatically merged when running `docker compose up`

### Ofelia Scheduler

[Ofelia](https://github.com/mcuadros/ofelia) is a lightweight job scheduler designed for Docker. It replaces cron for container environments.

Jobs configured in `docker/ofelia.ini`:
- `collect-companion`: Every minute (with `no-overlap=true`)
- `collect-repeater`: Every 15 minutes at :01, :16, :31, :46 (with `no-overlap=true`)
- `render-charts`: Every 5 minutes
- `render-site`: Every 5 minutes
- `render-reports`: Daily at midnight
- `db-maintenance`: Monthly at 3 AM on the 1st

### GitHub Actions Workflow

`.github/workflows/docker-publish.yml` builds and publishes Docker images for `linux/amd64`, `linux/arm64`, and `linux/arm/v7`:

| Trigger | Tags Created |
|---------|--------------|
| Release | `X.Y.Z`, `X.Y`, `latest` |
| Nightly (4 AM UTC) | Rebuilds all version tags + `nightly`, `nightly-YYYYMMDD` |
| Manual | `sha-xxxxxx` |
| Pull request | Builds image (linux/amd64) without pushing and runs a smoke test |

**Nightly rebuilds** ensure version tags always include the latest OS security patches. This is a common pattern used by official Docker images (nginx, postgres, node). Users needing reproducibility should pin by SHA digest or use dated nightly tags.

GitHub Actions use version tags in workflows, and Renovate is configured in `renovate.json` to pin action digests, maintain lockfiles, and auto-merge patch + digest updates once required checks pass (with automatic rebases when behind `main`).

The test and lint workflow (`.github/workflows/test.yml`) installs dependencies with uv (`uv sync --locked --extra dev`) and runs commands via `uv run`, using `uv.lock` as the source of truth.

### Version Placeholder

The version in `docker-compose.yml` uses release-please's placeholder syntax:
```yaml
image: ghcr.io/jorijn/meshcore-stats:0.3.0 # x-release-please-version
```

This is automatically updated when a new release is created.

### Agent Review Guidelines

When reviewing Docker-related changes, always provide the **full plan or implementation** to review agents. Do not summarize or abbreviate - agents need complete context to provide accurate feedback.

Relevant agents for Docker reviews:
- **k8s-security-reviewer**: Container security, RBAC, secrets handling
- **cicd-pipeline-specialist**: GitHub Actions workflows, build pipelines
- **python-code-reviewer**: Dockerfile Python-specific issues (venv PATH, runtime libs)

## Directory Structure

```
meshcore-stats/
├── src/meshmon/           # Core library
│   ├── __init__.py
│   ├── env.py             # Environment config parsing
│   ├── log.py             # Logging utilities
│   ├── meshcore_client.py # MeshCore connection wrapper
│   ├── db.py              # SQLite database module
│   ├── retry.py           # Retry logic & circuit breaker
│   ├── charts.py          # SVG chart rendering (matplotlib)
│   ├── html.py            # HTML site generation
│   ├── metrics.py         # Metric type definitions (counter vs gauge)
│   ├── reports.py         # Report generation (WeeWX-style)
│   ├── battery.py         # 18650 Li-ion voltage to percentage conversion
│   ├── migrations/        # SQL schema migrations
│   │   ├── 001_initial_schema.sql
│   │   └── 002_eav_schema.sql
│   └── templates/         # Jinja2 HTML templates
│       ├── base.html      # Base template with head/meta tags
│       ├── node.html      # Dashboard page template
│       ├── report.html    # Individual report template
│       ├── report_index.html  # Reports archive template
│       ├── credit.html    # Reusable footer credit partial
│       ├── styles.css     # Source CSS stylesheet
│       └── chart-tooltip.js   # Source tooltip JavaScript
├── docs/                  # Documentation
│   ├── firmware-responses.md  # MeshCore firmware response formats
│   ├── battery-voltage-sources.md  # Battery voltage research
│   └── repeater-winter-solar-analysis.md
├── scripts/               # Executable scripts (cron-friendly)
│   ├── collect_companion.py      # Collect metrics from companion node
│   ├── collect_repeater.py       # Collect metrics from repeater node
│   ├── render_charts.py          # Generate SVG charts from database
│   ├── render_site.py            # Generate static HTML site
│   ├── render_reports.py         # Generate monthly/yearly reports
│   └── db_maintenance.sh         # Database VACUUM/ANALYZE
├── data/
│   └── state/             # Persistent state
│       ├── metrics.db     # SQLite database (WAL mode)
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
├── meshcore.conf.example  # Example configuration
└── meshcore.conf          # Your configuration (auto-loaded by scripts)
```

## Configuration

All configuration via `meshcore.conf` or environment variables. The config file is automatically loaded by scripts; environment variables take precedence.

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

### Telemetry Collection
- `TELEMETRY_ENABLED`: Enable environmental telemetry collection from repeater (0/1, default: 0)
- `TELEMETRY_TIMEOUT_S`: Timeout for telemetry requests (default: 10)
- `TELEMETRY_RETRY_ATTEMPTS`: Retry attempts for telemetry (default: 2)
- `TELEMETRY_RETRY_BACKOFF_S`: Backoff between telemetry retries (default: 4)

### Intervals
- `COMPANION_STEP`: Collection interval for companion (default: 60s)
- `REPEATER_STEP`: Collection interval for repeater (default: 900s / 15min)

### Location & Display
- `REPORT_LOCATION_NAME`: Full location name for reports (default: "Your Location")
- `REPORT_LOCATION_SHORT`: Short location for sidebar/meta (default: "Your Location")
- `REPORT_LAT`: Latitude in decimal degrees (default: 0.0)
- `REPORT_LON`: Longitude in decimal degrees (default: 0.0)
- `REPORT_ELEV`: Elevation (default: 0.0)
- `REPORT_ELEV_UNIT`: Elevation unit, "m" or "ft" (default: "m")
- `REPEATER_DISPLAY_NAME`: Display name for repeater in UI (default: "Repeater Node")
- `COMPANION_DISPLAY_NAME`: Display name for companion in UI (default: "Companion Node")
- `REPEATER_HARDWARE`: Repeater hardware model for sidebar (default: "LoRa Repeater")
- `COMPANION_HARDWARE`: Companion hardware model for sidebar (default: "LoRa Node")

### Radio Configuration (for display)
- `RADIO_FREQUENCY`: e.g., "869.618 MHz"
- `RADIO_BANDWIDTH`: e.g., "62.5 kHz"
- `RADIO_SPREAD_FACTOR`: e.g., "SF8"
- `RADIO_CODING_RATE`: e.g., "CR8"

### Metrics (Hardcoded)

Metrics are now hardcoded in the codebase rather than configurable via environment variables. This simplifies the system and ensures consistency between the database schema and the code.

See the "Metrics Reference" sections below for the full list of companion and repeater metrics.

## Key Dependencies

- **meshcore**: Python library for MeshCore device communication
  - Commands accessed via `mc.commands.method_name()`
  - Contacts returned as dict keyed by public key
  - Binary request `req_status_sync` returns payload directly
- **matplotlib**: SVG chart generation
- **jinja2**: HTML template rendering

## Metric Types

Metrics are classified as either **gauge** or **counter** in `src/meshmon/metrics.py`, using firmware field names directly:

- **GAUGE**: Instantaneous values
  - Companion: `battery_mv`, `bat_pct`, `contacts`, `uptime_secs`
  - Repeater: `bat`, `bat_pct`, `last_rssi`, `last_snr`, `noise_floor`, `uptime`, `tx_queue_len`

- **COUNTER**: Cumulative values that show rate of change - displayed as per-minute:
  - Companion: `recv`, `sent`
  - Repeater: `nb_recv`, `nb_sent`, `airtime`, `rx_airtime`, `flood_dups`, `direct_dups`, `sent_flood`, `recv_flood`, `sent_direct`, `recv_direct`

Counter metrics are converted to rates during chart rendering by calculating deltas between consecutive readings.

- **TELEMETRY**: Environmental sensor data (when `TELEMETRY_ENABLED=1`):
  - Stored with `telemetry.` prefix: `telemetry.temperature.0`, `telemetry.humidity.0`, `telemetry.barometer.0`
  - Channel number distinguishes multiple sensors of the same type
  - Compound values (e.g., GPS) stored as: `telemetry.gps.0.latitude`, `telemetry.gps.0.longitude`
  - Telemetry collection does NOT affect circuit breaker state

## Database Schema

Metrics are stored in a SQLite database at `data/state/metrics.db` with WAL mode enabled for concurrent access.

### EAV Schema (Entity-Attribute-Value)

The database uses an EAV schema for flexible metric storage. Firmware field names are stored directly, allowing new metrics to be captured automatically without schema changes.

```sql
CREATE TABLE metrics (
    ts INTEGER NOT NULL,      -- Unix timestamp
    role TEXT NOT NULL,       -- 'companion' or 'repeater'
    metric TEXT NOT NULL,     -- Firmware field name (e.g., 'bat', 'nb_recv')
    value REAL,               -- Metric value
    PRIMARY KEY (ts, role, metric)
) STRICT, WITHOUT ROWID;

CREATE INDEX idx_metrics_role_ts ON metrics(role, ts);
```

**Key features:**
- Firmware field names stored as-is (no translation)
- New firmware fields captured automatically
- Renamed/dropped fields handled gracefully
- ~3.75M rows/year is well within SQLite capacity

### Firmware Field Names

Collectors iterate firmware response dicts directly and insert all numeric values:

**Companion** (from `get_stats_core`, `get_stats_packets`, `get_contacts`):
- `battery_mv` - Battery in millivolts
- `uptime_secs` - Uptime in seconds
- `recv`, `sent` - Packet counters
- `contacts` - Number of contacts

**Repeater** (from `req_status_sync`):
- `bat` - Battery in millivolts
- `uptime` - Uptime in seconds
- `last_rssi`, `last_snr`, `noise_floor` - Signal metrics
- `nb_recv`, `nb_sent` - Packet counters
- `airtime`, `rx_airtime` - Airtime counters
- `tx_queue_len` - TX queue depth
- `flood_dups`, `direct_dups`, `sent_flood`, `recv_flood`, `sent_direct`, `recv_direct` - Detailed packet counters

See `docs/firmware-responses.md` for complete firmware response documentation.

### Derived Fields (Computed at Query Time)

Battery percentage (`bat_pct`) is computed at query time from voltage using the 18650 Li-ion discharge curve:

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

Uses piecewise linear interpolation between points. Implementation in `src/meshmon/battery.py`.

### Migration System

Database migrations are stored as SQL files in `src/meshmon/migrations/` with naming convention `NNN_description.sql`. Migrations are applied automatically on database initialization.

Current migrations:
1. `001_initial_schema.sql` - Creates db_meta table and initial wide tables
2. `002_eav_schema.sql` - Migrates to EAV schema, converts field names

## Running the Scripts

```bash
cd /path/to/meshcore-stats
source .venv/bin/activate
```

Configuration is automatically loaded from `meshcore.conf`.

### Data Collection

```bash
# Collect companion data (run every 60s)
python scripts/collect_companion.py

# Collect repeater data (run every 15min)
python scripts/collect_repeater.py
```

### Chart Rendering

```bash
# Render all SVG charts from database (day/week/month/year for all metrics)
python scripts/render_charts.py
```

Charts are rendered using matplotlib, reading directly from the SQLite database. Each chart is generated in both light and dark theme variants.

### HTML Generation

```bash
# Generate static site pages
python scripts/render_site.py
```

### Reports

Generates monthly and yearly statistics reports in HTML, TXT (WeeWX-style ASCII), and JSON formats:

```bash
# Generate all reports
python scripts/render_reports.py
```

Reports are generated for all available months/years based on database data. Output structure:
- `/reports/` - Index page listing all available reports
- `/reports/{role}/{year}/` - Yearly report (HTML, TXT, JSON)
- `/reports/{role}/{year}/{month}/` - Monthly report (HTML, TXT, JSON)

Counter metrics (rx, tx, airtime) are aggregated from absolute counter values in the database, with proper handling of device reboots (negative deltas).

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
- Amber/orange line color (#b45309 light, #f59e0b dark)
- Semi-transparent area fill with solid line on top
- Min/Avg/Max statistics displayed in chart footer
- Current value displayed in chart header

### Repeater Metrics Summary

Metrics use firmware field names directly from `req_status_sync`:

| Metric | Type | Display Unit | Description |
|--------|------|--------------|-------------|
| `bat` | gauge | Voltage (V) | Battery voltage (stored in mV, displayed as V) |
| `bat_pct` | gauge | Battery (%) | Battery percentage (computed at query time) |
| `last_rssi` | gauge | RSSI (dBm) | Signal strength of last packet |
| `last_snr` | gauge | SNR (dB) | Signal-to-noise ratio |
| `noise_floor` | gauge | dBm | Background RF noise |
| `uptime` | gauge | Days | Time since reboot (seconds ÷ 86400) |
| `tx_queue_len` | gauge | Queue depth | TX queue length |
| `nb_recv` | counter | Packets/min | Total packets received |
| `nb_sent` | counter | Packets/min | Total packets transmitted |
| `airtime` | counter | Seconds/min | TX airtime rate |
| `rx_airtime` | counter | Seconds/min | RX airtime rate |
| `flood_dups` | counter | Packets/min | Flood duplicate packets |
| `direct_dups` | counter | Packets/min | Direct duplicate packets |
| `sent_flood` | counter | Packets/min | Flood packets transmitted |
| `recv_flood` | counter | Packets/min | Flood packets received |
| `sent_direct` | counter | Packets/min | Direct packets transmitted |
| `recv_direct` | counter | Packets/min | Direct packets received |

### Companion Metrics Summary

Metrics use firmware field names directly from `get_stats_*`:

| Metric | Type | Display Unit | Description |
|--------|------|--------------|-------------|
| `battery_mv` | gauge | Voltage (V) | Battery voltage (stored in mV, displayed as V) |
| `bat_pct` | gauge | Battery (%) | Battery percentage (computed at query time) |
| `contacts` | gauge | Count | Known mesh nodes |
| `uptime_secs` | gauge | Days | Time since reboot (seconds ÷ 86400) |
| `recv` | counter | Packets/min | Total packets received |
| `sent` | counter | Packets/min | Total packets transmitted |

## Circuit Breaker

The repeater collector uses a circuit breaker to avoid spamming LoRa when the repeater is unreachable:

- State stored in `data/state/repeater_circuit.json`
- After N consecutive failures, enters cooldown
- During cooldown, skips collection instead of attempting request
- Resets on successful response

## Debugging

Enable debug logging:
```bash
MESH_DEBUG=1 python scripts/collect_companion.py
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

2. **Configuration not loaded**: Ensure `meshcore.conf` exists in the project root, or set environment variables directly.

3. **Empty charts**: Need at least 2 data points to display meaningful data.

## Cron Setup (Example)

```cron
MESHCORE=/path/to/meshcore-stats

# Companion: every minute
* * * * * cd $MESHCORE && .venv/bin/python scripts/collect_companion.py

# Repeater: every 15 minutes (offset by 1 min for staggering)
1,16,31,46 * * * * cd $MESHCORE && .venv/bin/python scripts/collect_repeater.py

# Charts: every 5 minutes (generates SVG charts from database)
*/5 * * * * cd $MESHCORE && .venv/bin/python scripts/render_charts.py

# HTML: every 5 minutes
*/5 * * * * cd $MESHCORE && .venv/bin/python scripts/render_site.py

# Reports: daily at midnight (historical stats don't change often)
0 0 * * * cd $MESHCORE && .venv/bin/python scripts/render_reports.py
```

**Notes:**
- `cd $MESHCORE` is required because paths in the config are relative to the project root
- Serial port locking is handled automatically via `fcntl.flock()` in Python (no external `flock` needed)

## Adding New Metrics

With the EAV schema, adding new metrics is simple:

1. **Automatic capture**: New numeric fields from firmware responses are automatically stored in the database. No schema changes needed.

2. **To display in charts**: Add the firmware field name to:
   - `METRIC_CONFIG` in `src/meshmon/metrics.py` (label, unit, type, transform)
   - `COMPANION_CHART_METRICS` or `REPEATER_CHART_METRICS` in `src/meshmon/metrics.py`
   - `COMPANION_CHART_GROUPS` or `REPEATER_CHART_GROUPS` in `src/meshmon/html.py`

3. **To display in reports**: Add the firmware field name to:
   - `COMPANION_REPORT_METRICS` or `REPEATER_REPORT_METRICS` in `src/meshmon/reports.py`
   - Update the report table builders in `src/meshmon/html.py` if needed

4. Regenerate charts and site.

## Changing Metric Types

Metric configuration is centralized in `src/meshmon/metrics.py` using `MetricConfig`:

```python
MetricConfig(
    label="Packets RX",    # Human-readable label
    unit="/min",           # Display unit
    type="counter",        # "gauge" or "counter"
    scale=60,              # Multiply by this for display (60 = per minute)
    transform="mv_to_v",   # Optional: apply voltage conversion
)
```

To change a metric from gauge to counter (or vice versa):

1. Update `METRIC_CONFIG` in `src/meshmon/metrics.py` - change the `type` field
2. Update `scale` if needed (counters often use scale=60 for per-minute display)
3. Regenerate charts: `python scripts/render_charts.py`

## Database Maintenance

The SQLite database benefits from periodic maintenance to reclaim space and update query statistics. A maintenance script is provided:

```bash
# Run database maintenance (VACUUM + ANALYZE)
./scripts/db_maintenance.sh
```

SQLite's VACUUM command acquires an exclusive lock internally. Other processes with `busy_timeout` configured will wait for maintenance to complete.

### Recommended Cron Entry

Add to your crontab for monthly maintenance at 3 AM on the 1st:

```cron
# Database maintenance: monthly at 3 AM on the 1st
0 3 1 * * cd /path/to/meshcore-stats && ./scripts/db_maintenance.sh >> /var/log/meshcore-stats-maintenance.log 2>&1
```
