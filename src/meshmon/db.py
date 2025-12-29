"""SQLite database for metrics storage.

This module provides EAV (Entity-Attribute-Value) storage for metrics
from MeshCore devices. Firmware field names are stored directly for
future-proofing - new fields are captured automatically without schema changes.

Schema design:
- Single 'metrics' table with (ts, role, metric, value) structure
- Firmware field names stored as-is (e.g., 'bat', 'nb_recv', 'battery_mv')
- bat_pct computed at query time from voltage values
- Raw counter values stored (rates computed during chart rendering)

Migration system:
- Schema version tracked in db_meta table
- Migrations stored as SQL files in src/meshmon/migrations/
- Files named: NNN_description.sql (e.g., 001_initial_schema.sql)
- Applied in order on database init
"""

import sqlite3
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from .battery import voltage_to_percentage
from .env import get_config
from . import log


# Path to migrations directory (relative to this file)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

# Valid role values (used to prevent SQL injection)
VALID_ROLES = ("companion", "repeater")

# Battery voltage field names by role (for bat_pct derivation)
BATTERY_FIELD = {
    "companion": "battery_mv",
    "repeater": "bat",
}


def _validate_role(role: str) -> str:
    """Validate role parameter to prevent SQL injection.

    Args:
        role: Role name to validate

    Returns:
        The validated role string

    Raises:
        ValueError: If role is not valid
    """
    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role!r}. Must be one of {VALID_ROLES}")
    return role


# =============================================================================
# File-based Migration System
# =============================================================================


def _get_migration_files() -> list[tuple[int, Path]]:
    """Get all migration files sorted by version number.

    Returns:
        List of (version, path) tuples sorted by version
    """
    if not MIGRATIONS_DIR.exists():
        return []

    migrations = []
    for sql_file in MIGRATIONS_DIR.glob("*.sql"):
        # Extract version number from filename (e.g., "001_initial.sql" -> 1)
        try:
            version_str = sql_file.stem.split("_")[0]
            version = int(version_str)
            migrations.append((version, sql_file))
        except (ValueError, IndexError):
            log.warn(f"Skipping invalid migration filename: {sql_file.name}")
            continue

    return sorted(migrations, key=lambda x: x[0])


def _get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from database.

    Returns 0 if db_meta table doesn't exist (fresh database).
    """
    try:
        cursor = conn.execute(
            "SELECT value FROM db_meta WHERE key = 'schema_version'"
        )
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        # db_meta table doesn't exist
        return 0


def _set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Set schema version in database."""
    conn.execute(
        """
        INSERT OR REPLACE INTO db_meta (key, value)
        VALUES ('schema_version', ?)
        """,
        (str(version),)
    )


def _apply_migrations(conn: sqlite3.Connection) -> None:
    """Apply pending migrations from SQL files."""
    current_version = _get_schema_version(conn)
    migrations = _get_migration_files()

    if not migrations:
        raise RuntimeError(
            f"No migration files found in {MIGRATIONS_DIR}. "
            "Expected at least 001_initial_schema.sql"
        )

    latest_version = migrations[-1][0]

    # Apply each migration that hasn't been applied yet
    for version, sql_file in migrations:
        if version <= current_version:
            continue

        log.info(f"Applying migration {sql_file.name}")
        try:
            sql_content = sql_file.read_text()
            conn.executescript(sql_content)
            _set_schema_version(conn, version)
            conn.commit()
            log.debug(f"Migration {version} applied successfully")
        except Exception as e:
            conn.rollback()
            raise RuntimeError(
                f"Migration {sql_file.name} failed: {e}"
            ) from e

    final_version = _get_schema_version(conn)
    if final_version < latest_version:
        log.warn(
            f"Schema version {final_version} is behind latest migration {latest_version}"
        )


def get_schema_version() -> int:
    """Get current schema version from database.

    Returns:
        Current schema version, or 0 if database doesn't exist
    """
    db_path = get_db_path()
    if not db_path.exists():
        return 0

    with get_connection(readonly=True) as conn:
        return _get_schema_version(conn)


# =============================================================================
# Database Connection & Initialization
# =============================================================================


def get_db_path() -> Path:
    """Get database file path."""
    cfg = get_config()
    return cfg.state_dir / "metrics.db"


def init_db(db_path: Optional[Path] = None) -> None:
    """Initialize database with schema and apply pending migrations.

    Creates tables if they don't exist. Safe to call multiple times.
    Applies any pending migrations to bring schema up to date.

    Args:
        db_path: Optional path override (for testing)
    """
    if db_path is None:
        db_path = get_db_path()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    try:
        # Enable optimizations
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
        conn.execute("PRAGMA temp_store=MEMORY")

        # Apply schema creation and migrations
        _apply_migrations(conn)

        conn.commit()

        version = _get_schema_version(conn)
        log.debug(f"Database initialized at {db_path} (schema v{version})")

    finally:
        conn.close()


@contextmanager
def get_connection(
    db_path: Optional[Path] = None,
    readonly: bool = False
) -> Iterator[sqlite3.Connection]:
    """Context manager for database connections.

    Args:
        db_path: Optional path override
        readonly: If True, open in read-only mode

    Yields:
        sqlite3.Connection with Row factory enabled
    """
    if db_path is None:
        db_path = get_db_path()

    if readonly:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(db_path)

    conn.row_factory = sqlite3.Row
    # Wait up to 5 seconds if database is locked
    conn.execute("PRAGMA busy_timeout=5000")

    try:
        yield conn
        if not readonly:
            conn.commit()
    except Exception:
        if not readonly:
            conn.rollback()
        raise
    finally:
        conn.close()


# =============================================================================
# Metric Insert Functions (EAV)
# =============================================================================


def insert_metric(
    ts: int,
    role: str,
    metric: str,
    value: float,
    db_path: Optional[Path] = None,
) -> bool:
    """Insert a single metric value.

    Args:
        ts: Unix timestamp
        role: 'companion' or 'repeater'
        metric: Firmware field name (e.g., 'bat', 'nb_recv')
        value: Metric value
        db_path: Optional path override

    Returns:
        True if inserted, False if duplicate (ts, role, metric)
    """
    role = _validate_role(role)

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                "INSERT INTO metrics (ts, role, metric, value) VALUES (?, ?, ?, ?)",
                (ts, role, metric, value)
            )
        return True
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed" in str(e) or "PRIMARY KEY" in str(e):
            log.debug(f"Duplicate metric: ts={ts}, role={role}, metric={metric}")
            return False
        raise


def insert_metrics(
    ts: int,
    role: str,
    metrics: dict[str, Any],
    db_path: Optional[Path] = None,
) -> int:
    """Insert multiple metrics from a dict (e.g., firmware status response).

    Only numeric values (int, float) are inserted. Non-numeric values are skipped.

    Args:
        ts: Unix timestamp
        role: 'companion' or 'repeater'
        metrics: Dict of metric_name -> value (from firmware response)
        db_path: Optional path override

    Returns:
        Number of metrics inserted
    """
    role = _validate_role(role)
    inserted = 0

    try:
        with get_connection(db_path) as conn:
            for metric, value in metrics.items():
                # Only insert numeric values
                if not isinstance(value, (int, float)):
                    continue
                # Skip None values
                if value is None:
                    continue

                try:
                    conn.execute(
                        "INSERT INTO metrics (ts, role, metric, value) VALUES (?, ?, ?, ?)",
                        (ts, role, metric, float(value))
                    )
                    inserted += 1
                except sqlite3.IntegrityError:
                    # Duplicate, skip
                    pass

        log.debug(f"Inserted {inserted} metrics for {role} at ts={ts}")
        return inserted

    except Exception as e:
        log.error(f"Failed to insert metrics: {e}")
        raise


# =============================================================================
# Metric Query Functions (EAV)
# =============================================================================


def get_metrics_for_period(
    role: str,
    start_ts: int,
    end_ts: int,
    db_path: Optional[Path] = None,
) -> dict[str, list[tuple[int, float]]]:
    """Fetch all metrics for a role within a time range.

    Returns data pivoted by metric name for easy chart rendering.
    Also computes bat_pct from battery voltage if available.

    Args:
        role: "companion" or "repeater"
        start_ts: Start timestamp (inclusive)
        end_ts: End timestamp (inclusive)
        db_path: Optional path override

    Returns:
        Dict mapping metric names to list of (timestamp, value) tuples,
        sorted by timestamp ascending.

    Raises:
        ValueError: If role is not valid
    """
    role = _validate_role(role)

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(
            """
            SELECT ts, metric, value
            FROM metrics
            WHERE role = ? AND ts BETWEEN ? AND ?
            ORDER BY ts ASC
            """,
            (role, start_ts, end_ts)
        )

        result: dict[str, list[tuple[int, float]]] = defaultdict(list)
        for row in cursor:
            if row["value"] is not None:
                result[row["metric"]].append((row["ts"], row["value"]))

        # Compute bat_pct from battery voltage
        bat_field = BATTERY_FIELD.get(role)
        if bat_field and bat_field in result:
            bat_pct_data = []
            for ts, mv in result[bat_field]:
                voltage = mv / 1000.0  # Convert millivolts to volts
                pct = voltage_to_percentage(voltage)
                if pct is not None:
                    bat_pct_data.append((ts, pct))
            if bat_pct_data:
                result["bat_pct"] = bat_pct_data

        return dict(result)


def get_latest_metrics(
    role: str,
    db_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Get the most recent metrics for a role.

    Returns all metrics at the most recent timestamp as a flat dict.
    Also computes bat_pct from battery voltage.

    Args:
        role: "companion" or "repeater"
        db_path: Optional path override

    Returns:
        Dict with 'ts' and all metric values, or None if no data

    Raises:
        ValueError: If role is not valid
    """
    role = _validate_role(role)

    with get_connection(db_path, readonly=True) as conn:
        # Find the most recent timestamp for this role
        cursor = conn.execute(
            "SELECT MAX(ts) as max_ts FROM metrics WHERE role = ?",
            (role,)
        )
        row = cursor.fetchone()
        if not row or row["max_ts"] is None:
            return None

        max_ts = row["max_ts"]

        # Get all metrics at that timestamp
        cursor = conn.execute(
            "SELECT metric, value FROM metrics WHERE role = ? AND ts = ?",
            (role, max_ts)
        )

        result: dict[str, Any] = {"ts": max_ts}
        for row in cursor:
            result[row["metric"]] = row["value"]

        # Compute bat_pct from battery voltage
        bat_field = BATTERY_FIELD.get(role)
        if bat_field and bat_field in result:
            voltage = result[bat_field] / 1000.0
            result["bat_pct"] = voltage_to_percentage(voltage)

        return result


def get_metric_count(
    role: str,
    db_path: Optional[Path] = None,
) -> int:
    """Get total number of metric rows for a role.

    Args:
        role: "companion" or "repeater"
        db_path: Optional path override

    Returns:
        Number of rows

    Raises:
        ValueError: If role is not valid
    """
    role = _validate_role(role)

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM metrics WHERE role = ?",
            (role,)
        )
        return cursor.fetchone()[0]


def get_distinct_timestamps(
    role: str,
    db_path: Optional[Path] = None,
) -> int:
    """Get count of distinct timestamps for a role.

    Useful for understanding actual sample count (vs metric row count).

    Args:
        role: "companion" or "repeater"
        db_path: Optional path override

    Returns:
        Number of distinct timestamps
    """
    role = _validate_role(role)

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(
            "SELECT COUNT(DISTINCT ts) FROM metrics WHERE role = ?",
            (role,)
        )
        return cursor.fetchone()[0]


def get_available_metrics(
    role: str,
    db_path: Optional[Path] = None,
) -> list[str]:
    """Get list of all metric names stored for a role.

    Useful for discovering what metrics are available from firmware.

    Args:
        role: "companion" or "repeater"
        db_path: Optional path override

    Returns:
        List of metric names
    """
    role = _validate_role(role)

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(
            "SELECT DISTINCT metric FROM metrics WHERE role = ? ORDER BY metric",
            (role,)
        )
        return [row["metric"] for row in cursor]


def vacuum_db(db_path: Optional[Path] = None) -> None:
    """Compact database and rebuild indexes.

    Should be run periodically (e.g., weekly via cron).
    """
    if db_path is None:
        db_path = get_db_path()

    conn = sqlite3.connect(db_path)
    try:
        conn.execute("VACUUM")
        conn.execute("ANALYZE")
        log.info("Database vacuumed and analyzed")
    finally:
        conn.close()
