"""SQLite database for metrics storage.

This module replaces JSON snapshot storage with a SQLite database
for faster chart rendering and report generation.

Schema design:
- Two tables: companion_metrics, repeater_metrics
- timestamp as primary key (WITHOUT ROWID for compact storage)
- STRICT mode for type safety
- Pre-computed bat_pct at insert time
- Raw counter values stored (rates computed in queries)

Migration system:
- Schema version tracked in db_meta table
- Migrations stored as SQL files in src/meshmon/migrations/
- Files named: NNN_description.sql (e.g., 001_initial_schema.sql)
- Applied in order on database init
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Optional

from .battery import voltage_to_percentage
from .env import get_config
from . import log


# Path to migrations directory (relative to this file)
MIGRATIONS_DIR = Path(__file__).parent / "migrations"


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


def insert_companion_metrics(
    ts: int,
    bat_v: Optional[float] = None,
    contacts: Optional[int] = None,
    uptime: Optional[int] = None,
    rx: Optional[int] = None,
    tx: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """Insert companion metrics row.

    Pre-computes bat_pct from bat_v at insert time.

    Args:
        ts: Unix timestamp
        bat_v: Battery voltage in volts
        contacts: Contact count
        uptime: Uptime in seconds
        rx: Total packets received (counter)
        tx: Total packets sent (counter)
        db_path: Optional path override

    Returns:
        True if inserted, False if duplicate timestamp
    """
    # Pre-compute bat_pct
    bat_pct = voltage_to_percentage(bat_v) if bat_v is not None else None

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO companion_metrics
                (ts, bat_v, bat_pct, contacts, uptime, rx, tx)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, bat_v, bat_pct, contacts, uptime, rx, tx)
            )
        return True
    except sqlite3.IntegrityError:
        log.debug(f"Duplicate companion timestamp: {ts}")
        return False


def insert_repeater_metrics(
    ts: int,
    bat_v: Optional[float] = None,
    rssi: Optional[int] = None,
    snr: Optional[float] = None,
    uptime: Optional[int] = None,
    noise: Optional[int] = None,
    txq: Optional[int] = None,
    rx: Optional[int] = None,
    tx: Optional[int] = None,
    airtime: Optional[int] = None,
    rx_air: Optional[int] = None,
    fl_dups: Optional[int] = None,
    di_dups: Optional[int] = None,
    fl_tx: Optional[int] = None,
    fl_rx: Optional[int] = None,
    di_tx: Optional[int] = None,
    di_rx: Optional[int] = None,
    db_path: Optional[Path] = None,
) -> bool:
    """Insert repeater metrics row.

    Pre-computes bat_pct from bat_v at insert time.

    Args:
        ts: Unix timestamp
        bat_v: Battery voltage in volts
        rssi: Signal strength (dBm)
        snr: Signal-to-noise ratio (dB)
        uptime: Uptime in seconds
        noise: Noise floor (dBm)
        txq: TX queue depth
        rx: Total packets received (counter)
        tx: Total packets sent (counter)
        airtime: TX airtime seconds (counter)
        rx_air: RX airtime seconds (counter)
        fl_dups: Flood duplicates (counter)
        di_dups: Direct duplicates (counter)
        fl_tx: Flood TX packets (counter)
        fl_rx: Flood RX packets (counter)
        di_tx: Direct TX packets (counter)
        di_rx: Direct RX packets (counter)
        db_path: Optional path override

    Returns:
        True if inserted, False if duplicate timestamp
    """
    # Pre-compute bat_pct
    bat_pct = voltage_to_percentage(bat_v) if bat_v is not None else None

    try:
        with get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO repeater_metrics
                (ts, bat_v, bat_pct, rssi, snr, uptime, noise, txq,
                 rx, tx, airtime, rx_air, fl_dups, di_dups,
                 fl_tx, fl_rx, di_tx, di_rx)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (ts, bat_v, bat_pct, rssi, snr, uptime, noise, txq,
                 rx, tx, airtime, rx_air, fl_dups, di_dups,
                 fl_tx, fl_rx, di_tx, di_rx)
            )
        return True
    except sqlite3.IntegrityError:
        log.debug(f"Duplicate repeater timestamp: {ts}")
        return False


def get_metrics_for_period(
    role: str,
    start_ts: int,
    end_ts: int,
    db_path: Optional[Path] = None,
) -> list[dict[str, Any]]:
    """Fetch all metrics for a role within a time range.

    Args:
        role: "companion" or "repeater"
        start_ts: Start timestamp (inclusive)
        end_ts: End timestamp (inclusive)
        db_path: Optional path override

    Returns:
        List of metric rows as dicts
    """
    table = f"{role}_metrics"

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(
            f"""
            SELECT * FROM {table}
            WHERE ts BETWEEN ? AND ?
            ORDER BY ts ASC
            """,
            (start_ts, end_ts)
        )
        return [dict(row) for row in cursor.fetchall()]


def get_latest_metrics(
    role: str,
    db_path: Optional[Path] = None,
) -> Optional[dict[str, Any]]:
    """Get the most recent metrics row for a role.

    Args:
        role: "companion" or "repeater"
        db_path: Optional path override

    Returns:
        Most recent row as dict, or None if no data
    """
    table = f"{role}_metrics"

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(
            f"SELECT * FROM {table} ORDER BY ts DESC LIMIT 1"
        )
        row = cursor.fetchone()
        return dict(row) if row else None


def get_metric_count(
    role: str,
    db_path: Optional[Path] = None,
) -> int:
    """Get total row count for a role.

    Args:
        role: "companion" or "repeater"
        db_path: Optional path override

    Returns:
        Number of rows
    """
    table = f"{role}_metrics"

    with get_connection(db_path, readonly=True) as conn:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        return cursor.fetchone()[0]


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
