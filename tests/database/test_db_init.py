"""Tests for database initialization and migrations."""

import sqlite3

import pytest

from meshmon.db import (
    _get_schema_version,
    get_connection,
    init_db,
)


class TestInitDb:
    """Tests for init_db function."""

    def test_creates_database_file(self, db_path, configured_env):
        """Creates database file if it doesn't exist."""
        assert not db_path.exists()

        init_db(db_path)

        assert db_path.exists()

    def test_creates_parent_directories(self, tmp_path, configured_env):
        """Creates parent directories if needed."""
        nested_path = tmp_path / "deep" / "nested" / "metrics.db"
        assert not nested_path.parent.exists()

        init_db(nested_path)

        assert nested_path.exists()

    def test_applies_migrations(self, db_path, configured_env):
        """Applies schema migrations."""
        init_db(db_path)

        with get_connection(db_path, readonly=True) as conn:
            version = _get_schema_version(conn)
            assert version >= 1

    def test_safe_to_call_multiple_times(self, db_path, configured_env):
        """Can be called multiple times without error."""
        init_db(db_path)
        init_db(db_path)  # Should not raise
        init_db(db_path)  # Should not raise

        with get_connection(db_path, readonly=True) as conn:
            version = _get_schema_version(conn)
            assert version >= 1

    def test_enables_wal_mode(self, db_path, configured_env):
        """Enables WAL journal mode."""
        init_db(db_path)

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.execute("PRAGMA journal_mode")
            mode = cursor.fetchone()[0]
            assert mode.lower() == "wal"
        finally:
            conn.close()

    def test_creates_metrics_table(self, db_path, configured_env):
        """Creates metrics table with correct schema."""
        init_db(db_path)

        with get_connection(db_path, readonly=True) as conn:
            # Check table exists
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
            )
            assert cursor.fetchone() is not None

            # Check columns
            cursor = conn.execute("PRAGMA table_info(metrics)")
            columns = {row["name"]: row for row in cursor}
            assert "ts" in columns
            assert "role" in columns
            assert "metric" in columns
            assert "value" in columns

    def test_creates_db_meta_table(self, db_path, configured_env):
        """Creates db_meta table for schema versioning."""
        init_db(db_path)

        with get_connection(db_path, readonly=True) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='db_meta'"
            )
            assert cursor.fetchone() is not None


class TestGetConnection:
    """Tests for get_connection context manager."""

    def test_returns_connection(self, initialized_db):
        """Returns a working connection."""
        with get_connection(initialized_db) as conn:
            assert conn is not None
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_row_factory_enabled(self, initialized_db):
        """Row factory is set to sqlite3.Row."""
        with get_connection(initialized_db) as conn:
            conn.execute(
                "INSERT INTO metrics (ts, role, metric, value) VALUES (1, 'companion', 'test', 1.0)"
            )
        with get_connection(initialized_db, readonly=True) as conn:
            cursor = conn.execute("SELECT * FROM metrics WHERE metric = 'test'")
            row = cursor.fetchone()
            # sqlite3.Row supports dict-like access
            assert row["metric"] == "test"
            assert row["value"] == 1.0

    def test_commits_on_success(self, initialized_db):
        """Commits transaction on normal exit."""
        with get_connection(initialized_db) as conn:
            conn.execute(
                "INSERT INTO metrics (ts, role, metric, value) VALUES (1, 'companion', 'test', 1.0)"
            )

        # Check data persisted
        with get_connection(initialized_db, readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM metrics WHERE metric = 'test'")
            assert cursor.fetchone()[0] == 1

    def test_rollback_on_exception(self, initialized_db):
        """Rolls back transaction on exception."""
        try:
            with get_connection(initialized_db) as conn:
                conn.execute(
                    "INSERT INTO metrics (ts, role, metric, value) VALUES (2, 'companion', 'test2', 1.0)"
                )
                raise ValueError("Test error")
        except ValueError:
            pass

        # Check data was rolled back
        with get_connection(initialized_db, readonly=True) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM metrics WHERE metric = 'test2'")
            assert cursor.fetchone()[0] == 0

    def test_readonly_mode(self, initialized_db):
        """Read-only mode prevents writes."""
        with (
            get_connection(initialized_db, readonly=True) as conn,
            pytest.raises(sqlite3.OperationalError),
        ):
            conn.execute(
                "INSERT INTO metrics (ts, role, metric, value) VALUES (1, 'companion', 'test', 1.0)"
            )


class TestMigrationsDirectory:
    """Tests for migrations directory and files."""

    def test_migrations_dir_exists(self, migrations_dir):
        """Migrations directory exists."""
        assert migrations_dir.exists()
        assert migrations_dir.is_dir()

    def test_has_initial_migration(self, migrations_dir):
        """Has at least the initial schema migration."""
        sql_files = list(migrations_dir.glob("*.sql"))
        assert len(sql_files) >= 1

        # Check for 001 prefixed file
        initial = [f for f in sql_files if f.stem.startswith("001")]
        assert len(initial) == 1

    def test_migrations_are_numbered(self, migrations_dir):
        """Migration files follow NNN_description.sql pattern."""
        import re

        pattern = re.compile(r"^\d{3}_.*\.sql$")
        for sql_file in migrations_dir.glob("*.sql"):
            assert pattern.match(sql_file.name), f"{sql_file.name} doesn't match pattern"
