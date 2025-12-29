-- Migration 002: EAV metrics schema
-- Replaces wide companion_metrics and repeater_metrics tables with
-- a single flexible Entity-Attribute-Value pattern.
--
-- Benefits:
-- - New firmware fields automatically captured without schema changes
-- - Firmware field renames only require Python config updates
-- - Unified query interface for all metrics
--
-- Trade-offs:
-- - More rows (~3.75M/year vs ~560K/year)
-- - Queries filter by metric name instead of column access
-- - All values stored as REAL (no per-column type safety)

-- Create new EAV metrics table
CREATE TABLE metrics (
    ts INTEGER NOT NULL,
    role TEXT NOT NULL,            -- 'companion' or 'repeater'
    metric TEXT NOT NULL,          -- Firmware field name (e.g., 'bat', 'nb_recv')
    value REAL,                    -- Metric value
    PRIMARY KEY (ts, role, metric)
) STRICT, WITHOUT ROWID;

-- Index for common query pattern: get all metrics for a role in time range
-- Primary key covers (ts, role, metric) but this helps when filtering by role first
CREATE INDEX idx_metrics_role_ts ON metrics(role, ts);

-- Migrate companion data to firmware field names
-- Note: bat_v stored as volts, convert back to millivolts (battery_mv)
INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'companion', 'battery_mv', bat_v * 1000 FROM companion_metrics WHERE bat_v IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'companion', 'uptime_secs', uptime FROM companion_metrics WHERE uptime IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'companion', 'contacts', contacts FROM companion_metrics WHERE contacts IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'companion', 'recv', rx FROM companion_metrics WHERE rx IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'companion', 'sent', tx FROM companion_metrics WHERE tx IS NOT NULL;

-- Migrate repeater data to firmware field names
-- Note: bat_v stored as volts, convert back to millivolts (bat)
INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'bat', bat_v * 1000 FROM repeater_metrics WHERE bat_v IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'uptime', uptime FROM repeater_metrics WHERE uptime IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'last_rssi', rssi FROM repeater_metrics WHERE rssi IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'last_snr', snr FROM repeater_metrics WHERE snr IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'noise_floor', noise FROM repeater_metrics WHERE noise IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'tx_queue_len', txq FROM repeater_metrics WHERE txq IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'nb_recv', rx FROM repeater_metrics WHERE rx IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'nb_sent', tx FROM repeater_metrics WHERE tx IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'airtime', airtime FROM repeater_metrics WHERE airtime IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'rx_airtime', rx_air FROM repeater_metrics WHERE rx_air IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'flood_dups', fl_dups FROM repeater_metrics WHERE fl_dups IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'direct_dups', di_dups FROM repeater_metrics WHERE di_dups IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'sent_flood', fl_tx FROM repeater_metrics WHERE fl_tx IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'recv_flood', fl_rx FROM repeater_metrics WHERE fl_rx IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'sent_direct', di_tx FROM repeater_metrics WHERE di_tx IS NOT NULL;

INSERT INTO metrics (ts, role, metric, value)
SELECT ts, 'repeater', 'recv_direct', di_rx FROM repeater_metrics WHERE di_rx IS NOT NULL;

-- Drop old wide tables
DROP TABLE companion_metrics;
DROP TABLE repeater_metrics;
