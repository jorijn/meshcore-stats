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


def get_path(key: str, default: str) -> Path:
    """Get path env var, expanding user and making absolute."""
    val = os.environ.get(key, default)
    return Path(val).expanduser().resolve()


def parse_metrics(env_var: str) -> dict[str, str]:
    """
    Parse metric mapping from env var.
    Format: "ds_name=dotted.path,ds_name2=other.path"
    Returns: {"ds_name": "dotted.path", ...}
    """
    val = os.environ.get(env_var, "")
    if not val.strip():
        return {}
    result = {}
    for part in val.split(","):
        part = part.strip()
        if "=" in part:
            ds_name, path = part.split("=", 1)
            result[ds_name.strip()] = path.strip()
    return result


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
        self.snapshot_dir = get_path("SNAPSHOT_DIR", "./data/snapshots")
        self.rrd_dir = get_path("RRD_DIR", "./data/rrd")
        self.state_dir = get_path("STATE_DIR", "./data/state")
        self.out_dir = get_path("OUT_DIR", "./out")

        # Metric mappings
        self.companion_metrics = parse_metrics("COMPANION_METRICS")
        self.repeater_metrics = parse_metrics("REPEATER_METRICS")

        # Defaults if not specified
        # Based on actual payload structure from device
        if not self.companion_metrics:
            self.companion_metrics = {
                "bat_mv": "stats.core.battery_mv",  # Battery in millivolts
                "contacts": "derived.contacts_count",
                "rx": "derived.rx_packets",  # From stats.packets.recv
                "tx": "derived.tx_packets",  # From stats.packets.sent
            }
        if not self.repeater_metrics:
            self.repeater_metrics = {
                "bat_v": "telemetry.bat",
                "bat_pct": "telemetry.bat_pct",
                "neigh": "derived.neighbours_count",
                "rx": "telemetry.rx_packets",
                "tx": "telemetry.tx_packets",
                "rssi": "status.rssi",
                "snr": "status.snr",
            }


# Global config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = Config()
    return _config
