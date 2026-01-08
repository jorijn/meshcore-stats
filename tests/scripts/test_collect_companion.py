"""Tests for collect_companion.py script entry point.

These tests verify the actual script behavior, not just the library code.
The script is the entry point that users run - if it breaks, everything breaks.
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest

from tests.scripts.conftest import load_script_module


def load_collect_companion():
    """Load collect_companion.py as a module."""
    return load_script_module("collect_companion.py")


class TestCollectCompanionImport:
    """Verify script can be imported without errors."""

    def test_imports_successfully(self, configured_env):
        """Script should import without errors."""
        module = load_collect_companion()

        assert hasattr(module, "main")
        assert hasattr(module, "collect_companion")
        assert callable(module.main)

    def test_collect_companion_is_async(self, configured_env):
        """collect_companion() should be an async function."""
        module = load_collect_companion()
        assert inspect.iscoroutinefunction(module.collect_companion)


class TestCollectCompanionExitCodes:
    """Test exit code behavior - critical for monitoring."""

    @pytest.mark.asyncio
    async def test_returns_zero_on_successful_collection(
        self, configured_env, async_context_manager_factory, mock_run_command_factory
    ):
        """Successful collection should return exit code 0."""
        module = load_collect_companion()

        responses = {
            "send_appstart": (True, "SELF_INFO", {}, None),
            "send_device_query": (True, "DEVICE_INFO", {}, None),
            "get_time": (True, "TIME", {"time": 1234567890}, None),
            "get_self_telemetry": (True, "TELEMETRY", {}, None),
            "get_custom_vars": (True, "CUSTOM_VARS", {}, None),
            "get_contacts": (True, "CONTACTS", {"c1": {}, "c2": {}}, None),
            "get_stats_core": (
                True,
                "STATS_CORE",
                {"battery_mv": 3850, "uptime_secs": 86400},
                None,
            ),
            "get_stats_radio": (True, "STATS_RADIO", {"noise_floor": -115}, None),
            "get_stats_packets": (True, "STATS_PACKETS", {"recv": 100, "sent": 50}, None),
        }

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(
                module, "run_command", side_effect=mock_run_command_factory(responses)
            ),
            patch.object(module, "insert_metrics", return_value=5),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 0

    @pytest.mark.asyncio
    async def test_returns_one_on_connection_failure(
        self, configured_env, async_context_manager_factory
    ):
        """Failed connection should return exit code 1."""
        module = load_collect_companion()

        # Connection returns None (failed)
        ctx_mock = async_context_manager_factory(None)

        with patch.object(module, "connect_with_lock", return_value=ctx_mock):
            exit_code = await module.collect_companion()

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_returns_one_when_no_commands_succeed(
        self, configured_env, async_context_manager_factory
    ):
        """No successful commands should return exit code 1."""
        module = load_collect_companion()

        # All commands fail
        async def mock_run_command_fail(mc, coro, name):
            return (False, None, None, "Command failed")

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command_fail),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_returns_one_on_database_error(
        self, configured_env, async_context_manager_factory, mock_run_command_factory
    ):
        """Database write failure should return exit code 1."""
        module = load_collect_companion()

        responses = {
            "get_stats_core": (True, "STATS_CORE", {"battery_mv": 3850}, None),
        }
        # Default to success for other commands
        default = (True, "OK", {}, None)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(
                module, "run_command", side_effect=mock_run_command_factory(responses, default)
            ),
            patch.object(module, "insert_metrics", side_effect=Exception("DB error")),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 1


class TestCollectCompanionMetrics:
    """Test metric collection behavior."""

    @pytest.mark.asyncio
    async def test_collects_all_numeric_fields_from_stats(
        self, configured_env, async_context_manager_factory, mock_run_command_factory
    ):
        """Should insert all numeric fields from stats responses."""
        module = load_collect_companion()
        collected_metrics = {}

        responses = {
            "send_appstart": (True, "SELF_INFO", {}, None),
            "send_device_query": (True, "DEVICE_INFO", {}, None),
            "get_time": (True, "TIME", {}, None),
            "get_self_telemetry": (True, "TELEMETRY", {}, None),
            "get_custom_vars": (True, "CUSTOM_VARS", {}, None),
            "get_contacts": (True, "CONTACTS", {"c1": {}, "c2": {}, "c3": {}}, None),
            "get_stats_core": (
                True,
                "STATS_CORE",
                {"battery_mv": 3850, "uptime_secs": 86400, "errors": 0},
                None,
            ),
            "get_stats_radio": (
                True,
                "STATS_RADIO",
                {"noise_floor": -115, "last_rssi": -85, "last_snr": 7.5},
                None,
            ),
            "get_stats_packets": (True, "STATS_PACKETS", {"recv": 100, "sent": 50}, None),
        }

        def capture_metrics(ts, role, metrics, conn=None):
            collected_metrics.update(metrics)
            return len(metrics)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(
                module, "run_command", side_effect=mock_run_command_factory(responses)
            ),
            patch.object(module, "insert_metrics", side_effect=capture_metrics),
        ):
            await module.collect_companion()

        # Verify all expected metrics were collected
        assert collected_metrics["battery_mv"] == 3850
        assert collected_metrics["uptime_secs"] == 86400
        assert collected_metrics["contacts"] == 3  # From get_contacts count
        assert collected_metrics["recv"] == 100
        assert collected_metrics["sent"] == 50
        assert collected_metrics["noise_floor"] == -115

    @pytest.mark.asyncio
    async def test_telemetry_not_extracted_when_disabled(
        self, configured_env, async_context_manager_factory, monkeypatch
    ):
        """Telemetry metrics should NOT be extracted when TELEMETRY_ENABLED=0 (default)."""
        module = load_collect_companion()
        collected_metrics = {}

        async def mock_run_command(mc, coro, name):
            if name == "get_self_telemetry":
                # Return telemetry payload with LPP data
                return (True, "TELEMETRY", {"lpp": b"\x00\x67\x01\x00"}, None)
            if name == "get_stats_core":
                return (True, "STATS_CORE", {"battery_mv": 3850}, None)
            return (True, "OK", {}, None)

        def capture_metrics(ts, role, metrics, conn=None):
            collected_metrics.update(metrics)
            return len(metrics)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
            patch.object(module, "insert_metrics", side_effect=capture_metrics),
        ):
            await module.collect_companion()

        # No telemetry.* keys should be present
        telemetry_keys = [k for k in collected_metrics if k.startswith("telemetry.")]
        assert len(telemetry_keys) == 0

    @pytest.mark.asyncio
    async def test_telemetry_extracted_when_enabled(
        self, configured_env, async_context_manager_factory, monkeypatch
    ):
        """Telemetry metrics SHOULD be extracted when TELEMETRY_ENABLED=1."""
        # Enable telemetry BEFORE loading the module
        monkeypatch.setenv("TELEMETRY_ENABLED", "1")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_companion()
        collected_metrics = {}

        # LPP data format: list of dictionaries with type, channel, value
        # This matches the format from MeshCore API
        lpp_data = [
            {"type": "temperature", "channel": 0, "value": 25.5},
        ]

        async def mock_run_command(mc, coro, name):
            if name == "get_self_telemetry":
                return (True, "TELEMETRY", {"lpp": lpp_data}, None)
            if name == "get_stats_core":
                return (True, "STATS_CORE", {"battery_mv": 3850}, None)
            return (True, "OK", {}, None)

        def capture_metrics(ts, role, metrics, conn=None):
            collected_metrics.update(metrics)
            return len(metrics)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
            patch.object(module, "insert_metrics", side_effect=capture_metrics),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 0
        # Telemetry keys should be present
        telemetry_keys = [k for k in collected_metrics if k.startswith("telemetry.")]
        assert len(telemetry_keys) > 0, f"Expected telemetry keys, got: {collected_metrics.keys()}"
        assert "telemetry.temperature.0" in collected_metrics
        assert collected_metrics["telemetry.temperature.0"] == 25.5

    @pytest.mark.asyncio
    async def test_telemetry_extraction_handles_invalid_lpp(
        self, configured_env, async_context_manager_factory, monkeypatch
    ):
        """Telemetry extraction should handle invalid LPP data gracefully."""
        monkeypatch.setenv("TELEMETRY_ENABLED", "1")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_companion()
        collected_metrics = {}

        async def mock_run_command(mc, coro, name):
            if name == "get_self_telemetry":
                # Invalid LPP data (too short)
                return (True, "TELEMETRY", {"lpp": b"\x00"}, None)
            if name == "get_stats_core":
                return (True, "STATS_CORE", {"battery_mv": 3850}, None)
            return (True, "OK", {}, None)

        def capture_metrics(ts, role, metrics, conn=None):
            collected_metrics.update(metrics)
            return len(metrics)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
            patch.object(module, "insert_metrics", side_effect=capture_metrics),
        ):
            exit_code = await module.collect_companion()

        # Should still succeed - just no telemetry extracted
        assert exit_code == 0
        # No telemetry keys because LPP was invalid
        telemetry_keys = [k for k in collected_metrics if k.startswith("telemetry.")]
        assert len(telemetry_keys) == 0


class TestPartialSuccessScenarios:
    """Test behavior when only some commands succeed."""

    @pytest.mark.asyncio
    async def test_succeeds_with_only_stats_core(
        self, configured_env, async_context_manager_factory
    ):
        """Should succeed if only stats_core returns metrics."""
        module = load_collect_companion()
        collected_metrics = {}

        async def mock_run_command(mc, coro, name):
            if name == "get_stats_core":
                return (True, "STATS_CORE", {"battery_mv": 3850, "uptime_secs": 1000}, None)
            # All other commands fail
            return (False, None, None, "Timeout")

        def capture_metrics(ts, role, metrics, conn=None):
            collected_metrics.update(metrics)
            return len(metrics)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
            patch.object(module, "insert_metrics", side_effect=capture_metrics),
        ):
            exit_code = await module.collect_companion()

        # Should succeed because stats_core succeeded and had metrics
        assert exit_code == 0
        assert collected_metrics["battery_mv"] == 3850

    @pytest.mark.asyncio
    async def test_succeeds_with_only_contacts(
        self, configured_env, async_context_manager_factory
    ):
        """Should succeed if only contacts command returns data."""
        module = load_collect_companion()
        collected_metrics = {}

        async def mock_run_command(mc, coro, name):
            if name == "get_contacts":
                return (True, "CONTACTS", {"c1": {}, "c2": {}}, None)
            # Stats commands succeed but return no numeric data
            if name.startswith("get_stats"):
                return (True, "OK", {}, None)
            # Other commands succeed
            return (True, "OK", {}, None)

        def capture_metrics(ts, role, metrics, conn=None):
            collected_metrics.update(metrics)
            return len(metrics)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
            patch.object(module, "insert_metrics", side_effect=capture_metrics),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 0
        assert collected_metrics["contacts"] == 2

    @pytest.mark.asyncio
    async def test_fails_when_metrics_empty_despite_success(
        self, configured_env, async_context_manager_factory
    ):
        """Should fail if commands succeed but no metrics collected."""
        module = load_collect_companion()

        async def mock_run_command(mc, coro, name):
            # Commands succeed but return empty/non-dict payloads
            if name == "get_stats_core":
                return (True, "STATS_CORE", None, None)  # No payload
            if name == "get_stats_radio":
                return (True, "STATS_RADIO", "not a dict", None)  # Invalid payload
            if name == "get_stats_packets":
                return (True, "STATS_PACKETS", {}, None)  # Empty payload
            if name == "get_contacts":
                return (False, None, None, "Failed")  # Fails
            return (True, "OK", {}, None)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
        ):
            exit_code = await module.collect_companion()

        # Should fail because no metrics were collected
        assert exit_code == 1


class TestExceptionHandling:
    """Test exception handling in the command loop (lines 165-166)."""

    @pytest.mark.asyncio
    async def test_handles_exception_in_command_loop(
        self, configured_env, async_context_manager_factory
    ):
        """Should catch and log exceptions during command execution."""
        module = load_collect_companion()

        call_count = 0

        async def mock_run_command_with_exception(mc, coro, name):
            nonlocal call_count
            call_count += 1
            if call_count == 3:  # Fail on third command
                raise RuntimeError("Unexpected network error")
            return (True, "OK", {}, None)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command_with_exception),
            patch.object(module, "log") as mock_log,
        ):
            exit_code = await module.collect_companion()

        # Should have logged the error
        error_calls = [c for c in mock_log.error.call_args_list if "Error during collection" in str(c)]
        assert len(error_calls) > 0

        # Should return 1 because exception interrupted collection
        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_exception_closes_connection_properly(
        self, configured_env, async_context_manager_factory
    ):
        """Context manager should still exit properly after exception."""
        module = load_collect_companion()

        async def mock_run_command_raise(mc, coro, name):
            raise RuntimeError("Connection lost")

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command_raise),
        ):
            await module.collect_companion()

        # Verify context manager was properly exited
        assert ctx_mock.exited is True


class TestMainEntryPoint:
    """Test the main() entry point behavior."""

    def test_main_calls_init_db(self, configured_env):
        """main() should initialize database before collection."""
        module = load_collect_companion()

        with (
            patch.object(module, "init_db") as mock_init,
            patch.object(module, "collect_companion", return_value=0),
            patch.object(module, "asyncio") as mock_asyncio,
            patch.object(module, "sys"),
        ):
            # Patch collect_companion to return a non-coroutine to avoid unawaited coroutine warning
            mock_asyncio.run.return_value = 0
            module.main()

            mock_init.assert_called_once()

    def test_main_exits_with_collection_result(self, configured_env):
        """main() should exit with the collection exit code."""
        module = load_collect_companion()

        with (
            patch.object(module, "init_db"),
            patch.object(module, "collect_companion", return_value=1),
            patch.object(module, "asyncio") as mock_asyncio,
            patch.object(module, "sys") as mock_sys,
        ):
            # Patch collect_companion to return a non-coroutine to avoid unawaited coroutine warning
            mock_asyncio.run.return_value = 1  # Collection failed
            module.main()

            mock_sys.exit.assert_called_once_with(1)

    def test_main_runs_collect_companion_async(self, configured_env):
        """main() should run collect_companion() with asyncio.run()."""
        module = load_collect_companion()

        with (
            patch.object(module, "init_db"),
            patch.object(module, "collect_companion", return_value=0),
            patch.object(module, "asyncio") as mock_asyncio,
            patch.object(module, "sys"),
        ):
            # Patch collect_companion to return a non-coroutine to avoid unawaited coroutine warning
            mock_asyncio.run.return_value = 0
            module.main()

            # asyncio.run should be called with the return value
            mock_asyncio.run.assert_called_once()


class TestDatabaseIntegration:
    """Test that collection actually writes to database."""

    @pytest.mark.asyncio
    async def test_writes_metrics_to_database(
        self, configured_env, initialized_db, async_context_manager_factory, mock_run_command_factory
    ):
        """Collection should write metrics to database."""
        from meshmon.db import get_latest_metrics

        module = load_collect_companion()

        responses = {
            "send_appstart": (True, "SELF_INFO", {}, None),
            "send_device_query": (True, "DEVICE_INFO", {}, None),
            "get_time": (True, "TIME", {}, None),
            "get_self_telemetry": (True, "TELEMETRY", {}, None),
            "get_custom_vars": (True, "CUSTOM_VARS", {}, None),
            "get_contacts": (True, "CONTACTS", {"c1": {}}, None),
            "get_stats_core": (
                True,
                "STATS_CORE",
                {"battery_mv": 3777, "uptime_secs": 12345},
                None,
            ),
            "get_stats_radio": (True, "STATS_RADIO", {}, None),
            "get_stats_packets": (True, "STATS_PACKETS", {"recv": 999, "sent": 888}, None),
        }

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(
                module, "run_command", side_effect=mock_run_command_factory(responses)
            ),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 0

        # Verify data was written to database
        latest = get_latest_metrics("companion")
        assert latest is not None
        assert latest["battery_mv"] == 3777
        assert latest["recv"] == 999
        assert latest["sent"] == 888

    @pytest.mark.asyncio
    async def test_writes_telemetry_to_database_when_enabled(
        self, configured_env, initialized_db, async_context_manager_factory, monkeypatch
    ):
        """Telemetry should be written to database when enabled."""
        monkeypatch.setenv("TELEMETRY_ENABLED", "1")
        import meshmon.env

        meshmon.env._config = None

        from meshmon.db import get_latest_metrics

        module = load_collect_companion()

        # LPP data format: list of dictionaries with type, channel, value
        lpp_data = [
            {"type": "temperature", "channel": 0, "value": 25.5},
        ]

        async def mock_run_command(mc, coro, name):
            if name == "get_self_telemetry":
                return (True, "TELEMETRY", {"lpp": lpp_data}, None)
            if name == "get_stats_core":
                return (True, "STATS_CORE", {"battery_mv": 3850}, None)
            return (True, "OK", {}, None)

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
        ):
            exit_code = await module.collect_companion()

        assert exit_code == 0

        # Verify telemetry was written to database
        latest = get_latest_metrics("companion")
        assert latest is not None
        assert "telemetry.temperature.0" in latest
        assert latest["telemetry.temperature.0"] == 25.5
