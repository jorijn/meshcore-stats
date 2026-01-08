"""Tests for MESHCORE_AVAILABLE flag handling."""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestMeshcoreAvailableTrue:
    """Tests when MESHCORE_AVAILABLE is True."""

    @pytest.mark.asyncio
    async def test_run_command_executes_when_available(self, mock_meshcore_client, monkeypatch):
        """run_command executes command when meshcore available."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        from meshmon.meshcore_client import run_command

        from .conftest import make_mock_event

        event = make_mock_event("SELF_INFO", {"bat": 3850})

        async def cmd():
            return event

        success, event_type, payload, error = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert success is True
        assert event_type == "SELF_INFO"
        assert payload == {"bat": 3850}
        assert error is None

    @pytest.mark.asyncio
    async def test_connect_from_env_attempts_connection(self, monkeypatch, tmp_path):
        """connect_from_env attempts to connect when meshcore available."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        # Mock MeshCore.create_serial
        mock_mc = MagicMock()
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = AsyncMock(return_value=mock_mc)
        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        # Configure environment
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")
        monkeypatch.setenv("STATE_DIR", str(tmp_path))
        monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))

        import meshmon.env
        meshmon.env._config = None

        from meshmon.meshcore_client import connect_from_env

        result = await connect_from_env()

        assert result == mock_mc
        mock_meshcore.create_serial.assert_called_once_with("/dev/ttyACM0", 115200, debug=False)


class TestMeshcoreAvailableFalse:
    """Tests when MESHCORE_AVAILABLE is False."""

    @pytest.mark.asyncio
    async def test_run_command_returns_failure(self, mock_meshcore_client, monkeypatch):
        """run_command returns failure when meshcore not available."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        from meshmon.meshcore_client import run_command

        async def cmd():
            return None

        # Create the coroutine
        cmd_coro = cmd()

        success, event_type, payload, error = await run_command(
            mock_meshcore_client, cmd_coro, "test"
        )

        # Close the coroutine to prevent "never awaited" warning
        # since run_command returns early when MESHCORE_AVAILABLE=False
        cmd_coro.close()

        assert success is False
        assert event_type is None
        assert payload is None
        assert "not available" in error

    @pytest.mark.asyncio
    async def test_connect_from_env_returns_none(self, monkeypatch, tmp_path):
        """connect_from_env returns None when meshcore not available."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        # Configure environment
        monkeypatch.setenv("STATE_DIR", str(tmp_path))
        monkeypatch.setenv("OUT_DIR", str(tmp_path / "out"))

        import meshmon.env
        meshmon.env._config = None

        from meshmon.meshcore_client import connect_from_env

        result = await connect_from_env()

        assert result is None


class TestMeshcoreImportFallback:
    """Tests for import fallback behavior."""

    def test_meshcore_none_when_import_fails(self, monkeypatch):
        """MeshCore is None when import fails."""
        import builtins
        import importlib

        import meshmon.meshcore_client as module

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "meshcore":
                raise ImportError("No module named 'meshcore'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        module = importlib.reload(module)

        assert module.MESHCORE_AVAILABLE is False
        assert module.MeshCore is None
        assert module.EventType is None

        monkeypatch.setattr(builtins, "__import__", real_import)
        importlib.reload(module)

    @pytest.mark.asyncio
    async def test_event_type_check_handles_none(self, monkeypatch):
        """EventType checks handle None gracefully."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setattr("meshmon.meshcore_client.EventType", None)

        from meshmon.meshcore_client import run_command

        from .conftest import make_mock_event

        event = make_mock_event("SELF_INFO", {"bat": 3850})

        async def cmd():
            return event

        success, event_type, payload, error = await run_command(
            MagicMock(), cmd(), "test"
        )

        assert success is True
        assert event_type == "SELF_INFO"
        assert payload == {"bat": 3850}
        assert error is None


class TestContactFunctionsWithUnavailableMeshcore:
    """Tests that contact functions work regardless of MESHCORE_AVAILABLE."""

    def test_get_contact_by_name_works_when_unavailable(self, mock_meshcore_client, monkeypatch):
        """get_contact_by_name works even when meshcore unavailable."""
        # Contact functions don't check MESHCORE_AVAILABLE - they work with any client
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        from meshmon.meshcore_client import get_contact_by_name

        contact = MagicMock()
        contact.adv_name = "TestNode"
        mock_meshcore_client.get_contact_by_name.return_value = contact

        result = get_contact_by_name(mock_meshcore_client, "TestNode")

        assert result == contact

    def test_get_contact_by_key_prefix_works_when_unavailable(
        self, mock_meshcore_client, monkeypatch
    ):
        """get_contact_by_key_prefix works even when meshcore unavailable."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        from meshmon.meshcore_client import get_contact_by_key_prefix

        contact = MagicMock()
        contact.pubkey_prefix = "abc123"
        mock_meshcore_client.get_contact_by_key_prefix.return_value = contact

        result = get_contact_by_key_prefix(mock_meshcore_client, "abc123")

        assert result == contact

    def test_extract_contact_info_works_when_unavailable(self, monkeypatch):
        """extract_contact_info works even when meshcore unavailable."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        from meshmon.meshcore_client import extract_contact_info

        contact = {"adv_name": "TestNode", "type": 1}

        result = extract_contact_info(contact)

        assert result["adv_name"] == "TestNode"
        assert result["type"] == 1

    def test_list_contacts_summary_works_when_unavailable(self, monkeypatch):
        """list_contacts_summary works even when meshcore unavailable."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        from meshmon.meshcore_client import list_contacts_summary

        contacts = [{"adv_name": "Node1"}, {"adv_name": "Node2"}]

        result = list_contacts_summary(contacts)

        assert len(result) == 2
        assert result[0]["adv_name"] == "Node1"


class TestAutoDetectWithUnavailablePyserial:
    """Tests for auto_detect_serial_port when pyserial unavailable."""

    def test_returns_none_when_pyserial_not_installed(self, monkeypatch):
        """Returns None when pyserial not installed."""
        # Mock the import to fail
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "serial.tools.list_ports" or name == "serial":
                raise ImportError("No module named 'serial'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)

        from meshmon.meshcore_client import auto_detect_serial_port

        result = auto_detect_serial_port()

        assert result is None
