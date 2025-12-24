# Battery Voltage Data Sources: Analysis and Recommendations

## Background

The MeshCore repeater exposes battery voltage through two different data paths in the status response:

1. **`status.bat`** - An integer value in millivolts from the main status object
2. **`telemetry[].value`** - A decimal value in volts from the telemetry array (where `type="voltage"`)

This document analyzes which source is more reliable for monitoring battery health and why the values differ.

## Why This Matters

Accurate battery monitoring is critical for a solar-powered remote repeater:

- **Predict downtime**: Understanding the true discharge curve helps predict when the repeater might go offline
- **Chart clarity**: Noisy data obscures the actual battery trend, making it harder to spot problems
- **Alerting accuracy**: False fluctuations could trigger spurious low-battery alerts
- **Data integrity**: Choosing the wrong source could lead to misleading historical analysis

## Analysis Methodology

We analyzed 169 repeater snapshots collected over 3 days (December 22-24, 2025) at 15-minute intervals. Both battery sources were extracted and compared statistically.

## Key Findings

### 1. `status.bat` is More Stable

| Metric | status.bat | telemetry.value | Difference |
|--------|-----------|-----------------|------------|
| Standard Deviation | 0.0088V | 0.0118V | 37% higher variance in telemetry |
| Range (min to max) | 0.046V | 0.070V | 52% wider range in telemetry |
| Coefficient of Variation | 0.217% | 0.295% | 36% more variable |

**Conclusion**: The telemetry source is approximately 1.4x more volatile than the status source.

### 2. Systematic Offset Between Sources

The two sources don't report the same voltage:

| Statistic | Value |
|-----------|-------|
| Mean Difference | +0.029V (status reads higher) |
| Range of Differences | -0.012V to +0.055V |

The `status.bat` value consistently reads approximately 29mV higher than `telemetry.value`. This suggests they measure from different points in the circuit or have different calibration offsets.

### 3. Resolution Differences

Despite their formats, the effective resolution differs:

- **`status.bat`** (integer millivolts): ~1mV increments
  - Example values: 4016, 4018, 4020, 4023, 4025...

- **`telemetry.value`** (decimal volts): ~10mV increments
  - Example values: 3.97, 3.98, 3.99, 4.00, 4.01, 4.02...

The telemetry source has coarser effective resolution (10mV steps) despite being stored as a decimal.

### 4. Telemetry Has Unexplained Spikes

The telemetry source shows occasional voltage drops that don't appear in the status source:

| When telemetry reads LOW (≤ 3.98V) | status.bat value |
|------------------------------------|------------------|
| 5 instances on Dec 24 | Remained stable at 4.023-4.027V |
| Largest divergence | +0.055V difference |

These uncorrelated spikes suggest measurement artifacts in the telemetry channel.

### 5. No Correlation with Radio Activity

Both sources show weak negative correlation with RSSI and SNR:

| Source | RSSI Correlation | SNR Correlation |
|--------|-----------------|-----------------|
| status.bat | -0.19 | -0.26 |
| telemetry.value | -0.22 | -0.23 |

This confirms that battery voltage measurements are largely independent of radio transmission activity.

## Probable Explanation

The two values appear to come from different measurement systems within the firmware:

1. **`status.bat`**: Likely a direct ADC reading or internal firmware calculation - characterized by smooth, low-noise measurements with fine granularity.

2. **`telemetry.value`**: Likely a separate telemetry channel implementation - possibly using a different ADC, sampling rate, or averaging method, resulting in noisier readings.

## Why Fluctuations Occur

Battery voltage readings fluctuate due to several factors:

1. **ADC sampling noise**: Analog-to-digital conversion introduces quantization noise
2. **Load variations**: TX power draw, CPU activity, and GPS operations cause voltage sag
3. **Temperature effects**: Battery internal resistance changes with temperature
4. **Measurement timing**: The exact moment of sampling affects the reading (mid-transmission vs idle)
5. **Solar charging pulses**: MPPT charge controllers cause voltage variations during charging

## Recommendation

**Use `status.bat` as the primary battery voltage source.**

Reasons:
- 37% lower variance (more stable readings)
- Finer effective resolution (1mV vs 10mV)
- Fewer unexplained spikes
- Smooth measurement pattern suitable for trend analysis

The current implementation already uses this source correctly:
```python
bat_v = status.bat / 1000  # Convert millivolts to volts
```

The telemetry value can serve as a secondary validation check but should not be the primary source for charting or alerting.

## Additional Smoothing

Even with the more stable `status.bat` source, a 2-hour rolling average (TREND function in RRD) is applied to charts to further smooth out short-term fluctuations. This reveals the true discharge/charge pattern without visual noise.

## Data Source

Analysis based on snapshots from:
- `data/snapshots/repeater/2025/12/22/` (47 samples)
- `data/snapshots/repeater/2025/12/23/` (92 samples)
- `data/snapshots/repeater/2025/12/24/` (30 samples)

---

*Document created: December 24, 2025*
