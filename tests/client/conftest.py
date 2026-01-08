"""Fixtures for MeshCore client tests."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_meshcore_module():
    """Mock the entire meshcore module at import level."""
    mock_mc = MagicMock()
    mock_mc.MeshCore = MagicMock()
    mock_mc.EventType = MagicMock()
    mock_mc.EventType.ERROR = "ERROR"

    with patch.dict("sys.modules", {"meshcore": mock_mc}):
        yield mock_mc


@pytest.fixture
def mock_meshcore_client():
    """Create mock MeshCore client with AsyncMock for coroutines."""
    mc = MagicMock()
    mc.commands = MagicMock()
    mc.contacts = {}

    # Async methods
    mc.disconnect = AsyncMock()
    mc.commands.send_appstart = MagicMock(return_value=AsyncMock())
    mc.commands.get_contacts = MagicMock(return_value=AsyncMock())
    mc.commands.req_status_sync = MagicMock(return_value=AsyncMock())

    # Synchronous methods
    mc.get_contact_by_name = MagicMock(return_value=None)
    mc.get_contact_by_key_prefix = MagicMock(return_value=None)

    return mc


@pytest.fixture
def mock_serial_port():
    """Mock pyserial for serial port detection."""
    mock_serial = MagicMock()
    mock_port = MagicMock()
    mock_port.device = "/dev/ttyACM0"
    mock_port.description = "Mock MeshCore Device"
    mock_serial.tools = MagicMock()
    mock_serial.tools.list_ports = MagicMock()
    mock_serial.tools.list_ports.comports = MagicMock(return_value=[mock_port])

    with patch.dict("sys.modules", {
        "serial": mock_serial,
        "serial.tools": mock_serial.tools,
        "serial.tools.list_ports": mock_serial.tools.list_ports,
    }):
        yield mock_serial


def make_mock_event(event_type: str, payload: dict = None):
    """Helper: Create a mock MeshCore event.

    Args:
        event_type: Event type name (e.g., "SELF_INFO", "ERROR")
        payload: Event payload dict

    Returns:
        Mock event object
    """
    event = MagicMock()
    event.type = MagicMock()
    event.type.name = event_type
    event.payload = payload if payload is not None else {}
    return event


@pytest.fixture
def sample_contact():
    """Sample contact object."""
    contact = MagicMock()
    contact.adv_name = "TestNode"
    contact.name = "Test"
    contact.pubkey_prefix = "abc123"
    contact.public_key = b"\x01\x02\x03\x04"
    contact.type = 1
    contact.flags = 0
    return contact


@pytest.fixture
def sample_contact_dict():
    """Sample contact as dictionary."""
    return {
        "adv_name": "TestNode",
        "name": "Test",
        "pubkey_prefix": "abc123",
        "public_key": b"\x01\x02\x03\x04",
        "type": 1,
        "flags": 0,
    }
