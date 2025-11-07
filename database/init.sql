-- OraCore Database Initialization (Simplified for Dev - No TimescaleDB)
SET TIME ZONE 'UTC';

-- ============================================================================
-- CORE TABLES
-- ============================================================================

-- Symbols: Instrument registry
CREATE TABLE IF NOT EXISTS symbols (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    exchange TEXT DEFAULT '',
    asset_type TEXT DEFAULT 'equity',
    currency TEXT DEFAULT 'USD',
    first_seen TIMESTAMPTZ DEFAULT NOW(),
    last_seen TIMESTAMPTZ,
    UNIQUE (ticker, exchange)
);

CREATE INDEX IF NOT EXISTS idx_symbols_ticker ON symbols(ticker);

-- ============================================================================
-- Candles: Multi-timeframe OHLCV
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

-- Index for fast queries
CREATE INDEX IF NOT EXISTS idx_candles_symbol_tf_ts ON candles (symbol_id, timeframe, ts DESC);

-- ============================================================================
-- Signals: Strategy-generated trading signals
CREATE TABLE IF NOT EXISTS signals (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    strategy TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('LONG','SHORT')),
    fired_at TIMESTAMPTZ NOT NULL,
    timeframe TEXT,
    confidence NUMERIC(5,2),
    entry_price NUMERIC(18,6),
    stop_loss NUMERIC(18,6),
    take_profit NUMERIC(18,6),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_signals_symbol_fired ON signals(symbol_id, fired_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy);

-- ============================================================================
-- Alerts: User-facing notifications
CREATE TABLE IF NOT EXISTS alerts (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id),
    alert_type TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    channel TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_alerts_signal ON alerts(signal_id);

-- ============================================================================
-- Decisions: Trade decision log
CREATE TABLE IF NOT EXISTS decisions (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT REFERENCES signals(id),
    action TEXT NOT NULL CHECK (action IN ('TAKE','SKIP','WAIT')),
    decided_at TIMESTAMPTZ DEFAULT NOW(),
    reason TEXT,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_decisions_signal ON decisions(signal_id);

-- ============================================================================
-- Orders: Broker order log
CREATE TABLE IF NOT EXISTS orders (
    id BIGSERIAL PRIMARY KEY,
    symbol_id BIGINT NOT NULL REFERENCES symbols(id),
    order_type TEXT NOT NULL CHECK (order_type IN ('MARKET','LIMIT','STOP','STOP_LIMIT')),
    side TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity NUMERIC(18,6) NOT NULL,
    price NUMERIC(18,6),
    status TEXT NOT NULL CHECK (status IN ('PENDING','SUBMITTED','FILLED','CANCELLED','REJECTED')),
    submitted_at TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status, submitted_at DESC);

-- ============================================================================
-- Executions: Order fills
CREATE TABLE IF NOT EXISTS executions (
    id BIGSERIAL PRIMARY KEY,
    order_id BIGINT NOT NULL REFERENCES orders(id),
    executed_at TIMESTAMPTZ NOT NULL,
    filled_quantity NUMERIC(18,6) NOT NULL,
    filled_price NUMERIC(18,6) NOT NULL,
    commission NUMERIC(18,6),
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_executions_order ON executions(order_id);

-- ============================================================================
-- Outcomes: Signal performance tracking
CREATE TABLE IF NOT EXISTS outcomes (
    id BIGSERIAL PRIMARY KEY,
    signal_id BIGINT NOT NULL REFERENCES signals(id),
    computed_at TIMESTAMPTZ NOT NULL,
    holding_period_hours NUMERIC(10,2),
    pnl_pct NUMERIC(10,4),
    max_drawdown_pct NUMERIC(10,4),
    hit_target BOOLEAN,
    hit_stop BOOLEAN,
    metadata JSONB
);

CREATE INDEX IF NOT EXISTS idx_outcomes_signal ON outcomes(signal_id);

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
DO $$
BEGIN
    RAISE NOTICE '✅ OraCore database initialized successfully (simplified mode)!';
    RAISE NOTICE 'Tables created: symbols, candles, signals, outcomes, alerts, orders, executions, decisions';
    RAISE NOTICE 'Note: Running without TimescaleDB for development';
END $$;
