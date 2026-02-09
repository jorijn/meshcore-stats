"""Environment variable parsing and configuration."""

import os
import re
import warnings
from pathlib import Path


def _parse_config_value(value: str) -> str:
    """Parse a shell-style value, handling quotes and inline comments."""
    value = value.strip()

    if not value:
        return ""

    # Handle double-quoted strings
    if value.startswith('"'):
        end = value.find('"', 1)
        if end != -1:
            return value[1:end]
        return value[1:]  # No closing quote

    # Handle single-quoted strings
    if value.startswith("'"):
        end = value.find("'", 1)
        if end != -1:
            return value[1:end]
        return value[1:]

    # Unquoted value - strip inline comments (# preceded by whitespace)
    comment_match = re.search(r"\s+#", value)
    if comment_match:
        value = value[: comment_match.start()]

    return value.strip()


def _load_config_file() -> None:
    """Load meshcore.conf if it exists. Env vars take precedence.

    The config file is expected in the project root (three levels up from this module).
    Scripts should be run from the project directory via cron: cd $MESHCORE && .venv/bin/python ...
    """
    config_path = Path(__file__).resolve().parent.parent.parent / "meshcore.conf"

    if not config_path.exists():
        return

    try:
        with open(config_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()

                # Skip comments and empty lines
                if not line or line.startswith("#"):
                    continue

                # Remove 'export ' prefix
                if line.startswith("export "):
                    line = line[7:].lstrip()

                # Must have KEY=value format
                if "=" not in line:
                    continue

                key, _, value = line.partition("=")
                key = key.strip()

                # Validate key is a valid shell identifier
                if not key or not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                    continue

                # Parse value (handles quotes, inline comments)
                value = _parse_config_value(value)

                # Only set if not already in environment
                if key not in os.environ:
                    os.environ[key] = value

    except (OSError, UnicodeDecodeError) as e:
        warnings.warn(f"Failed to load {config_path}: {e}", stacklevel=2)


# Load config file at module import time, before Config is instantiated
_load_config_file()


def get_str(key: str, default: str | None = None) -> str | None:
    """Get string env var."""
    return os.environ.get(key, default)


def get_int(key: str, default: int) -> int:
    """Get integer env var."""
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        return default


def get_bool(key: str, default: bool = False) -> bool:
    """Get boolean env var (0/1, true/false, yes/no)."""
    val = os.environ.get(key, "").lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "on")


def get_float(key: str, default: float) -> float:
    """Get float env var."""
    val = os.environ.get(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        return default


def get_path(key: str, default: str) -> Path:
    """Get path env var, expanding user and making absolute."""
    val = os.environ.get(key, default)
    return Path(val).expanduser().resolve()


def get_unit_system(key: str, default: str = "metric") -> str:
    """Get display unit system env var, normalized to metric/imperial."""
    val = os.environ.get(key, default).strip().lower()
    if val in ("metric", "imperial"):
        return val
    return default


class Config:
    """Configuration loaded from environment variables."""

    # Connection settings
    mesh_transport: str
    mesh_serial_port: str | None
    mesh_serial_baud: int
    mesh_tcp_host: str | None
    mesh_tcp_port: int
    mesh_ble_addr: str | None
    mesh_ble_pin: str | None
    mesh_debug: bool

    # Remote repeater identity
    repeater_name: str | None
    repeater_key_prefix: str | None
    repeater_password: str | None

    # Intervals and timeouts
    companion_step: int
    repeater_step: int
    remote_timeout_s: int
    remote_retry_attempts: int
    remote_retry_backoff_s: int
    remote_cb_fails: int
    remote_cb_cooldown_s: int

    # Telemetry
    telemetry_enabled: bool
    telemetry_timeout_s: int
    telemetry_retry_attempts: int
    telemetry_retry_backoff_s: int

    # Paths
    state_dir: Path
    out_dir: Path
    html_path: str

    # Report location metadata
    report_location_name: str | None
    report_location_short: str | None
    report_lat: float
    report_lon: float
    report_elev: float
    report_elev_unit: str | None

    # Node display names
    repeater_display_name: str | None
    companion_display_name: str | None
    repeater_pubkey_prefix: str | None
    companion_pubkey_prefix: str | None
    repeater_hardware: str | None
    companion_hardware: str | None

    # Radio configuration
    radio_frequency: str | None
    radio_bandwidth: str | None
    radio_spread_factor: str | None
    radio_coding_rate: str | None

    # Display formatting
    display_unit_system: str

    def __init__(self) -> None:
        # Connection settings
        self.mesh_transport = get_str("MESH_TRANSPORT", "serial") or "serial"
        self.mesh_serial_port = get_str("MESH_SERIAL_PORT")  # None = auto-detect
        self.mesh_serial_baud = get_int("MESH_SERIAL_BAUD", 115200)
        self.mesh_tcp_host = get_str("MESH_TCP_HOST", "localhost")
        self.mesh_tcp_port = get_int("MESH_TCP_PORT", 5000)
        self.mesh_ble_addr = get_str("MESH_BLE_ADDR")
        self.mesh_ble_pin = get_str("MESH_BLE_PIN")
        self.mesh_debug = get_bool("MESH_DEBUG", False)

        # Remote repeater identity
        self.repeater_name = get_str("REPEATER_NAME")
        self.repeater_key_prefix = get_str("REPEATER_KEY_PREFIX")
        self.repeater_password = get_str("REPEATER_PASSWORD")

        # Intervals and timeouts
        self.companion_step = get_int("COMPANION_STEP", 60)
        self.repeater_step = get_int("REPEATER_STEP", 900)
        self.remote_timeout_s = get_int("REMOTE_TIMEOUT_S", 10)
        self.remote_retry_attempts = get_int("REMOTE_RETRY_ATTEMPTS", 2)
        self.remote_retry_backoff_s = get_int("REMOTE_RETRY_BACKOFF_S", 4)
        self.remote_cb_fails = get_int("REMOTE_CB_FAILS", 6)
        self.remote_cb_cooldown_s = get_int("REMOTE_CB_COOLDOWN_S", 3600)

        # Telemetry collection (requires sensor board on repeater)
        self.telemetry_enabled = get_bool("TELEMETRY_ENABLED", False)
        # Separate settings allow tuning if telemetry proves problematic
        # Defaults match status settings - tune down if needed
        self.telemetry_timeout_s = get_int("TELEMETRY_TIMEOUT_S", 10)
        self.telemetry_retry_attempts = get_int("TELEMETRY_RETRY_ATTEMPTS", 2)
        self.telemetry_retry_backoff_s = get_int("TELEMETRY_RETRY_BACKOFF_S", 4)

        # Paths (defaults are Docker container paths; native installs override via config)
        self.state_dir = get_path("STATE_DIR", "/data/state")
        self.out_dir = get_path("OUT_DIR", "/out")

        # Report location metadata
        self.report_location_name = get_str(
            "REPORT_LOCATION_NAME", "Your Location"
        )
        self.report_location_short = get_str(
            "REPORT_LOCATION_SHORT", "Your Location"
        )
        self.report_lat = get_float("REPORT_LAT", 0.0)
        self.report_lon = get_float("REPORT_LON", 0.0)
        self.report_elev = get_float("REPORT_ELEV", 0.0)
        self.report_elev_unit = get_str("REPORT_ELEV_UNIT", "m")  # "m" or "ft"

        # Node display names for UI
        self.repeater_display_name = get_str(
            "REPEATER_DISPLAY_NAME", "Repeater Node"
        )
        self.companion_display_name = get_str(
            "COMPANION_DISPLAY_NAME", "Companion Node"
        )

        # Public key prefixes for display (e.g., "!a1b2c3d4")
        self.repeater_pubkey_prefix = get_str("REPEATER_PUBKEY_PREFIX")
        self.companion_pubkey_prefix = get_str("COMPANION_PUBKEY_PREFIX")

        # Hardware info for sidebar
        self.repeater_hardware = get_str("REPEATER_HARDWARE", "LoRa Repeater")
        self.companion_hardware = get_str("COMPANION_HARDWARE", "LoRa Node")

        # Radio configuration (for display in sidebar)
        self.radio_frequency = get_str("RADIO_FREQUENCY", "869.618 MHz")
        self.radio_bandwidth = get_str("RADIO_BANDWIDTH", "62.5 kHz")
        self.radio_spread_factor = get_str("RADIO_SPREAD_FACTOR", "SF8")
        self.radio_coding_rate = get_str("RADIO_CODING_RATE", "CR8")

        # Display formatting
        self.display_unit_system = get_unit_system("DISPLAY_UNIT_SYSTEM", "metric")

        self.html_path = get_str("HTML_PATH", "") or ""

# Global config instance
_config: Config | None = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
