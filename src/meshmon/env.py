"""Environment variable parsing and configuration."""

import os
from pathlib import Path
from typing import Optional


def get_str(key: str, default: Optional[str] = None) -> Optional[str]:
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


class Config:
    """Configuration loaded from environment variables."""

    def __init__(self):
        # Connection settings
        self.mesh_transport = get_str("MESH_TRANSPORT", "serial")
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
        self.repeater_fetch_acl = get_bool("REPEATER_FETCH_ACL", False)

        # Intervals and timeouts
        self.companion_step = get_int("COMPANION_STEP", 60)
        self.repeater_step = get_int("REPEATER_STEP", 900)
        self.remote_timeout_s = get_int("REMOTE_TIMEOUT_S", 10)
        self.remote_retry_attempts = get_int("REMOTE_RETRY_ATTEMPTS", 2)
        self.remote_retry_backoff_s = get_int("REMOTE_RETRY_BACKOFF_S", 4)
        self.remote_cb_fails = get_int("REMOTE_CB_FAILS", 6)
        self.remote_cb_cooldown_s = get_int("REMOTE_CB_COOLDOWN_S", 3600)

        # Paths
        self.state_dir = get_path("STATE_DIR", "./data/state")
        self.out_dir = get_path("OUT_DIR", "./out")

        # Report location metadata
        self.report_location_name = get_str(
            "REPORT_LOCATION_NAME", "Oosterhout, The Netherlands"
        )
        self.report_lat = get_float("REPORT_LAT", 51.6674308)
        self.report_lon = get_float("REPORT_LON", 4.8596901)
        self.report_elev = get_float("REPORT_ELEV", 10.0)

        # Node display names for reports
        self.repeater_display_name = get_str(
            "REPEATER_DISPLAY_NAME", "jorijn.com Repeater N"
        )
        self.companion_display_name = get_str(
            "COMPANION_DISPLAY_NAME", "Companion Node"
        )


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
