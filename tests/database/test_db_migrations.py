"""Tests for database migration system."""

import sqlite3
from pathlib import Path

import pytest

from meshmon.db import (
    _apply_migrations,
    _get_migration_files,
    _get_schema_version,
    _set_schema_version,
    get_schema_version,
)


class TestGetMigrationFiles:
    """Tests for _get_migration_files function."""

    def test_finds_migration_files(self):
        """Should find actual migration files in MIGRATIONS_DIR."""
        migrations = _get_migration_files()

        assert len(migrations) >= 2
        # Should include 001 and 002
        versions = [v for v, _ in migrations]
        assert 1 in versions
        assert 2 in versions

    def test_returns_sorted_by_version(self):
        """Migrations should be sorted by version number."""
        migrations = _get_migration_files()

        versions = [v for v, _ in migrations]
        assert versions == sorted(versions)

    def test_returns_path_objects(self):
        """Each migration should have a Path object."""
        migrations = _get_migration_files()

        for _version, path in migrations:
            assert isinstance(path, Path)
            assert path.exists()
            assert path.suffix == ".sql"

    def test_extracts_version_from_filename(self):
        """Version number extracted from filename prefix."""
        migrations = _get_migration_files()

        for version, path in migrations:
            filename_version = int(path.stem.split("_")[0])
            assert version == filename_version

    def test_empty_when_no_migrations_dir(self, tmp_path, monkeypatch):
        """Returns empty list when migrations dir doesn't exist."""
        fake_dir = tmp_path / "nonexistent"
        monkeypatch.setattr("meshmon.db.MIGRATIONS_DIR", fake_dir)

        migrations = _get_migration_files()

        assert migrations == []

    def test_skips_invalid_filenames(self, tmp_path, monkeypatch):
        """Skips files without valid version prefix."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        # Create valid migration
        (migrations_dir / "001_valid.sql").write_text("-- valid")
        # Create invalid migrations
        (migrations_dir / "invalid_name.sql").write_text("-- invalid")
        (migrations_dir / "abc_noversion.sql").write_text("-- no version")

        monkeypatch.setattr("meshmon.db.MIGRATIONS_DIR", migrations_dir)

        migrations = _get_migration_files()

        assert len(migrations) == 1
        assert migrations[0][0] == 1


class TestGetSchemaVersion:
    """Tests for _get_schema_version internal function."""

    def test_returns_zero_for_fresh_db(self, tmp_path):
        """Fresh database with no db_meta returns 0."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        version = _get_schema_version(conn)

        assert version == 0
        conn.close()

    def test_returns_stored_version(self, tmp_path):
        """Returns version from db_meta table."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO db_meta (key, value) VALUES ('schema_version', '5')"
        )
        conn.commit()

        version = _get_schema_version(conn)

        assert version == 5
        conn.close()

    def test_returns_zero_when_key_missing(self, tmp_path):
        """Returns 0 if db_meta exists but schema_version key is missing."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO db_meta (key, value) VALUES ('other_key', 'value')"
        )
        conn.commit()

        version = _get_schema_version(conn)

        assert version == 0
        conn.close()


class TestSetSchemaVersion:
    """Tests for _set_schema_version internal function."""

    def test_inserts_new_version(self, tmp_path):
        """Can insert schema version into fresh db_meta."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        """)

        _set_schema_version(conn, 3)
        conn.commit()

        cursor = conn.execute(
            "SELECT value FROM db_meta WHERE key = 'schema_version'"
        )
        assert cursor.fetchone()[0] == "3"
        conn.close()

    def test_updates_existing_version(self, tmp_path):
        """Can update existing schema version."""
        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO db_meta (key, value) VALUES ('schema_version', '1')"
        )
        conn.commit()

        _set_schema_version(conn, 5)
        conn.commit()

        cursor = conn.execute(
            "SELECT value FROM db_meta WHERE key = 'schema_version'"
        )
        assert cursor.fetchone()[0] == "5"
        conn.close()


class TestApplyMigrations:
    """Tests for _apply_migrations function."""

    def test_applies_all_migrations_to_fresh_db(self, tmp_path, monkeypatch):
        """Applies all migrations to a fresh database."""
        # Create mock migrations
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_initial.sql").write_text("""
            CREATE TABLE IF NOT EXISTS db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            );
            CREATE TABLE test1 (id INTEGER);
        """)
        (migrations_dir / "002_second.sql").write_text("""
            CREATE TABLE test2 (id INTEGER);
        """)

        monkeypatch.setattr("meshmon.db.MIGRATIONS_DIR", migrations_dir)

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        _apply_migrations(conn)

        # Check both tables exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in cursor]
        assert "test1" in tables
        assert "test2" in tables
        assert "db_meta" in tables

        # Check version is updated
        assert _get_schema_version(conn) == 2
        conn.close()

    def test_skips_already_applied_migrations(self, tmp_path, monkeypatch):
        """Skips migrations that have already been applied."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_initial.sql").write_text("""
            CREATE TABLE IF NOT EXISTS db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            );
            CREATE TABLE test1 (id INTEGER);
        """)
        (migrations_dir / "002_second.sql").write_text("""
            CREATE TABLE test2 (id INTEGER);
        """)

        monkeypatch.setattr("meshmon.db.MIGRATIONS_DIR", migrations_dir)

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        # Apply first time
        _apply_migrations(conn)

        # Apply second time - should not fail
        _apply_migrations(conn)

        assert _get_schema_version(conn) == 2
        conn.close()

    def test_raises_when_no_migrations(self, tmp_path, monkeypatch):
        """Raises error when no migration files exist."""
        empty_dir = tmp_path / "empty_migrations"
        empty_dir.mkdir()
        monkeypatch.setattr("meshmon.db.MIGRATIONS_DIR", empty_dir)

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        with pytest.raises(RuntimeError, match="No migration files found"):
            _apply_migrations(conn)

        conn.close()

    def test_rolls_back_failed_migration(self, tmp_path, monkeypatch):
        """Rolls back if a migration fails."""
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()

        (migrations_dir / "001_initial.sql").write_text("""
            CREATE TABLE IF NOT EXISTS db_meta (
                key TEXT PRIMARY KEY NOT NULL,
                value TEXT NOT NULL
            );
            CREATE TABLE test1 (id INTEGER);
        """)
        (migrations_dir / "002_broken.sql").write_text("""
            THIS IS NOT VALID SQL;
        """)

        monkeypatch.setattr("meshmon.db.MIGRATIONS_DIR", migrations_dir)

        db_path = tmp_path / "test.db"
        conn = sqlite3.connect(db_path)

        with pytest.raises(RuntimeError, match="Migration.*failed"):
            _apply_migrations(conn)

        # Version should still be 1 (first migration applied)
        assert _get_schema_version(conn) == 1
        conn.close()


class TestPublicGetSchemaVersion:
    """Tests for public get_schema_version function."""

    def test_returns_zero_when_db_missing(self, configured_env):
        """Returns 0 when database file doesn't exist."""
        version = get_schema_version()
        assert version == 0

    def test_returns_version_from_existing_db(self, initialized_db):
        """Returns schema version from initialized database."""
        version = get_schema_version()

        # Should be at least version 2 (we have 2 migrations)
        assert version >= 2

    def test_uses_readonly_connection(self, initialized_db, monkeypatch):
        """Opens database in readonly mode."""
        calls = []
        original_get_connection = __import__(
            "meshmon.db", fromlist=["get_connection"]
        ).get_connection

        from contextlib import contextmanager

        @contextmanager
        def mock_get_connection(*args, **kwargs):
            calls.append(kwargs)
            with original_get_connection(*args, **kwargs) as conn:
                yield conn

        monkeypatch.setattr("meshmon.db.get_connection", mock_get_connection)

        get_schema_version()

        assert any(call.get("readonly") is True for call in calls)
