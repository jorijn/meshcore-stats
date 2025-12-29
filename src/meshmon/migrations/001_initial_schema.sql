-- Migration 001: Initial schema
-- Creates companion_metrics and repeater_metrics tables

-- Companion metrics (6 metrics, ~525K rows/year at 60s intervals)
CREATE TABLE IF NOT EXISTS companion_metrics (
    ts INTEGER PRIMARY KEY NOT NULL,
    bat_v REAL,
    bat_pct REAL,
    contacts INTEGER,
    uptime INTEGER,
    rx INTEGER,
    tx INTEGER
) STRICT, WITHOUT ROWID;

-- Repeater metrics (17 metrics, ~35K rows/year at 15min intervals)
CREATE TABLE IF NOT EXISTS repeater_metrics (
    ts INTEGER PRIMARY KEY NOT NULL,
    bat_v REAL,
    bat_pct REAL,
    rssi INTEGER,
    snr REAL,
    uptime INTEGER,
    noise INTEGER,
    txq INTEGER,
    rx INTEGER,
    tx INTEGER,
    airtime INTEGER,
    rx_air INTEGER,
    fl_dups INTEGER,
    di_dups INTEGER,
    fl_tx INTEGER,
    fl_rx INTEGER,
    di_tx INTEGER,
    di_rx INTEGER
) STRICT, WITHOUT ROWID;

-- Schema metadata
CREATE TABLE IF NOT EXISTS db_meta (
    key TEXT PRIMARY KEY NOT NULL,
    value TEXT NOT NULL
) STRICT, WITHOUT ROWID;
