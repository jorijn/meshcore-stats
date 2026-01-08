"""Tests for run_command function."""

from unittest.mock import MagicMock

import pytest

from meshmon.meshcore_client import run_command

from .conftest import make_mock_event


class TestRunCommandSuccess:
    """Tests for successful command execution."""

    @pytest.mark.asyncio
    async def test_returns_success_tuple(self, mock_meshcore_client, monkeypatch):
        """Returns (True, event_type, payload, None) on success."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

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
    async def test_extracts_payload_dict(self, mock_meshcore_client, monkeypatch):
        """Extracts payload when it's a dict."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        payload_data = {"voltage": 3.85, "uptime": 86400}
        event = make_mock_event("SELF_INFO", payload_data)

        async def cmd():
            return event

        success, _, payload, _ = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert payload == payload_data

    @pytest.mark.asyncio
    async def test_converts_object_payload(self, mock_meshcore_client, monkeypatch):
        """Converts object payload to dict."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        # Create object-like payload using a simple class with instance attributes
        # vars() only returns instance attributes, not class attributes
        class ObjPayload:
            def __init__(self):
                self.voltage = 3.85

        obj_payload = ObjPayload()

        event = make_mock_event("SELF_INFO", payload=obj_payload)

        async def cmd():
            return event

        success, _, payload, _ = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert "voltage" in payload

    @pytest.mark.asyncio
    async def test_converts_namedtuple_payload(self, mock_meshcore_client, monkeypatch):
        """Converts namedtuple payload to dict."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        from collections import namedtuple
        Payload = namedtuple("Payload", ["voltage", "uptime"])
        nt_payload = Payload(voltage=3.85, uptime=86400)

        event = make_mock_event("SELF_INFO")
        event.payload = nt_payload

        async def cmd():
            return event

        success, _, payload, _ = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert payload["voltage"] == 3.85
        assert payload["uptime"] == 86400


class TestRunCommandFailure:
    """Tests for command failure scenarios."""

    @pytest.mark.asyncio
    async def test_returns_failure_when_unavailable(self, mock_meshcore_client, monkeypatch):
        """Returns failure when meshcore not available."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

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
        assert "not available" in error

    @pytest.mark.asyncio
    async def test_returns_failure_on_none_event(self, mock_meshcore_client, monkeypatch):
        """Returns failure when no event received."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        async def cmd():
            return None

        success, _, _, error = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert success is False
        assert "No response" in error

    @pytest.mark.asyncio
    async def test_returns_failure_on_error_event(self, mock_meshcore_client, monkeypatch):
        """Returns failure on ERROR event type."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        # Set up EventType mock
        mock_event_type = MagicMock()
        mock_event_type.ERROR = "ERROR"
        monkeypatch.setattr("meshmon.meshcore_client.EventType", mock_event_type)

        event = MagicMock()
        event.type = mock_event_type.ERROR
        event.payload = "Command failed"

        async def cmd():
            return event

        success, event_type, payload, error = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert success is False
        assert error is not None

    @pytest.mark.asyncio
    async def test_returns_failure_on_timeout(self, mock_meshcore_client, monkeypatch):
        """Returns failure on timeout."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        async def cmd():
            raise TimeoutError()

        success, _, _, error = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert success is False
        assert "Timeout" in error

    @pytest.mark.asyncio
    async def test_returns_failure_on_exception(self, mock_meshcore_client, monkeypatch):
        """Returns failure on general exception."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        async def cmd():
            raise RuntimeError("Connection lost")

        success, _, _, error = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert success is False
        assert "Connection lost" in error


class TestRunCommandEventTypeParsing:
    """Tests for event type name extraction."""

    @pytest.mark.asyncio
    async def test_extracts_type_name_attribute(self, mock_meshcore_client, monkeypatch):
        """Extracts event type from .type.name attribute."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        event = make_mock_event("CUSTOM_EVENT", {})

        async def cmd():
            return event

        _, event_type, _, _ = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert event_type == "CUSTOM_EVENT"

    @pytest.mark.asyncio
    async def test_falls_back_to_str_type(self, mock_meshcore_client, monkeypatch):
        """Falls back to str(type) when no .name."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)

        event = MagicMock()
        event.type = "STRING_TYPE"
        event.payload = {}

        async def cmd():
            return event

        _, event_type, _, _ = await run_command(
            mock_meshcore_client, cmd(), "test"
        )

        assert event_type == "STRING_TYPE"
