"""Snapshot test fixtures and utilities.

This package contains:
- conftest.py: Shared fixtures for snapshot testing
- svg/: SVG chart snapshot files
- txt/: TXT report snapshot files

To update snapshots, run tests with UPDATE_SNAPSHOTS=1 environment variable:
    UPDATE_SNAPSHOTS=1 pytest tests/charts/test_chart_render.py::TestSvgSnapshots
    UPDATE_SNAPSHOTS=1 pytest tests/reports/test_snapshots.py

Or use the generator script to create all snapshots at once:
    python scripts/generate_snapshots.py
"""
