"""Simple logging helper."""

import sys
from datetime import datetime

from .env import get_config


def _ts() -> str:
    """Get current timestamp string."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def info(msg: str) -> None:
    """Print info message to stdout."""
    print(f"[{_ts()}] {msg}")


def debug(msg: str) -> None:
    """Print debug message if MESH_DEBUG is enabled."""
    if get_config().mesh_debug:
        print(f"[{_ts()}] DEBUG: {msg}")


def error(msg: str) -> None:
    """Print error message to stderr."""
    print(f"[{_ts()}] ERROR: {msg}", file=sys.stderr)


def warn(msg: str) -> None:
    """Print warning message to stderr."""
    print(f"[{_ts()}] WARN: {msg}", file=sys.stderr)
