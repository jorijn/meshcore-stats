"""Snapshot tests for text report formatting.

These tests compare generated TXT reports against saved snapshots
to detect unintended changes in report layout and formatting.

To update snapshots, run: UPDATE_SNAPSHOTS=1 pytest tests/reports/test_snapshots.py
"""

import os
from datetime import date, datetime
from pathlib import Path

import pytest

from meshmon.reports import (
    DailyAggregate,
    LocationInfo,
    MetricStats,
    MonthlyAggregate,
    YearlyAggregate,
    format_monthly_txt,
    format_yearly_txt,
)


class TestTxtReportSnapshots:
    """Snapshot tests for WeeWX-style ASCII text reports."""

    @pytest.fixture
    def update_snapshots(self):
        """Return True if snapshots should be updated."""
        return os.environ.get("UPDATE_SNAPSHOTS", "").lower() in ("1", "true", "yes")

    @pytest.fixture
    def txt_snapshots_dir(self):
        """Path to TXT snapshots directory."""
        return Path(__file__).parent.parent / "snapshots" / "txt"

    @pytest.fixture
    def sample_location(self):
        """Create sample LocationInfo for testing."""
        return LocationInfo(
            name="Test Observatory",
            lat=52.3676,  # Amsterdam
            lon=4.9041,
            elev=2.0,
        )

    @pytest.fixture
    def repeater_monthly_aggregate(self):
        """Create sample MonthlyAggregate for repeater role testing."""
        daily_data = []

        # Create 5 days of sample data
        for day in range(1, 6):
            daily_data.append(
                DailyAggregate(
                    date=date(2024, 1, day),
                    metrics={
                        "bat": MetricStats(
                            min_value=3600 + day * 10,
                            min_time=datetime(2024, 1, day, 4, 0),
                            max_value=3900 + day * 10,
                            max_time=datetime(2024, 1, day, 14, 0),
                            mean=3750 + day * 10,
                            count=96,
                        ),
                        "bat_pct": MetricStats(
                            mean=65.0 + day * 2,
                            count=96,
                        ),
                        "last_rssi": MetricStats(
                            mean=-85.0 - day,
                            count=96,
                        ),
                        "last_snr": MetricStats(
                            mean=8.5 + day * 0.2,
                            count=96,
                        ),
                        "noise_floor": MetricStats(
                            mean=-115.0,
                            count=96,
                        ),
                        "nb_recv": MetricStats(
                            total=500 + day * 100,
                            count=96,
                            reboot_count=0,
                        ),
                        "nb_sent": MetricStats(
                            total=200 + day * 50,
                            count=96,
                            reboot_count=0,
                        ),
                        "airtime": MetricStats(
                            total=120 + day * 20,
                            count=96,
                            reboot_count=0,
                        ),
                    },
                    snapshot_count=96,
                )
            )

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=daily_data,
            summary={
                "bat": MetricStats(
                    min_value=3610,
                    min_time=datetime(2024, 1, 1, 4, 0),
                    max_value=3950,
                    max_time=datetime(2024, 1, 5, 14, 0),
                    mean=3780,
                    count=480,
                ),
                "bat_pct": MetricStats(
                    mean=71.0,
                    count=480,
                ),
                "last_rssi": MetricStats(
                    mean=-88.0,
                    count=480,
                ),
                "last_snr": MetricStats(
                    mean=9.1,
                    count=480,
                ),
                "noise_floor": MetricStats(
                    mean=-115.0,
                    count=480,
                ),
                "nb_recv": MetricStats(
                    total=4000,
                    count=480,
                    reboot_count=0,
                ),
                "nb_sent": MetricStats(
                    total=1750,
                    count=480,
                    reboot_count=0,
                ),
                "airtime": MetricStats(
                    total=900,
                    count=480,
                    reboot_count=0,
                ),
            },
        )

    @pytest.fixture
    def companion_monthly_aggregate(self):
        """Create sample MonthlyAggregate for companion role testing."""
        daily_data = []

        # Create 5 days of sample data
        for day in range(1, 6):
            daily_data.append(
                DailyAggregate(
                    date=date(2024, 1, day),
                    metrics={
                        "battery_mv": MetricStats(
                            min_value=3700 + day * 10,
                            min_time=datetime(2024, 1, day, 5, 0),
                            max_value=4000 + day * 10,
                            max_time=datetime(2024, 1, day, 12, 0),
                            mean=3850 + day * 10,
                            count=1440,
                        ),
                        "bat_pct": MetricStats(
                            mean=75.0 + day * 2,
                            count=1440,
                        ),
                        "contacts": MetricStats(
                            mean=8 + day,
                            count=1440,
                        ),
                        "recv": MetricStats(
                            total=1000 + day * 200,
                            count=1440,
                            reboot_count=0,
                        ),
                        "sent": MetricStats(
                            total=500 + day * 100,
                            count=1440,
                            reboot_count=0,
                        ),
                    },
                    snapshot_count=1440,
                )
            )

        return MonthlyAggregate(
            year=2024,
            month=1,
            role="companion",
            daily=daily_data,
            summary={
                "battery_mv": MetricStats(
                    min_value=3710,
                    min_time=datetime(2024, 1, 1, 5, 0),
                    max_value=4050,
                    max_time=datetime(2024, 1, 5, 12, 0),
                    mean=3880,
                    count=7200,
                ),
                "bat_pct": MetricStats(
                    mean=81.0,
                    count=7200,
                ),
                "contacts": MetricStats(
                    mean=11.0,
                    count=7200,
                ),
                "recv": MetricStats(
                    total=8000,
                    count=7200,
                    reboot_count=0,
                ),
                "sent": MetricStats(
                    total=4000,
                    count=7200,
                    reboot_count=0,
                ),
            },
        )

    @pytest.fixture
    def repeater_yearly_aggregate(self):
        """Create sample YearlyAggregate for repeater role testing."""
        monthly_data = []

        # Create 3 months of sample data
        for month in range(1, 4):
            monthly_data.append(
                MonthlyAggregate(
                    year=2024,
                    month=month,
                    role="repeater",
                    daily=[],  # Daily details not needed for yearly summary
                    summary={
                        "bat": MetricStats(
                            min_value=3500 + month * 50,
                            min_time=datetime(2024, month, 15, 4, 0),
                            max_value=3950 + month * 20,
                            max_time=datetime(2024, month, 20, 14, 0),
                            mean=3700 + month * 30,
                            count=2976,  # ~31 days * 96 readings
                        ),
                        "bat_pct": MetricStats(
                            mean=60.0 + month * 5,
                            count=2976,
                        ),
                        "last_rssi": MetricStats(
                            mean=-90.0 + month,
                            count=2976,
                        ),
                        "last_snr": MetricStats(
                            mean=7.5 + month * 0.5,
                            count=2976,
                        ),
                        "nb_recv": MetricStats(
                            total=30000 + month * 5000,
                            count=2976,
                            reboot_count=0,
                        ),
                        "nb_sent": MetricStats(
                            total=15000 + month * 2500,
                            count=2976,
                            reboot_count=0,
                        ),
                    },
                )
            )

        return YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=monthly_data,
            summary={
                "bat": MetricStats(
                    min_value=3550,
                    min_time=datetime(2024, 1, 15, 4, 0),
                    max_value=4010,
                    max_time=datetime(2024, 3, 20, 14, 0),
                    mean=3760,
                    count=8928,
                ),
                "bat_pct": MetricStats(
                    mean=70.0,
                    count=8928,
                ),
                "last_rssi": MetricStats(
                    mean=-88.0,
                    count=8928,
                ),
                "last_snr": MetricStats(
                    mean=8.5,
                    count=8928,
                ),
                "nb_recv": MetricStats(
                    total=120000,
                    count=8928,
                    reboot_count=0,
                ),
                "nb_sent": MetricStats(
                    total=60000,
                    count=8928,
                    reboot_count=0,
                ),
            },
        )

    @pytest.fixture
    def companion_yearly_aggregate(self):
        """Create sample YearlyAggregate for companion role testing."""
        monthly_data = []

        # Create 3 months of sample data
        for month in range(1, 4):
            monthly_data.append(
                MonthlyAggregate(
                    year=2024,
                    month=month,
                    role="companion",
                    daily=[],
                    summary={
                        "battery_mv": MetricStats(
                            min_value=3600 + month * 30,
                            min_time=datetime(2024, month, 10, 5, 0),
                            max_value=4100 + month * 20,
                            max_time=datetime(2024, month, 25, 12, 0),
                            mean=3850 + month * 25,
                            count=44640,  # ~31 days * 1440 readings
                        ),
                        "bat_pct": MetricStats(
                            mean=70.0 + month * 3,
                            count=44640,
                        ),
                        "contacts": MetricStats(
                            mean=10 + month,
                            count=44640,
                        ),
                        "recv": MetricStats(
                            total=50000 + month * 10000,
                            count=44640,
                            reboot_count=0,
                        ),
                        "sent": MetricStats(
                            total=25000 + month * 5000,
                            count=44640,
                            reboot_count=0,
                        ),
                    },
                )
            )

        return YearlyAggregate(
            year=2024,
            role="companion",
            monthly=monthly_data,
            summary={
                "battery_mv": MetricStats(
                    min_value=3630,
                    min_time=datetime(2024, 1, 10, 5, 0),
                    max_value=4160,
                    max_time=datetime(2024, 3, 25, 12, 0),
                    mean=3900,
                    count=133920,
                ),
                "bat_pct": MetricStats(
                    mean=76.0,
                    count=133920,
                ),
                "contacts": MetricStats(
                    mean=12.0,
                    count=133920,
                ),
                "recv": MetricStats(
                    total=210000,
                    count=133920,
                    reboot_count=0,
                ),
                "sent": MetricStats(
                    total=105000,
                    count=133920,
                    reboot_count=0,
                ),
            },
        )

    def _assert_snapshot_match(
        self,
        actual: str,
        snapshot_path: Path,
        update: bool,
    ) -> None:
        """Compare TXT report against snapshot, with optional update mode."""
        if update:
            # Update mode: write actual to snapshot
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(actual, encoding="utf-8")
            pytest.skip(f"Snapshot updated: {snapshot_path}")
        else:
            # Compare mode
            if not snapshot_path.exists():
                # Create new snapshot if it doesn't exist
                snapshot_path.parent.mkdir(parents=True, exist_ok=True)
                snapshot_path.write_text(actual, encoding="utf-8")
                pytest.fail(
                    f"Snapshot created: {snapshot_path}\n"
                    f"Run tests again to verify, or set UPDATE_SNAPSHOTS=1 to regenerate."
                )

            expected = snapshot_path.read_text(encoding="utf-8")

            if actual != expected:
                # Show differences for debugging
                actual_lines = actual.splitlines()
                expected_lines = expected.splitlines()

                diff_info = []
                for i, (a, e) in enumerate(zip(actual_lines, expected_lines, strict=False), 1):
                    if a != e:
                        diff_info.append(f"Line {i} differs:")
                        diff_info.append(f"  Expected: '{e}'")
                        diff_info.append(f"  Actual:   '{a}'")
                        if len(diff_info) > 15:
                            diff_info.append("  (more differences omitted)")
                            break

                if len(actual_lines) != len(expected_lines):
                    diff_info.append(
                        f"Line count: expected {len(expected_lines)}, got {len(actual_lines)}"
                    )

                pytest.fail(
                    f"Snapshot mismatch: {snapshot_path}\n"
                    f"Set UPDATE_SNAPSHOTS=1 to regenerate.\n\n"
                    + "\n".join(diff_info)
                )

    def test_monthly_report_repeater(
        self,
        repeater_monthly_aggregate,
        sample_location,
        txt_snapshots_dir,
        update_snapshots,
    ):
        """Monthly repeater report matches snapshot."""
        result = format_monthly_txt(
            repeater_monthly_aggregate,
            "Test Repeater",
            sample_location,
        )

        snapshot_path = txt_snapshots_dir / "monthly_report_repeater.txt"
        self._assert_snapshot_match(result, snapshot_path, update_snapshots)

    def test_monthly_report_companion(
        self,
        companion_monthly_aggregate,
        sample_location,
        txt_snapshots_dir,
        update_snapshots,
    ):
        """Monthly companion report matches snapshot."""
        result = format_monthly_txt(
            companion_monthly_aggregate,
            "Test Companion",
            sample_location,
        )

        snapshot_path = txt_snapshots_dir / "monthly_report_companion.txt"
        self._assert_snapshot_match(result, snapshot_path, update_snapshots)

    def test_yearly_report_repeater(
        self,
        repeater_yearly_aggregate,
        sample_location,
        txt_snapshots_dir,
        update_snapshots,
    ):
        """Yearly repeater report matches snapshot."""
        result = format_yearly_txt(
            repeater_yearly_aggregate,
            "Test Repeater",
            sample_location,
        )

        snapshot_path = txt_snapshots_dir / "yearly_report_repeater.txt"
        self._assert_snapshot_match(result, snapshot_path, update_snapshots)

    def test_yearly_report_companion(
        self,
        companion_yearly_aggregate,
        sample_location,
        txt_snapshots_dir,
        update_snapshots,
    ):
        """Yearly companion report matches snapshot."""
        result = format_yearly_txt(
            companion_yearly_aggregate,
            "Test Companion",
            sample_location,
        )

        snapshot_path = txt_snapshots_dir / "yearly_report_companion.txt"
        self._assert_snapshot_match(result, snapshot_path, update_snapshots)

    def test_empty_monthly_report(
        self,
        sample_location,
        txt_snapshots_dir,
        update_snapshots,
    ):
        """Empty monthly report matches snapshot."""
        empty_aggregate = MonthlyAggregate(
            year=2024,
            month=1,
            role="repeater",
            daily=[],
            summary={},
        )

        result = format_monthly_txt(
            empty_aggregate,
            "Test Repeater",
            sample_location,
        )

        snapshot_path = txt_snapshots_dir / "empty_monthly_report.txt"
        self._assert_snapshot_match(result, snapshot_path, update_snapshots)

    def test_empty_yearly_report(
        self,
        sample_location,
        txt_snapshots_dir,
        update_snapshots,
    ):
        """Empty yearly report matches snapshot."""
        empty_aggregate = YearlyAggregate(
            year=2024,
            role="repeater",
            monthly=[],
            summary={},
        )

        result = format_yearly_txt(
            empty_aggregate,
            "Test Repeater",
            sample_location,
        )

        snapshot_path = txt_snapshots_dir / "empty_yearly_report.txt"
        self._assert_snapshot_match(result, snapshot_path, update_snapshots)
