"""Tests for collect_repeater.py script entry point.

These tests verify the actual script behavior, including:
- Finding repeater contact by name or key prefix
- Circuit breaker integration
- Exit codes for monitoring
- Database writes
"""

import inspect
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.scripts.conftest import load_script_module


def load_collect_repeater():
    """Load collect_repeater.py as a module."""
    return load_script_module("collect_repeater.py")


class TestCollectRepeaterImport:
    """Verify script can be imported without errors."""

    def test_imports_successfully(self, configured_env):
        """Script should import without errors."""
        module = load_collect_repeater()

        assert hasattr(module, "main")
        assert hasattr(module, "collect_repeater")
        assert hasattr(module, "find_repeater_contact")
        assert hasattr(module, "query_repeater_with_retry")
        assert callable(module.main)

    def test_collect_repeater_is_async(self, configured_env):
        """collect_repeater() should be an async function."""
        module = load_collect_repeater()
        assert inspect.iscoroutinefunction(module.collect_repeater)

    def test_find_repeater_contact_is_async(self, configured_env):
        """find_repeater_contact() should be an async function."""
        module = load_collect_repeater()
        assert inspect.iscoroutinefunction(module.find_repeater_contact)


class TestFindRepeaterContact:
    """Test the find_repeater_contact function."""

    @pytest.mark.asyncio
    async def test_finds_contact_by_name(self, configured_env, monkeypatch):
        """Should find repeater by advertised name."""
        monkeypatch.setenv("REPEATER_NAME", "MyRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        mc.contacts = {"abc123": {"adv_name": "MyRepeater", "public_key": "abc123"}}

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name") as mock_get,
        ):
            mock_run.return_value = (True, "CONTACTS", mc.contacts, None)
            mock_get.return_value = mc.contacts["abc123"]

            contact = await module.find_repeater_contact(mc)

            assert contact is not None
            assert contact["adv_name"] == "MyRepeater"
            mock_get.assert_called_once_with(mc, "MyRepeater")

    @pytest.mark.asyncio
    async def test_finds_contact_by_key_prefix(self, configured_env, monkeypatch):
        """Should find repeater by public key prefix when name not set."""
        monkeypatch.setenv("REPEATER_KEY_PREFIX", "abc123")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        mc.contacts = {"abc123def456": {"adv_name": "SomeNode", "public_key": "abc123def456"}}

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
            patch.object(module, "get_contact_by_key_prefix") as mock_get,
        ):
            mock_run.return_value = (True, "CONTACTS", mc.contacts, None)
            mock_get.return_value = mc.contacts["abc123def456"]

            contact = await module.find_repeater_contact(mc)

            assert contact is not None
            assert contact["public_key"] == "abc123def456"
            mock_get.assert_called_once()

    @pytest.mark.asyncio
    async def test_fallback_to_manual_name_search(self, configured_env, monkeypatch):
        """Should fallback to manual name search in payload dict."""
        monkeypatch.setenv("REPEATER_NAME", "ManualFind")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        contacts_dict = {"xyz789": {"adv_name": "ManualFind", "public_key": "xyz789"}}

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
        ):
            mock_run.return_value = (True, "CONTACTS", contacts_dict, None)
            # get_contact_by_name returns None, forcing manual search
            contact = await module.find_repeater_contact(mc)

            assert contact is not None
            assert contact["adv_name"] == "ManualFind"

    @pytest.mark.asyncio
    async def test_case_insensitive_name_match(self, configured_env, monkeypatch):
        """Name search should be case-insensitive."""
        monkeypatch.setenv("REPEATER_NAME", "myrepeater")  # lowercase
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        contacts_dict = {"key1": {"adv_name": "MyRepeater", "public_key": "key1"}}  # Mixed case

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
        ):
            mock_run.return_value = (True, "CONTACTS", contacts_dict, None)
            contact = await module.find_repeater_contact(mc)

            assert contact is not None
            assert contact["adv_name"] == "MyRepeater"

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self, configured_env, monkeypatch):
        """Should return None when repeater not in contacts."""
        monkeypatch.setenv("REPEATER_NAME", "NonExistent")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
        ):
            mock_run.return_value = (True, "CONTACTS", {}, None)
            contact = await module.find_repeater_contact(mc)

            assert contact is None

    @pytest.mark.asyncio
    async def test_returns_none_when_get_contacts_fails(self, configured_env, monkeypatch):
        """Should return None when get_contacts command fails."""
        monkeypatch.setenv("REPEATER_NAME", "AnyName")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()

        with patch.object(module, "run_command") as mock_run:
            mock_run.return_value = (False, None, None, "Connection failed")

            contact = await module.find_repeater_contact(mc)

            assert contact is None


class TestCircuitBreakerIntegration:
    """Test circuit breaker integration in collect_repeater."""

    @pytest.mark.asyncio
    async def test_skips_collection_when_circuit_open(self, configured_env):
        """Should return 0 and skip collection when circuit breaker is open."""
        module = load_collect_repeater()

        # Create mock circuit breaker that is open
        mock_cb = MagicMock()
        mock_cb.is_open.return_value = True
        mock_cb.cooldown_remaining.return_value = 1800

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock") as mock_connect,
        ):
            exit_code = await module.collect_repeater()

            # Should return 0 (not an error, just skipped)
            assert exit_code == 0
            # Should not have tried to connect
            mock_cb.is_open.assert_called_once()
            mock_connect.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_success_on_successful_status(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should record success when status query succeeds."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(module, "insert_metrics", return_value=2),
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (True, {"bat": 3850, "uptime": 86400}, None)

            await module.collect_repeater()

            mock_cb.record_success.assert_called_once()
            mock_cb.record_failure.assert_not_called()

    @pytest.mark.asyncio
    async def test_records_failure_on_status_timeout(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should record failure when status query times out."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "query_repeater_with_retry") as mock_query,
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (False, None, "Timeout")

            exit_code = await module.collect_repeater()

            mock_cb.record_failure.assert_called_once()
            mock_cb.record_success.assert_not_called()
            assert exit_code == 1


class TestCollectRepeaterExitCodes:
    """Test exit code behavior - critical for monitoring."""

    @pytest.mark.asyncio
    async def test_returns_zero_on_successful_collection(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Successful collection should return exit code 0."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(module, "insert_metrics") as mock_insert,
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (
                True,
                {"bat": 3850, "uptime": 86400, "nb_recv": 100},
                None,
            )

            exit_code = await module.collect_repeater()

        assert exit_code == 0
        mock_insert.assert_called_once()
        insert_kwargs = mock_insert.call_args.kwargs
        assert insert_kwargs["role"] == "repeater"
        assert insert_kwargs["metrics"]["bat"] == 3850
        assert insert_kwargs["metrics"]["nb_recv"] == 100

    @pytest.mark.asyncio
    async def test_returns_one_on_connection_failure(
        self, configured_env, async_context_manager_factory
    ):
        """Failed connection should return exit code 1."""
        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False
        ctx_mock = async_context_manager_factory(None)  # Connection returns None

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
        ):
            exit_code = await module.collect_repeater()

        assert exit_code == 1

    @pytest.mark.asyncio
    async def test_returns_one_when_repeater_not_found(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should return 1 when repeater contact not found."""
        monkeypatch.setenv("REPEATER_NAME", "NonExistent")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = None  # Not found

            exit_code = await module.collect_repeater()

        assert exit_code == 1


class TestQueryRepeaterWithRetry:
    """Test the retry wrapper for repeater queries."""

    @pytest.mark.asyncio
    async def test_returns_success_on_first_try(self, configured_env):
        """Should return success when command succeeds immediately."""
        module = load_collect_repeater()

        mc = MagicMock()
        contact = {"adv_name": "Test"}

        async def successful_command():
            return {"bat": 3850}

        with patch.object(module, "with_retries") as mock_retries:
            mock_retries.return_value = (True, {"bat": 3850}, None)

            success, payload, err = await module.query_repeater_with_retry(
                mc, contact, "test_cmd", successful_command
            )

            assert success is True
            assert payload == {"bat": 3850}
            assert err is None

    @pytest.mark.asyncio
    async def test_returns_failure_after_retries_exhausted(self, configured_env):
        """Should return failure when all retries fail."""
        module = load_collect_repeater()

        mc = MagicMock()
        contact = {"adv_name": "Test"}

        async def failing_command():
            raise Exception("Timeout")

        with patch.object(module, "with_retries") as mock_retries:
            mock_retries.return_value = (False, None, Exception("Timeout"))

            success, payload, err = await module.query_repeater_with_retry(
                mc, contact, "test_cmd", failing_command
            )

            assert success is False
            assert payload is None
            assert "Timeout" in err


class TestMainEntryPoint:
    """Test the main() entry point behavior."""

    def test_main_calls_init_db(self, configured_env):
        """main() should initialize database before collection."""
        module = load_collect_repeater()

        with (
            patch.object(module, "init_db") as mock_init,
            patch.object(module, "collect_repeater", new=MagicMock(return_value=0)),
            patch.object(module, "asyncio") as mock_asyncio,
            patch.object(module, "sys"),
        ):
            # Patch collect_repeater to return a non-coroutine to avoid unawaited coroutine warning
            mock_asyncio.run.return_value = 0
            module.main()

            mock_init.assert_called_once()

    def test_main_exits_with_collection_result(self, configured_env):
        """main() should exit with the collection exit code."""
        module = load_collect_repeater()

        with (
            patch.object(module, "init_db"),
            patch.object(module, "collect_repeater", new=MagicMock(return_value=1)),
            patch.object(module, "asyncio") as mock_asyncio,
            patch.object(module, "sys") as mock_sys,
        ):
            # Patch collect_repeater to return a non-coroutine to avoid unawaited coroutine warning
            mock_asyncio.run.return_value = 1  # Collection failed
            module.main()

            mock_sys.exit.assert_called_once_with(1)


class TestDatabaseIntegration:
    """Test that collection actually writes to database."""

    @pytest.mark.asyncio
    async def test_writes_metrics_to_database(
        self, configured_env, initialized_db, monkeypatch, async_context_manager_factory
    ):
        """Collection should write metrics to database."""
        from meshmon.db import get_latest_metrics

        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "query_repeater_with_retry") as mock_query,
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (
                True,
                {"bat": 3777, "uptime": 99999, "nb_recv": 1234, "nb_sent": 567},
                None,
            )

            exit_code = await module.collect_repeater()

        assert exit_code == 0

        # Verify data was written to database
        latest = get_latest_metrics("repeater")
        assert latest is not None
        assert latest["bat"] == 3777
        assert latest["nb_recv"] == 1234


class TestFindRepeaterContactEdgeCases:
    """Test edge cases in find_repeater_contact."""

    @pytest.mark.asyncio
    async def test_finds_contact_in_payload_dict(self, configured_env, monkeypatch):
        """Should find contact in payload dict when mc.contacts is empty."""
        monkeypatch.setenv("REPEATER_NAME", "PayloadRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        mc.contacts = {}  # Empty contacts attribute
        payload_dict = {"pk123": {"adv_name": "PayloadRepeater", "public_key": "pk123"}}

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
        ):
            # Return contacts in payload
            mock_run.return_value = (True, "CONTACTS", payload_dict, None)
            # get_contact_by_name returns None, forcing manual search in payload
            contact = await module.find_repeater_contact(mc)

            assert contact is not None
            assert contact["adv_name"] == "PayloadRepeater"

    @pytest.mark.asyncio
    async def test_finds_contact_by_key_prefix_manual_search(self, configured_env, monkeypatch):
        """Should find contact by key prefix via manual search in payload."""
        monkeypatch.setenv("REPEATER_KEY_PREFIX", "abc")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        contacts_dict = {"abc123xyz": {"adv_name": "KeyPrefixNode"}}

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
            patch.object(module, "get_contact_by_key_prefix", return_value=None),
        ):
            mock_run.return_value = (True, "CONTACTS", contacts_dict, None)
            # Both helper functions return None, forcing manual search
            contact = await module.find_repeater_contact(mc)

            assert contact is not None
            assert contact["adv_name"] == "KeyPrefixNode"

    @pytest.mark.asyncio
    async def test_prints_available_contacts_when_not_found(self, configured_env, monkeypatch):
        """Should print available contacts when repeater not found."""
        monkeypatch.setenv("REPEATER_NAME", "NonExistent")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mc = MagicMock()
        mc.commands = MagicMock()
        contacts_dict = {
            "key1": {"adv_name": "Node1", "name": "alt1"},
            "key2": {"adv_name": "Node2"},
            "key3": {},  # No name fields
        }

        with (
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "get_contact_by_name", return_value=None),
            patch.object(module, "log") as mock_log,
        ):
            mock_run.return_value = (True, "CONTACTS", contacts_dict, None)
            contact = await module.find_repeater_contact(mc)

            assert contact is None
            # Should have logged available contacts
            mock_log.info.assert_called()


class TestLoginFunctionality:
    """Test optional login functionality."""

    @pytest.mark.asyncio
    async def test_attempts_login_when_password_set(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should attempt login when REPEATER_PASSWORD is set."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        monkeypatch.setenv("REPEATER_PASSWORD", "secret123")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        mc.commands.send_login = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "extract_contact_info") as mock_extract,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(module, "insert_metrics", return_value=1),
        ):
            # Return success for all commands
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_extract.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (True, {"bat": 3850}, None)

            await module.collect_repeater()

            # Verify login was attempted (run_command called with send_login)
            login_calls = [c for c in mock_run.call_args_list if c[0][2] == "send_login"]
            assert len(login_calls) == 1

    @pytest.mark.asyncio
    async def test_handles_login_exception(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should handle exception during login gracefully."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        monkeypatch.setenv("REPEATER_PASSWORD", "secret123")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        mc.commands.send_login = MagicMock(side_effect=Exception("Login not supported"))
        ctx_mock = async_context_manager_factory(mc)

        call_count = 0

        async def mock_run_command(mc, coro, name):
            nonlocal call_count
            call_count += 1
            if name == "send_login":
                raise Exception("Login not supported")
            return (True, "OK", {}, None)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command", side_effect=mock_run_command),
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "extract_contact_info") as mock_extract,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(module, "insert_metrics", return_value=1),
        ):
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_extract.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (True, {"bat": 3850}, None)

            # Should not raise - login failure should be handled
            exit_code = await module.collect_repeater()
            assert exit_code == 0


class TestTelemetryCollection:
    """Test telemetry collection when enabled."""

    @pytest.mark.asyncio
    async def test_collects_telemetry_when_enabled(
        self, configured_env, monkeypatch, initialized_db, async_context_manager_factory
    ):
        """Should collect telemetry when TELEMETRY_ENABLED=1."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        monkeypatch.setenv("TELEMETRY_ENABLED", "1")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "extract_contact_info") as mock_extract,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(
                module,
                "with_retries",
                new=AsyncMock(return_value=(True, {"lpp": b"\x00\x67\x01\x00"}, None)),
            ),
            patch.object(module, "extract_lpp_from_payload") as mock_lpp,
            patch.object(module, "extract_telemetry_metrics") as mock_telem,
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_extract.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (True, {"bat": 3850}, None)
            mock_lpp.return_value = {"temperature": [(0, 25.5)]}
            mock_telem.return_value = {"telemetry.temperature.0": 25.5}

            exit_code = await module.collect_repeater()

            assert exit_code == 0
            # Verify telemetry was processed
            mock_lpp.assert_called_once()
            mock_telem.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_telemetry_failure_gracefully(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should continue when telemetry collection fails."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        monkeypatch.setenv("TELEMETRY_ENABLED", "1")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "extract_contact_info") as mock_extract,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(module, "insert_metrics", return_value=1),
            patch.object(
                module,
                "with_retries",
                new=AsyncMock(return_value=(False, None, Exception("Timeout"))),
            ),
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_extract.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (True, {"bat": 3850}, None)

            # Should still succeed (status metrics were saved)
            exit_code = await module.collect_repeater()
            assert exit_code == 0


class TestDatabaseErrorHandling:
    """Test database error handling."""

    @pytest.mark.asyncio
    async def test_returns_one_on_status_db_error(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should return 1 when status metrics DB write fails."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "extract_contact_info") as mock_extract,
            patch.object(module, "query_repeater_with_retry") as mock_query,
            patch.object(module, "insert_metrics", side_effect=Exception("DB error")),
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_extract.return_value = {"adv_name": "TestRepeater"}
            mock_query.return_value = (True, {"bat": 3850}, None)

            exit_code = await module.collect_repeater()
            assert exit_code == 1


class TestExceptionHandling:
    """Test general exception handling."""

    @pytest.mark.asyncio
    async def test_records_failure_on_exception(
        self, configured_env, monkeypatch, async_context_manager_factory
    ):
        """Should record circuit breaker failure on unexpected exception."""
        monkeypatch.setenv("REPEATER_NAME", "TestRepeater")
        import meshmon.env

        meshmon.env._config = None

        module = load_collect_repeater()

        mock_cb = MagicMock()
        mock_cb.is_open.return_value = False

        mc = MagicMock()
        mc.commands = MagicMock()
        ctx_mock = async_context_manager_factory(mc)

        with (
            patch.object(module, "get_repeater_circuit_breaker", return_value=mock_cb),
            patch.object(module, "connect_with_lock", return_value=ctx_mock),
            patch.object(module, "run_command") as mock_run,
            patch.object(module, "find_repeater_contact") as mock_find,
            patch.object(module, "extract_contact_info") as mock_extract,
        ):
            mock_run.return_value = (True, "OK", {}, None)
            mock_find.return_value = {"adv_name": "TestRepeater"}
            mock_extract.side_effect = Exception("Unexpected error")

            await module.collect_repeater()

            # Circuit breaker should record failure
            mock_cb.record_failure.assert_called_once()
