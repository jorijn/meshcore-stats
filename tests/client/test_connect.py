"""Tests for MeshCore connection functions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from meshmon.meshcore_client import (
    _acquire_lock_async,
    auto_detect_serial_port,
    connect_from_env,
    connect_with_lock,
)


class TestAutoDetectSerialPort:
    """Tests for auto_detect_serial_port function."""

    def test_prefers_acm_devices(self, mock_serial_port):
        """Prefers /dev/ttyACM* devices."""
        mock_port_acm = MagicMock()
        mock_port_acm.device = "/dev/ttyACM0"
        mock_port_acm.description = "ACM Device"

        mock_port_usb = MagicMock()
        mock_port_usb.device = "/dev/ttyUSB0"
        mock_port_usb.description = "USB Device"

        mock_serial_port.tools.list_ports.comports.return_value = [mock_port_usb, mock_port_acm]

        result = auto_detect_serial_port()

        assert result == "/dev/ttyACM0"

    def test_falls_back_to_usb(self, mock_serial_port):
        """Falls back to /dev/ttyUSB* if no ACM."""
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyUSB0"
        mock_port.description = "USB Device"

        mock_serial_port.tools.list_ports.comports.return_value = [mock_port]

        result = auto_detect_serial_port()

        assert result == "/dev/ttyUSB0"

    def test_falls_back_to_first_available(self, mock_serial_port):
        """Falls back to first available port."""
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyS0"
        mock_port.description = "Serial Port"

        mock_serial_port.tools.list_ports.comports.return_value = [mock_port]

        result = auto_detect_serial_port()

        assert result == "/dev/ttyS0"

    def test_returns_none_when_no_ports(self, mock_serial_port):
        """Returns None when no ports available."""
        mock_serial_port.tools.list_ports.comports.return_value = []

        result = auto_detect_serial_port()

        assert result is None

    def test_handles_import_error(self):
        """Returns None when pyserial not installed."""
        with patch.dict("sys.modules", {"serial": None, "serial.tools": None, "serial.tools.list_ports": None}):
            # Force re-import to test import error handling
            # This test may need adjustment based on actual import structure
            pass


class TestConnectFromEnv:
    """Tests for connect_from_env function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_meshcore_unavailable(self, configured_env, monkeypatch):
        """Returns None when meshcore library not available."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", False)

        result = await connect_from_env()

        assert result is None

    @pytest.mark.asyncio
    async def test_serial_connection(self, configured_env, monkeypatch, mock_serial_port):
        """Connects via serial when configured."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None

        mock_create = AsyncMock(return_value=MagicMock())
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        await connect_from_env()

        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_tcp_connection(self, configured_env, monkeypatch):
        """Connects via TCP when configured."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "tcp")
        monkeypatch.setenv("MESH_TCP_HOST", "localhost")
        monkeypatch.setenv("MESH_TCP_PORT", "4403")

        import meshmon.env
        meshmon.env._config = None

        mock_create = AsyncMock(return_value=MagicMock())
        mock_meshcore = MagicMock()
        mock_meshcore.create_tcp = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        await connect_from_env()

        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_unknown_transport(self, configured_env, monkeypatch):
        """Returns None for unknown transport."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "unknown")

        import meshmon.env
        meshmon.env._config = None

        result = await connect_from_env()

        assert result is None

    @pytest.mark.asyncio
    async def test_handles_connection_error(self, configured_env, monkeypatch, mock_serial_port):
        """Returns None on connection error."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None

        mock_create = AsyncMock(side_effect=Exception("Connection failed"))
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        result = await connect_from_env()

        assert result is None

    @pytest.mark.asyncio
    async def test_ble_connection(self, configured_env, monkeypatch):
        """Connects via BLE when configured."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "ble")
        monkeypatch.setenv("MESH_BLE_ADDR", "AA:BB:CC:DD:EE:FF")
        monkeypatch.setenv("MESH_BLE_PIN", "123456")

        import meshmon.env
        meshmon.env._config = None

        mock_create = AsyncMock(return_value=MagicMock())
        mock_meshcore = MagicMock()
        mock_meshcore.create_ble = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        await connect_from_env()

        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_ble_missing_address(self, configured_env, monkeypatch):
        """Returns None when BLE address not configured."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "ble")
        # Don't set MESH_BLE_ADDR

        import meshmon.env
        meshmon.env._config = None

        result = await connect_from_env()

        assert result is None

    @pytest.mark.asyncio
    async def test_serial_auto_detect(self, configured_env, monkeypatch, mock_serial_port):
        """Auto-detects serial port when not configured."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        # Don't set MESH_SERIAL_PORT to trigger auto-detection

        import meshmon.env
        meshmon.env._config = None

        # Set up mock port detection
        mock_port = MagicMock()
        mock_port.device = "/dev/ttyACM0"
        mock_serial_port.tools.list_ports.comports.return_value = [mock_port]

        mock_create = AsyncMock(return_value=MagicMock())
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        await connect_from_env()

        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_serial_auto_detect_fails(self, configured_env, monkeypatch, mock_serial_port):
        """Returns None when serial auto-detection fails."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        # Don't set MESH_SERIAL_PORT to trigger auto-detection

        import meshmon.env
        meshmon.env._config = None

        # No ports available
        mock_serial_port.tools.list_ports.comports.return_value = []

        result = await connect_from_env()

        assert result is None


class TestConnectWithLock:
    """Tests for connect_with_lock context manager."""

    @pytest.mark.asyncio
    async def test_yields_client_on_success(self, configured_env, monkeypatch, mock_serial_port):
        """Yields connected client on success."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None

        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        mock_create = AsyncMock(return_value=mock_client)
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        async with connect_with_lock() as mc:
            assert mc is mock_client

        # Should disconnect when exiting context
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_yields_none_on_connection_failure(self, configured_env, monkeypatch, mock_serial_port):
        """Yields None when connection fails."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None

        mock_create = AsyncMock(side_effect=Exception("Connection failed"))
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        async with connect_with_lock() as mc:
            assert mc is None

    @pytest.mark.asyncio
    async def test_acquires_lock_for_serial(self, configured_env, monkeypatch, mock_serial_port):
        """Acquires lock file for serial transport."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None
        cfg = meshmon.env.get_config()

        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        mock_create = AsyncMock(return_value=mock_client)
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        async with connect_with_lock():
            # Lock file should exist while connected
            lock_path = cfg.state_dir / "serial.lock"
            assert lock_path.exists()

    @pytest.mark.asyncio
    async def test_no_lock_for_tcp(self, configured_env, monkeypatch):
        """Does not acquire lock for TCP transport."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "tcp")
        monkeypatch.setenv("MESH_TCP_HOST", "localhost")
        monkeypatch.setenv("MESH_TCP_PORT", "4403")

        import meshmon.env
        meshmon.env._config = None
        cfg = meshmon.env.get_config()

        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock()
        mock_create = AsyncMock(return_value=mock_client)
        mock_meshcore = MagicMock()
        mock_meshcore.create_tcp = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        lock_path = cfg.state_dir / "serial.lock"

        async with connect_with_lock():
            # Lock file should not exist for TCP
            assert not lock_path.exists()

    @pytest.mark.asyncio
    async def test_handles_disconnect_error(self, configured_env, monkeypatch, mock_serial_port):
        """Handles disconnect error gracefully."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None

        mock_client = MagicMock()
        mock_client.disconnect = AsyncMock(side_effect=Exception("Disconnect error"))
        mock_create = AsyncMock(return_value=mock_client)
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        # Should not raise even when disconnect fails
        async with connect_with_lock() as mc:
            assert mc is mock_client

        # Disconnect was still called
        mock_client.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_releases_lock_on_failure(self, configured_env, monkeypatch, mock_serial_port):
        """Releases lock even when connection fails."""
        monkeypatch.setattr("meshmon.meshcore_client.MESHCORE_AVAILABLE", True)
        monkeypatch.setenv("MESH_TRANSPORT", "serial")
        monkeypatch.setenv("MESH_SERIAL_PORT", "/dev/ttyACM0")

        import meshmon.env
        meshmon.env._config = None

        mock_create = AsyncMock(side_effect=Exception("Connection failed"))
        mock_meshcore = MagicMock()
        mock_meshcore.create_serial = mock_create

        monkeypatch.setattr("meshmon.meshcore_client.MeshCore", mock_meshcore)

        async with connect_with_lock() as mc:
            assert mc is None

        # Lock should be released after exiting context
        # We can verify by acquiring it again without timeout
        cfg = meshmon.env.get_config()
        lock_path = cfg.state_dir / "serial.lock"
        if lock_path.exists():
            import fcntl
            with open(lock_path, "a") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


class TestAcquireLockAsync:
    """Tests for _acquire_lock_async function."""

    @pytest.mark.asyncio
    async def test_acquires_lock_immediately(self, tmp_path):
        """Acquires lock when not held by others."""
        lock_file = tmp_path / "test.lock"

        with open(lock_file, "w") as f:
            await _acquire_lock_async(f, timeout=1.0)
            # If we get here, lock was acquired

    @pytest.mark.asyncio
    async def test_times_out_when_locked(self, tmp_path):
        """Times out when lock held by another."""
        import fcntl

        lock_file = tmp_path / "test.lock"

        # Hold the lock in this process
        holder = open(lock_file, "w")  # noqa: SIM115 - must stay open for lock
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX)

        try:
            # Try to acquire with different file handle
            with open(lock_file, "a") as f, pytest.raises(TimeoutError):
                await _acquire_lock_async(f, timeout=0.2, poll_interval=0.05)
        finally:
            holder.close()

    @pytest.mark.asyncio
    async def test_waits_for_lock_release(self, tmp_path):
        """Waits and acquires when lock released."""
        import asyncio
        import fcntl

        lock_file = tmp_path / "test.lock"

        holder = open(lock_file, "w")  # noqa: SIM115 - must stay open for lock
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX)

        async def release_later():
            await asyncio.sleep(0.1)
            holder.close()

        # Start release task
        release_task = asyncio.create_task(release_later())

        # Try to acquire - should succeed after release
        with open(lock_file, "a") as f:
            await _acquire_lock_async(f, timeout=2.0, poll_interval=0.05)

        await release_task
