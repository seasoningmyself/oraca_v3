-- OraCore Database Initialization
-- Creates all tables, indexes, and policies for the trading system

-- Enable TimescaleDB
CREATE EXTENSION IF NOT EXISTS timescaledb;
SET TIME ZONE 'UTC';

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Symbols: Instrument registry
CREATE TABLE IF NOT EXISTS symbols (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    exchange TEXT,
    asset_type TEXT DEFAULT 'equity',
    currency TEXT DEFAULT 'USD',
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ,
    UNIQUE (ticker, COALESCE(exchange,''))
);

CREATE INDEX idx_symbols_ticker ON symbols(ticker);

-- ============================================================================
-- Candles: Multi-timeframe OHLCV (30-day rolling window)
CREATE TABLE IF NOT EXISTS candles (
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    timeframe TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','5h','1d')),
    ts TIMESTAMPTZ NOT NULL,
    open NUMERIC(18,6),
    high NUMERIC(18,6),
    low NUMERIC(18,6),
    close NUMERIC(18,6),
    volume BIGINT,
    vwap NUMERIC(18,6),
    trade_count BIGINT,
    source TEXT DEFAULT 'provider',
    is_adjusted BOOLEAN DEFAULT TRUE,
    PRIMARY KEY (symbol_id, timeframe, ts)
);

-- Convert to hypertable
SELECT create_hypertable('candles', 'ts', if_not_exists => TRUE);

-- Index for fast queries
CREATE INDEX idx_candles_symbol_tf_ts ON candles (symbol_id, timeframe, ts DESC);

-- ============================================================================
-- Detectors: Strategy and model registry
CREATE TABLE IF NOT EXISTS detectors (
    id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('rule','ml')),
    description TEXT,
    params JSONB
);

-- ============================================================================
-- Signals: Events at detection time (persistent)
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    timeframe TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','5h','1d')),
    fired_at TIMESTAMPTZ NOT NULL,
    side TEXT CHECK (side IN ('long','short')),
    detector_id TEXT NOT NULL REFERENCES detectors(id),
    detector_version TEXT NOT NULL,
    source_system TEXT NOT NULL,
    watch_run_id TEXT,
    price_at_signal NUMERIC(18,6),
    bid NUMERIC(18,6),
    ask NUMERIC(18,6),
    spread NUMERIC(18,6),
    rel_volume NUMERIC(18,6),
    session TEXT,
    data_freshness_ms INTEGER,
    features JSONB,
    features_version INTEGER NOT NULL DEFAULT 1,
    UNIQUE(symbol_id, timeframe, fired_at, detector_id, detector_version)
);

-- Convert to hypertable
SELECT create_hypertable('signals', 'fired_at', if_not_exists => TRUE);

-- Indexes for fast queries
CREATE INDEX idx_signals_symbol_tf_fired ON signals (symbol_id, timeframe, fired_at DESC);
CREATE INDEX idx_signals_detector ON signals (detector_id, detector_version);

-- ============================================================================
-- Alerts: Notifications emitted
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    channel TEXT,
    payload JSONB,
    delivered BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_alerts_signal ON alerts (signal_id);

-- ============================================================================
-- Journal Tables: Human and trade tracking
CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT NOT NULL REFERENCES signals(id),
    decided_at TIMESTAMPTZ NOT NULL,
    action TEXT NOT NULL CHECK (action IN ('ignore','enter','watch','snooze')),
    note TEXT,
    reasons JSONB,
    decided_by TEXT DEFAULT 'human'
);

CREATE INDEX idx_decisions_signal ON decisions (signal_id, decided_at);

CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    signal_id BIGINT REFERENCES signals(id),
    side TEXT CHECK (side IN ('buy','sell','short','cover')),
    order_type TEXT,
    submitted_at TIMESTAMPTZ,
    qty NUMERIC,
    limit_price NUMERIC(18,6),
    stop_price NUMERIC(18,6),
    status TEXT,
    broker TEXT,
    meta JSONB
);

CREATE INDEX idx_orders_symbol ON orders (symbol_id);
CREATE INDEX idx_orders_signal ON orders (signal_id);

CREATE TABLE IF NOT EXISTS executions (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    filled_at TIMESTAMPTZ NOT NULL,
    qty NUMERIC NOT NULL,
    price NUMERIC(18,6) NOT NULL,
    fee NUMERIC(18,6),
    tag TEXT,
    liquidity TEXT
);

CREATE INDEX idx_executions_order ON executions (order_id, filled_at);

-- ============================================================================
-- Outcomes: Labels for each signal and horizon (persistent)
CREATE TABLE IF NOT EXISTS outcomes (
    signal_id BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
    horizon_tf TEXT NOT NULL CHECK (horizon_tf IN ('1m','5m','15m','1h','4h','5h','1d')),
    horizon_bars INTEGER NOT NULL,
    ret_close NUMERIC(12,6),
    max_run_up NUMERIC(12,6),
    max_drawdown NUMERIC(12,6),
    hit_tp1 BOOLEAN,
    hit_tp2 BOOLEAN,
    hit_tp3 BOOLEAN,
    hit_stop BOOLEAN,
    t_to_tp1 INTERVAL,
    t_to_stop INTERVAL,
    label_version INTEGER NOT NULL DEFAULT 1,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (signal_id, horizon_tf, horizon_bars, label_version)
);

-- Convert to hypertable
SELECT create_hypertable('outcomes', 'computed_at', if_not_exists => TRUE);

CREATE INDEX idx_outcomes_signal ON outcomes (signal_id);

-- ============================================================================
-- CRITICAL: Ingestion Log (mandatory for debugging data flow)
CREATE TABLE IF NOT EXISTS ingestion_log (
    id BIGSERIAL PRIMARY KEY,
    source TEXT,
    symbol_id BIGINT,
    timeframe TEXT,
    bars_written INTEGER,
    lag_ms INTEGER,
    errors TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for recent log queries
CREATE INDEX idx_ingestion_log_created ON ingestion_log (created_at DESC);

-- ============================================================================
-- RETENTION & COMPRESSION POLICIES
-- ============================================================================

-- 30-day retention for candles
SELECT add_retention_policy('candles', INTERVAL '30 days', if_not_exists => TRUE);

-- Compression for candles older than 7 days
ALTER TABLE candles SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id,timeframe',
    timescaledb.compress_orderby = 'ts DESC'
);
SELECT add_compression_policy('candles', INTERVAL '7 days', if_not_exists => TRUE);

-- No retention for signals/outcomes (keep forever)
-- But compress old data for space efficiency
ALTER TABLE signals SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'symbol_id',
    timescaledb.compress_orderby = 'fired_at DESC'
);
SELECT add_compression_policy('signals', INTERVAL '30 days', if_not_exists => TRUE);

ALTER TABLE outcomes SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'signal_id',
    timescaledb.compress_orderby = 'computed_at DESC'
);
SELECT add_compression_policy('outcomes', INTERVAL '30 days', if_not_exists => TRUE);

-- ============================================================================
-- CONTINUOUS AGGREGATES (for faster queries)
-- ============================================================================

-- 15-minute candles from 1-minute data
CREATE MATERIALIZED VIEW IF NOT EXISTS candles_15m
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', ts) AS ts,
    symbol_id,
    '15m'::text AS timeframe,
    first(open, ts) AS open,
    max(high) AS high,
    min(low) AS low,
    last(close, ts) AS close,
    sum(volume) AS volume,
    avg(vwap) AS vwap,
    sum(trade_count) AS trade_count
FROM candles
WHERE timeframe = '1m'
GROUP BY symbol_id, time_bucket('15 minutes', ts)
WITH NO DATA;

-- Add refresh policy for continuous aggregate
SELECT add_continuous_aggregate_policy('candles_15m',
    start_offset => INTERVAL '2 days',
    end_offset => INTERVAL '5 minutes',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE
);

-- ============================================================================
-- INITIAL DATA
-- ============================================================================

-- Insert default detectors
INSERT INTO detectors (id, version, kind, description, params)
VALUES
    ('breakout_v1', '1.0.0', 'rule', 'Spring curl pattern detector', '{"threshold": 2.5}'::jsonb),
    ('volume_flush_v1', '1.0.0', 'rule', 'Volume flush detector', '{"min_ratio": 3.0}'::jsonb),
    ('ml_ensemble_v1', '1.0.0', 'ml', 'XGBoost + LSTM ensemble', '{"confidence_min": 0.75}'::jsonb)
ON CONFLICT (id) DO NOTHING;

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function to check data staleness
CREATE OR REPLACE FUNCTION check_data_staleness()
RETURNS TABLE(
    symbol_id BIGINT,
    ticker TEXT,
    last_candle TIMESTAMPTZ,
    staleness INTERVAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.symbol_id,
        s.ticker,
        MAX(c.ts) as last_candle,
        NOW() - MAX(c.ts) as staleness
    FROM candles c
    JOIN symbols s ON s.id = c.symbol_id
    WHERE c.timeframe = '1m'
    GROUP BY c.symbol_id, s.ticker
    HAVING NOW() - MAX(c.ts) > INTERVAL '5 minutes'
    ORDER BY staleness DESC;
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- PERMISSIONS (for future read-only user)
-- ============================================================================

-- Create read-only role (to be assigned to users later)
CREATE ROLE readonly_role;
GRANT CONNECT ON DATABASE oracore TO readonly_role;
GRANT USAGE ON SCHEMA public TO readonly_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO readonly_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO readonly_role;

-- ============================================================================
-- FINAL SETUP MESSAGE
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ OraCore database initialized successfully!';
    RAISE NOTICE 'TimescaleDB version: %', (SELECT extversion FROM pg_extension WHERE extname = 'timescaledb');
    RAISE NOTICE 'Tables created: symbols, candles, signals, outcomes, alerts, orders, executions, decisions';
    RAISE NOTICE 'Retention policy: 30 days for candles';
    RAISE NOTICE 'Compression: Enabled for data older than 7 days';
END $$;