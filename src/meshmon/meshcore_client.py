"""MeshCore client wrapper with safe command execution and contact lookup."""

import asyncio
from typing import Any, Optional, Callable, Coroutine

from .env import get_config
from . import log

# Try to import meshcore - will fail gracefully if not installed
try:
    from meshcore import MeshCore, EventType
    MESHCORE_AVAILABLE = True
except ImportError:
    MESHCORE_AVAILABLE = False
    MeshCore = None
    EventType = None


def auto_detect_serial_port() -> Optional[str]:
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


async def connect_from_env() -> Optional[Any]:
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


async def run_command(
    mc: Any,
    cmd_coro: Coroutine,
    name: str,
) -> tuple[bool, Optional[str], Optional[dict], Optional[str]]:
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
            if hasattr(event.type, "name"):
                event_type_name = event.type.name
            else:
                event_type_name = str(event.type)

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

    except asyncio.TimeoutError:
        return (False, None, None, "Timeout")
    except Exception as e:
        return (False, None, None, str(e))


def get_contact_by_name(mc: Any, name: str) -> Optional[Any]:
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


def get_contact_by_key_prefix(mc: Any, prefix: str) -> Optional[Any]:
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
