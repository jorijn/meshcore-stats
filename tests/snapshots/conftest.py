"""Fixtures for snapshot testing.

Provides shared utilities for comparing test output against saved snapshots.
Supports updating snapshots via UPDATE_SNAPSHOTS=1 environment variable.
"""

import os
import pytest
from pathlib import Path


@pytest.fixture
def update_snapshots():
    """Return True if snapshots should be updated instead of compared.

    Set UPDATE_SNAPSHOTS=1 environment variable to regenerate snapshots.
    """
    return os.environ.get("UPDATE_SNAPSHOTS", "").lower() in ("1", "true", "yes")


@pytest.fixture
def svg_snapshots_dir():
    """Path to SVG snapshots directory."""
    return Path(__file__).parent / "svg"


@pytest.fixture
def txt_snapshots_dir():
    """Path to TXT snapshots directory."""
    return Path(__file__).parent / "txt"


def assert_snapshot_match(
    actual: str,
    snapshot_path: Path,
    update: bool = False,
    normalize_fn=None,
) -> None:
    """Compare actual output against a saved snapshot.

    Args:
        actual: The actual output to compare
        snapshot_path: Path to the snapshot file
        update: If True, update the snapshot instead of comparing
        normalize_fn: Optional function to normalize both actual and expected
                      before comparison (e.g., for removing non-deterministic content)

    Raises:
        AssertionError: If actual doesn't match expected and update is False
    """
    if normalize_fn:
        actual = normalize_fn(actual)

    if update:
        # Update mode: write actual to snapshot
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_text(actual, encoding="utf-8")
        pytest.skip(f"Snapshot updated: {snapshot_path}")
    else:
        # Compare mode: check against existing snapshot
        if not snapshot_path.exists():
            # Create new snapshot if it doesn't exist
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(actual, encoding="utf-8")
            pytest.fail(
                f"Snapshot created: {snapshot_path}\n"
                f"Run tests again to verify, or set UPDATE_SNAPSHOTS=1 to skip this check."
            )

        expected = snapshot_path.read_text(encoding="utf-8")
        if normalize_fn:
            expected = normalize_fn(expected)

        if actual != expected:
            # Provide helpful diff information
            actual_lines = actual.splitlines()
            expected_lines = expected.splitlines()

            diff_info = []
            for i, (a, e) in enumerate(zip(actual_lines, expected_lines), 1):
                if a != e:
                    diff_info.append(f"Line {i}:")
                    diff_info.append(f"  Expected: {e[:100]}...")
                    diff_info.append(f"  Actual:   {a[:100]}...")
                    if len(diff_info) > 15:  # Limit diff output
                        diff_info.append("  ...")
                        break

            if len(actual_lines) != len(expected_lines):
                diff_info.append(
                    f"Line count: expected {len(expected_lines)}, got {len(actual_lines)}"
                )

            diff_str = "\n".join(diff_info)
            pytest.fail(
                f"Snapshot mismatch: {snapshot_path}\n"
                f"Set UPDATE_SNAPSHOTS=1 to update.\n\n"
                f"Differences:\n{diff_str}"
            )
