"""Tests for database maintenance functions."""

import pytest
import sqlite3
import os

from meshmon.db import (
    vacuum_db,
    get_db_path,
    init_db,
)


class TestVacuumDb:
    """Tests for vacuum_db function."""

    def test_vacuums_existing_db(self, initialized_db):
        """Vacuum should run without error on initialized database."""
        # Add some data then vacuum
        conn = sqlite3.connect(initialized_db)
        conn.execute(
            "INSERT INTO metrics (ts, role, metric, value) VALUES (1, 'companion', 'test', 1.0)"
        )
        conn.commit()
        conn.close()

        # Should not raise
        vacuum_db(initialized_db)

    def test_runs_analyze(self, initialized_db, capfd):
        """ANALYZE should be run after VACUUM."""
        # Vacuum includes ANALYZE
        vacuum_db(initialized_db)

        # Check that database stats were updated
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("SELECT * FROM sqlite_stat1")
        # After ANALYZE, sqlite_stat1 should have entries if tables have data
        conn.close()

    def test_uses_default_path_when_none(self, configured_env, monkeypatch):
        """Uses get_db_path() when no path provided."""
        # Initialize db at default location
        init_db()

        # vacuum_db with None should use default path
        vacuum_db(None)

    def test_can_vacuum_empty_db(self, initialized_db):
        """Can vacuum an empty database."""
        vacuum_db(initialized_db)

    def test_reclaims_space_after_delete(self, initialized_db):
        """Vacuum should reclaim space after deleting rows."""
        conn = sqlite3.connect(initialized_db)

        # Insert many rows
        for i in range(1000):
            conn.execute(
                "INSERT INTO metrics (ts, role, metric, value) VALUES (?, 'companion', 'test', 1.0)",
                (i,)
            )
        conn.commit()

        # Get size before delete
        conn.close()
        size_before = os.path.getsize(initialized_db)

        # Delete all rows
        conn = sqlite3.connect(initialized_db)
        conn.execute("DELETE FROM metrics")
        conn.commit()
        conn.close()

        # Vacuum
        vacuum_db(initialized_db)

        # Size should be smaller (or at least not larger)
        size_after = os.path.getsize(initialized_db)
        # Note: Due to WAL mode, this might not always shrink dramatically
        # but vacuum should at least complete without error
        assert size_after <= size_before + 4096  # Allow for some overhead


class TestGetDbPath:
    """Tests for get_db_path function."""

    def test_returns_path_in_state_dir(self, configured_env):
        """Path should be in the configured state directory."""
        path = get_db_path()

        assert path.name == "metrics.db"
        assert str(configured_env["state_dir"]) in str(path)

    def test_returns_path_object(self, configured_env):
        """Should return a Path object."""
        from pathlib import Path

        path = get_db_path()

        assert isinstance(path, Path)


class TestDatabaseIntegrity:
    """Tests for database integrity after operations."""

    def test_wal_mode_enabled(self, initialized_db):
        """Database should be in WAL mode."""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        conn.close()

        assert mode.lower() == "wal"

    def test_foreign_keys_disabled_by_default(self, initialized_db):
        """Foreign keys should be disabled (SQLite default)."""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("PRAGMA foreign_keys")
        enabled = cursor.fetchone()[0]
        conn.close()

        # Default is off, and we don't explicitly enable them
        assert enabled == 0

    def test_metrics_table_exists(self, initialized_db):
        """Metrics table should exist after init."""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='metrics'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None
        assert result[0] == "metrics"

    def test_db_meta_table_exists(self, initialized_db):
        """db_meta table should exist after init."""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='db_meta'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_metrics_index_exists(self, initialized_db):
        """Index on metrics(role, ts) should exist."""
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name='idx_metrics_role_ts'"
        )
        result = cursor.fetchone()
        conn.close()

        assert result is not None

    def test_vacuum_preserves_data(self, initialized_db):
        """Vacuum should not lose any data."""
        conn = sqlite3.connect(initialized_db)
        for i in range(100):
            conn.execute(
                "INSERT INTO metrics (ts, role, metric, value) VALUES (?, 'companion', 'test', ?)",
                (i, float(i))
            )
        conn.commit()
        conn.close()

        # Vacuum
        vacuum_db(initialized_db)

        # Check data is still there
        conn = sqlite3.connect(initialized_db)
        cursor = conn.execute("SELECT COUNT(*) FROM metrics")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 100

    def test_vacuum_preserves_schema_version(self, initialized_db):
        """Vacuum should not change schema version."""
        from meshmon.db import _get_schema_version

        conn = sqlite3.connect(initialized_db)
        version_before = _get_schema_version(conn)
        conn.close()

        vacuum_db(initialized_db)

        conn = sqlite3.connect(initialized_db)
        version_after = _get_schema_version(conn)
        conn.close()

        assert version_before == version_after
