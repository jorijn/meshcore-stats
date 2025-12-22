"""JSON snapshot writing utilities."""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from .env import get_config
from . import log


def write_snapshot(role: str, ts: int, obj: dict[str, Any]) -> Path:
    """
    Write a snapshot JSON file.

    Args:
        role: "companion" or "repeater"
        ts: Unix timestamp (epoch seconds)
        obj: Snapshot data

    Returns:
        Path to written file
    """
    cfg = get_config()
    dt = datetime.fromtimestamp(ts)

    # Create path: snapshots/<role>/YYYY/MM/DD/HHMMSS.json
    snapshot_path = (
        cfg.snapshot_dir
        / role
        / dt.strftime("%Y")
        / dt.strftime("%m")
        / dt.strftime("%d")
        / f"{dt.strftime('%H%M%S')}.json"
    )

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(obj, indent=2, default=str))
    log.debug(f"Wrote snapshot to {snapshot_path}")
    return snapshot_path


def get_latest_snapshot(role: str) -> Optional[tuple[Path, dict[str, Any]]]:
    """
    Find and load the most recent snapshot for a role.

    Args:
        role: "companion" or "repeater"

    Returns:
        (path, data) or None if no snapshots exist
    """
    cfg = get_config()
    base = cfg.snapshot_dir / role

    if not base.exists():
        return None

    # Find all JSON files and get the most recent
    json_files = sorted(base.rglob("*.json"), reverse=True)
    if not json_files:
        return None

    latest = json_files[0]
    try:
        data = json.loads(latest.read_text())
        return (latest, data)
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Failed to load snapshot {latest}: {e}")
        return None


def load_snapshot(path: Path) -> Optional[dict[str, Any]]:
    """Load a snapshot from a specific path."""
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError) as e:
        log.error(f"Failed to load snapshot {path}: {e}")
        return None
