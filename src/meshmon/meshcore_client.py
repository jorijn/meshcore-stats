"""MeshCore client wrapper with safe command execution and contact lookup."""

import asyncio
import fcntl
from collections.abc import AsyncIterator, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from . import log
from .env import get_config

# Try to import meshcore - will fail gracefully if not installed
try:
    from meshcore import EventType, MeshCore
    MESHCORE_AVAILABLE = True
except ImportError:
    MESHCORE_AVAILABLE = False
    MeshCore = None
    EventType = None


def auto_detect_serial_port() -> str | None:
    """
    Auto-detect a suitable serial port for MeshCore device.
    Prefers /dev/ttyACM* or /dev/ttyUSB* devices.
    """
    try:
        import serial.tools.list_ports
    except ImportError:
        log.error("pyserial not installed, cannot auto-detect serial port")
        return None

    ports = list(serial.tools.list_ports.comports())
    if not ports:
        log.error("No serial ports found")
        return None

    # Prefer ACM devices (CDC/ACM USB), then USB serial
    for port in ports:
        if "ttyACM" in port.device:
            log.info(f"Auto-detected serial port: {port.device} ({port.description})")
            return port.device

    for port in ports:
        if "ttyUSB" in port.device:
            log.info(f"Auto-detected serial port: {port.device} ({port.description})")
            return port.device

    # Fall back to first available
    port = ports[0]
    log.info(f"Using first available port: {port.device} ({port.description})")
    return port.device


async def connect_from_env() -> Any | None:
    """
    Connect to MeshCore device using environment configuration.

    Returns:
        MeshCore instance or None on failure
    """
    if not MESHCORE_AVAILABLE:
        log.error("meshcore library not available")
        return None

    cfg = get_config()
    transport = cfg.mesh_transport.lower()

    try:
        if transport == "serial":
            port = cfg.mesh_serial_port
            if not port:
                port = auto_detect_serial_port()
                if not port:
                    log.error("No serial port configured or detected")
                    return None

            log.debug(f"Connecting via serial: {port} @ {cfg.mesh_serial_baud}")
            mc = await MeshCore.create_serial(
                port, cfg.mesh_serial_baud, debug=cfg.mesh_debug
            )
            return mc

        elif transport == "tcp":
            log.debug(f"Connecting via TCP: {cfg.mesh_tcp_host}:{cfg.mesh_tcp_port}")
            mc = await MeshCore.create_tcp(cfg.mesh_tcp_host, cfg.mesh_tcp_port)
            return mc

        elif transport == "ble":
            if not cfg.mesh_ble_addr:
                log.error("MESH_BLE_ADDR required for BLE transport")
                return None
            log.debug(f"Connecting via BLE: {cfg.mesh_ble_addr}")
            mc = await MeshCore.create_ble(cfg.mesh_ble_addr, pin=cfg.mesh_ble_pin)
            return mc

        else:
            log.error(f"Unknown transport: {transport}")
            return None

    except Exception as e:
        log.error(f"Failed to connect: {e}")
        return None


async def _acquire_lock_async(
    lock_file,
    timeout: float = 60.0,
    poll_interval: float = 0.1,
) -> None:
    """Acquire exclusive file lock without blocking the event loop.

    Uses non-blocking LOCK_NB with async polling to avoid freezing the event loop.

    Args:
        lock_file: Open file handle to lock
        timeout: Maximum seconds to wait for lock
        poll_interval: Seconds between lock attempts

    Raises:
        TimeoutError: If lock cannot be acquired within timeout
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout

    while True:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return
        except BlockingIOError as err:
            if loop.time() >= deadline:
                raise TimeoutError(
                    f"Could not acquire serial lock within {timeout}s. "
                    "Another process may be using the serial port."
                ) from err
            await asyncio.sleep(poll_interval)


@asynccontextmanager
async def connect_with_lock(
    lock_timeout: float = 60.0,
) -> AsyncIterator[Any | None]:
    """Connect to MeshCore with serial port locking to prevent concurrent access.

    For serial transport: Acquires exclusive file lock before connecting.
    For TCP/BLE: No locking needed (protocol handles multiple connections).

    Args:
        lock_timeout: Maximum seconds to wait for serial lock

    Yields:
        MeshCore client instance, or None if connection failed
    """
    cfg = get_config()
    lock_file = None
    mc = None
    needs_lock = cfg.mesh_transport.lower() == "serial"

    try:
        if needs_lock:
            lock_path: Path = cfg.state_dir / "serial.lock"
            lock_path.parent.mkdir(parents=True, exist_ok=True)

            # Use 'a' mode: doesn't truncate, creates if missing
            lock_file = open(lock_path, "a")  # noqa: SIM115 - must stay open for lock
            try:
                await _acquire_lock_async(lock_file, timeout=lock_timeout)
                log.debug(f"Acquired serial lock: {lock_path}")
            except Exception:
                # If lock acquisition fails, close file before re-raising
                lock_file.close()
                lock_file = None
                raise

        mc = await connect_from_env()
        yield mc

    finally:
        # Disconnect first (while we still hold the lock)
        if mc is not None and hasattr(mc, "disconnect"):
            try:
                await mc.disconnect()
            except Exception as e:
                log.debug(f"Error during disconnect (ignored): {e}")

        # Release lock by closing the file (close() auto-releases flock)
        if lock_file is not None:
            lock_file.close()
            log.debug("Released serial lock")


async def run_command(
    mc: Any,
    cmd_coro: Coroutine,
    name: str,
) -> tuple[bool, str | None, dict | None, str | None]:
    """
    Run a MeshCore command and capture result.

    Args:
        mc: MeshCore instance
        cmd_coro: The command coroutine to execute
        name: Human-readable command name for logging

    Returns:
        (success, event_type_name, payload_dict, error_message)
    """
    if not MESHCORE_AVAILABLE:
        return (False, None, None, "meshcore not available")

    try:
        log.debug(f"Running command: {name}")
        event = await cmd_coro

        if event is None:
            return (False, None, None, "No response received")

        # Extract event type name
        event_type_name = None
        if hasattr(event, "type"):
            event_type_name = event.type.name if hasattr(event.type, "name") else str(event.type)

        # Check for error
        if EventType and hasattr(event, "type") and event.type == EventType.ERROR:
            error_msg = None
            if hasattr(event, "payload"):
                error_msg = str(event.payload)
            return (False, event_type_name, None, error_msg or "Command returned error")

        # Extract payload
        payload = None
        if hasattr(event, "payload"):
            payload = event.payload
            # Try to convert to dict if it's a custom object
            if payload is not None and not isinstance(payload, dict):
                if hasattr(payload, "__dict__"):
                    payload = vars(payload)
                elif hasattr(payload, "_asdict"):
                    payload = payload._asdict()
                else:
                    payload = {"raw": payload}

        log.debug(f"Command {name} returned: {event_type_name}")
        return (True, event_type_name, payload, None)

    except TimeoutError:
        return (False, None, None, "Timeout")
    except Exception as e:
        return (False, None, None, str(e))


def get_contact_by_name(mc: Any, name: str) -> Any | None:
    """
    Find a contact by advertised name.

    Note: This is a synchronous method on MeshCore.

    Args:
        mc: MeshCore instance
        name: The advertised name to search for

    Returns:
        Contact object or None
    """
    if not hasattr(mc, "get_contact_by_name"):
        log.warn("get_contact_by_name not available in meshcore")
        return None

    try:
        return mc.get_contact_by_name(name)
    except Exception as e:
        log.debug(f"get_contact_by_name failed: {e}")
        return None


def get_contact_by_key_prefix(mc: Any, prefix: str) -> Any | None:
    """
    Find a contact by public key prefix.

    Note: This is a synchronous method on MeshCore.

    Args:
        mc: MeshCore instance
        prefix: Hex prefix of the public key

    Returns:
        Contact object or None
    """
    if not hasattr(mc, "get_contact_by_key_prefix"):
        log.warn("get_contact_by_key_prefix not available in meshcore")
        return None

    try:
        return mc.get_contact_by_key_prefix(prefix)
    except Exception as e:
        log.debug(f"get_contact_by_key_prefix failed: {e}")
        return None


def extract_contact_info(contact: Any) -> dict[str, Any]:
    """Extract useful info from a contact object or dict."""
    info = {}

    attrs = ["adv_name", "name", "pubkey_prefix", "public_key", "type", "flags"]

    # Handle dict contacts
    if isinstance(contact, dict):
        for attr in attrs:
            if attr in contact:
                val = contact[attr]
                if val is not None:
                    if isinstance(val, bytes):
                        info[attr] = val.hex()
                    else:
                        info[attr] = val
    else:
        # Handle object contacts
        for attr in attrs:
            if hasattr(contact, attr):
                val = getattr(contact, attr)
                if val is not None:
                    if isinstance(val, bytes):
                        info[attr] = val.hex()
                    else:
                        info[attr] = val

    return info


def list_contacts_summary(contacts: list) -> list[dict[str, Any]]:
    """Get summary of all contacts for debugging."""
    result = []
    for c in contacts:
        info = extract_contact_info(c)
        result.append(info)
    return result
