# MeshCore Firmware Response Reference

This document captures the actual response structures from MeshCore firmware commands.
Use this as a reference when updating collectors or adding new metrics.

> **Last verified**: 2025-12-29

---

## Companion Node

The companion node is queried via USB serial using multiple commands.

### `get_stats_core()`

Core system statistics.

```python
{
    'battery_mv': 3895,      # Battery voltage in millivolts
    'uptime_secs': 126,      # Uptime in seconds
    'errors': 0,             # Error count
    'queue_len': 0           # Message queue length
}
```

### `get_stats_packets()`

Packet counters (cumulative since boot).

```python
{
    'recv': 20,              # Total packets received
    'sent': 0,               # Total packets sent
    'flood_tx': 0,           # Flood packets transmitted
    'direct_tx': 0,          # Direct packets transmitted
    'flood_rx': 20,          # Flood packets received
    'direct_rx': 0           # Direct packets received
}
```

### `get_stats_radio()`

Radio/RF statistics.

```python
{
    'noise_floor': -113,     # Noise floor in dBm
    'last_rssi': -123,       # RSSI of last received packet (dBm)
    'last_snr': -8.5,        # SNR of last received packet (dB)
    'tx_air_secs': 0,        # Cumulative TX airtime in seconds
    'rx_air_secs': 11        # Cumulative RX airtime in seconds
}
```

### `get_bat()`

Battery/storage info (note: not the main battery source for metrics).

```python
{
    'level': 4436,           # Battery level (unclear unit)
    'used_kb': 256,          # Used storage in KB
    'total_kb': 1404         # Total storage in KB
}
```

### `get_contacts()`

Returns a dict keyed by public key. Count via `len(payload)`.

---

## Repeater Node

The repeater is queried over LoRa using the binary protocol command `req_status_sync()`.

### `req_status_sync(contact)`

Returns a single dict with all status fields.

```python
{
    'bat': 4047,             # Battery voltage in millivolts
    'uptime': 1441998,       # Uptime in seconds
    'last_rssi': -63,        # RSSI of last received packet (dBm)
    'last_snr': 12.5,        # SNR of last received packet (dB)
    'noise_floor': -118,     # Noise floor in dBm
    'tx_queue_len': 0,       # TX queue depth
    'nb_recv': 221311,       # Total packets received (counter)
    'nb_sent': 93993,        # Total packets sent (counter)
    'airtime': 64461,        # TX airtime in seconds (counter)
    'rx_airtime': 146626,    # RX airtime in seconds (counter)
    'flood_dups': 59799,     # Duplicate flood packets (counter)
    'direct_dups': 8,        # Duplicate direct packets (counter)
    'sent_flood': 92207,     # Flood packets transmitted (counter)
    'recv_flood': 216960,    # Flood packets received (counter)
    'sent_direct': 1786,     # Direct packets transmitted (counter)
    'recv_direct': 4328      # Direct packets received (counter)
}
```

---

## Telemetry Data

Environmental telemetry is requested via `req_telemetry_sync(contact)` and returns
Cayenne LPP formatted sensor data. This requires `TELEMETRY_ENABLED=1` and a sensor
board attached to the repeater.

### Payload Format

Both `req_telemetry_sync()` and `get_self_telemetry()` return a dict containing the
LPP data list and a public key prefix:

```python
{
    'pubkey_pre': 'a5c14f5244d6',
    'lpp': [
        {'channel': 0, 'type': 'temperature', 'value': 23.5},
        {'channel': 0, 'type': 'humidity', 'value': 45.2},
    ]
}
```

The `extract_lpp_from_payload()` helper in `src/meshmon/telemetry.py` handles
extracting the `lpp` list from this wrapper format.

### `req_telemetry_sync(contact)`

Returns sensor readings from a remote node in Cayenne LPP format:

```python
[
    {'channel': 0, 'type': 'temperature', 'value': 23.5},
    {'channel': 0, 'type': 'humidity', 'value': 45.2},
    {'channel': 0, 'type': 'barometer', 'value': 1013.25},
    {'channel': 1, 'type': 'gps', 'value': {'latitude': 51.5, 'longitude': -0.1, 'altitude': 10}},
]
```

**Common sensor types:**

| Type | Unit | Description |
|------|------|-------------|
| `temperature` | Celsius | Temperature reading |
| `humidity` | % | Relative humidity |
| `barometer` | hPa/mbar | Barometric pressure |
| `voltage` | V | Voltage reading |
| `gps` | compound | GPS with `latitude`, `longitude`, `altitude` |

**Stored as:**
- `telemetry.temperature.0` - Temperature on channel 0
- `telemetry.humidity.0` - Humidity on channel 0
- `telemetry.gps.1.latitude` - GPS latitude on channel 1

**Notes:**
- Requires environmental sensor board (BME280, BME680, etc.) on repeater
- Channel number distinguishes multiple sensors of the same type
- Not all repeaters have environmental sensors attached
- Telemetry collection does not affect circuit breaker state
- Telemetry failures are logged as warnings and do not block status collection

### `get_self_telemetry()`

Returns self telemetry from the companion node's attached sensors.
Same Cayenne LPP format as `req_telemetry_sync()`.

```python
[
    {'channel': 0, 'type': 'temperature', 'value': 23.5},
    {'channel': 0, 'type': 'humidity', 'value': 45.2},
]
```

**Notes:**
- Requires environmental sensor board attached to companion
- Returns empty list if no sensors attached
- Uses same format as repeater telemetry

---

## Derived Metrics

These are computed at query time, not stored:

| Metric | Source | Computation |
|--------|--------|-------------|
| `bat_pct` | `bat` or `battery_mv` | `voltage_to_percentage(mv / 1000)` using 18650 Li-ion discharge curve |

---

## Notes

- **Counters** reset to 0 on device reboot
- **Millivolts to volts**: Divide by 1000 (e.g., `bat: 4047` → `4.047V`)
- Repeater fields come from a single `req_status_sync()` call
- Companion fields are spread across multiple `get_stats_*()` calls
