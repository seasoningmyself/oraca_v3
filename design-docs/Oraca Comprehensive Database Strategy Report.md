# Oraca Comprehensive Database Strategy Report
**Prepared by:** Ennis M. Salam  
**Client:** Intertwined Investments

## 1. Executive Overview

I conducted a detailed review of the OraCore data layer and developed a comprehensive database strategy that addresses both immediate operational needs and future machine learning requirements. The existing MongoDB implementation functions for small-scale testing but shows critical limitations in structure, consistency, and scalability. 

After evaluating the current architecture, I present two migration paths with a clear recommendation for **Route B: Postgres + TimescaleDB (core only)**. This report includes both the strategic assessment and the complete technical implementation blueprint for an ML-ready data model that will support your trading intelligence platform's evolution.

## 2. Current State Analysis

### Architecture Assessment
The current pipeline follows this flow:
```
Yahoo Finance → Scanner → MongoDB Atlas → API / Dashboard → Trader
```

I found only three active collections (prediction_data, trade_logs, scanner_hits) with no indexes or schema validators. Data is overwritten each run instead of preserved historically, a critical gap for ML training.

### Key Findings

| Area | Observation | Business Impact |
|------|-------------|-----------------|
| Performance | Queries scan entire collections | Slower response as data grows |
| Data Retention | Each scan replaces existing data | No history for analytics or ML |
| Data Quality | No type enforcement or validation | Risk of inconsistent calculations |
| Security | Credentials repeated across files | Increased exposure |
| Automation | Manual execution; no scheduler | Inconsistent runtime and maintenance burden |

### What's Working
- Trading logic runs correctly and produces usable outputs
- MongoDB Atlas hosting eliminates server management
- Data model is simple enough for smooth migration
- Python stack (pandas/scikit-learn) integrates well with either database option

## 3. Strategic Migration Options

### Route A — Harden MongoDB (Stay and Fix)
**Objective:** Keep MongoDB Atlas but implement targeted improvements.

**Implementation:**
- Add timestamps and schema validators
- Create indexes on ticker, timestamp, and roi
- Preserve history using run_id field
- Normalize tickers and enforce numeric types
- Enable backups and introduce job scheduler

**Pros:** Minimal code change, fastest path to incremental stability  
**Cons:** Still limited for analytics; would likely revisit storage layer again

### Route B — Postgres + TimescaleDB (Core Only) RECOMMENDED
**Objective:** Establish a reliable, structured foundation with managed Postgres + Timescale extension.

**What "Core Only" Includes:**
- Structured storage with well-defined SQL tables
- Time-series optimization via Timescale hypertables
- Indexes and constraints for data integrity
- Simple SQL querying from existing Python stack
- Managed reliability (backups, monitoring)

**What It Excludes (for now):**
- No Redis cache or job-locking layer
- No S3/Parquet archive for ML training data
- No message queues or complex orchestration

These can be added incrementally as volume demands.

## 4. Comparison Matrix

| Criteria | Route A: Harden Mongo | Route B: Postgres + Timescale |
|----------|----------------------|-------------------------------|
| Change scope | Minimal configuration | Small, focused migration |
| Time to stability | Days | 2-3 weeks |
| Historical data | Added via run IDs | Native support (hypertables) |
| Query performance | Moderate with indexes | Strong and consistent |
| Data quality | Basic validation | Full relational constraints |
| ML readiness | Possible but manual | Direct and seamless |
| Long-term fit | Short-term solution | Scalable foundation |
| **Recommended?** | Viable fallback | **✅ Preferred route** |

## 5. ML-Ready Data Model Implementation

I've designed a comprehensive data model that works for both immediate human-in-the-loop trading and future ML training. The schema captures clean inputs, clear labels, and full auditability.

### Core Data Requirements for ML Training

For each trading signal, we need:

1. **Context at signal time**
   - OHLCV data on multiple timeframes (1m/5m/15m/1h/4h/5h)
   - Technical indicators (RSI, MACD, ATR, VWAP, Bollinger Bands, relative volume)
   - Market session context (pre/regular/after, day of week, market regime)
   - Data provenance (scanner version, parameters)

2. **Ground-truth outcomes** (computed from future candles)
   - Forward returns over multiple horizons (5/15/60/240/1440 bars)
   - Max run-up and drawdown within each horizon
   - Target price hits (TP1/TP2/TP3) and stop-loss triggers
   - Time-to-event metrics

3. **Human actions** (optional features for policy learning)
   - Trader decisions (enter/ignore/watch)
   - Execution details (entry/exit/partials, P&L)
   - Reason codes and contextual notes

4. **Negative samples**
   - Random non-signal times for balanced training sets

### Database Schema (Postgres + Timescale)

All timestamps are UTC, prices in quote currency (USD), tickers normalized to UPPERCASE. JSONB fields map 1:1 to MongoDB documents if staying on Mongo temporarily.

#### 1. symbols — Instrument Registry
```sql
CREATE TABLE symbols (
  id           BIGSERIAL PRIMARY KEY,
  ticker       TEXT NOT NULL,
  exchange     TEXT,
  asset_type   TEXT DEFAULT 'equity',
  currency     TEXT DEFAULT 'USD',
  active       BOOLEAN DEFAULT TRUE,
  first_seen   TIMESTAMPTZ,
  last_seen    TIMESTAMPTZ,
  UNIQUE (ticker, COALESCE(exchange,''))
);
```

#### 2. candles — Multi-Timeframe OHLCV (Hypertable)
```sql
CREATE TABLE candles (
  symbol_id   BIGINT NOT NULL REFERENCES symbols(id),
  timeframe   TEXT   NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','5h')),
  ts          TIMESTAMPTZ NOT NULL,
  open        NUMERIC(18,6),
  high        NUMERIC(18,6),
  low         NUMERIC(18,6),
  close       NUMERIC(18,6),
  volume      BIGINT,
  vwap        NUMERIC(18,6),
  source      TEXT,                    -- 'yfinance', etc.
  is_adjusted BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (symbol_id, timeframe, ts)
);
SELECT create_hypertable('candles', 'ts', chunk_time_interval => interval '7 days');
CREATE INDEX ON candles (symbol_id, timeframe, ts DESC);
```

#### 3. detectors — Scanner/Strategy Catalog
```sql
CREATE TABLE detectors (
  id           TEXT PRIMARY KEY,      -- 'breakout_v1'
  version      TEXT NOT NULL,
  kind         TEXT NOT NULL,         -- 'rule' | 'ml'
  description  TEXT,
  params       JSONB                  -- thresholds, lookbacks
);
```

#### 4. signals — Event Detection (Hypertable)
```sql
CREATE TABLE signals (
  id                BIGSERIAL PRIMARY KEY,
  symbol_id         BIGINT NOT NULL REFERENCES symbols(id),
  timeframe         TEXT   NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','5h')),
  fired_at          TIMESTAMPTZ NOT NULL,
  side              TEXT CHECK (side IN ('long','short')),
  detector_id       TEXT NOT NULL REFERENCES detectors(id),
  detector_version  TEXT NOT NULL,
  score             NUMERIC,
  price_at_signal   NUMERIC(18,6),
  bid               NUMERIC(18,6),
  ask               NUMERIC(18,6),
  spread            NUMERIC(18,6),
  rel_volume        NUMERIC(18,6),
  session           TEXT,
  features          JSONB,              -- RSI/MACD/ATR snapshot
  data_freshness_ms INTEGER,
  source_system     TEXT NOT NULL,      -- 'basic_scanner' | 'ml_scanner'
  watch_run_id      TEXT,
  UNIQUE(symbol_id, timeframe, fired_at, detector_id, detector_version)
);
SELECT create_hypertable('signals', 'fired_at');
CREATE INDEX ON signals (symbol_id, timeframe, fired_at DESC);
CREATE INDEX ON signals (detector_id, detector_version);
```

#### 5. alerts — Notification History
```sql
CREATE TABLE alerts (
  id          BIGSERIAL PRIMARY KEY,
  signal_id   BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  channel     TEXT,              -- 'discord','email','slack'
  payload     JSONB,
  delivered   BOOLEAN DEFAULT TRUE
);
CREATE INDEX ON alerts (signal_id);
```

#### 6. decisions — Human Response Tracking
```sql
CREATE TABLE decisions (
  id          BIGSERIAL PRIMARY KEY,
  signal_id   BIGINT NOT NULL REFERENCES signals(id),
  decided_at  TIMESTAMPTZ NOT NULL,
  action      TEXT NOT NULL CHECK (action IN ('ignore','enter','watch','snooze')),
  note        TEXT,
  reasons     JSONB,
  decided_by  TEXT DEFAULT 'human'
);
CREATE INDEX ON decisions (signal_id, decided_at);
```

#### 7. orders & executions — Trade Journal
```sql
CREATE TABLE orders (
  id            BIGSERIAL PRIMARY KEY,
  symbol_id     BIGINT NOT NULL REFERENCES symbols(id),
  signal_id     BIGINT REFERENCES signals(id),
  side          TEXT CHECK (side IN ('buy','sell','short','cover')),
  order_type    TEXT,
  submitted_at  TIMESTAMPTZ,
  qty           NUMERIC,
  limit_price   NUMERIC(18,6),
  stop_price    NUMERIC(18,6),
  status        TEXT,
  broker        TEXT,
  meta          JSONB
);

CREATE TABLE executions (
  id           BIGSERIAL PRIMARY KEY,
  order_id     BIGINT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  filled_at    TIMESTAMPTZ NOT NULL,
  qty          NUMERIC NOT NULL,
  price        NUMERIC(18,6) NOT NULL,
  fee          NUMERIC(18,6),
  tag          TEXT,                       -- 'ENTRY','TP1','TP2','TP3','STOP'
  liquidity    TEXT
);
CREATE INDEX ON executions (order_id, filled_at);
```

#### 8. outcomes — ML Training Labels (Hypertable)
```sql
CREATE TABLE outcomes (
  signal_id        BIGINT NOT NULL REFERENCES signals(id) ON DELETE CASCADE,
  horizon_tf       TEXT   NOT NULL CHECK (horizon_tf IN ('1m','5m','15m','1h','4h','5h','1d')),
  horizon_bars     INTEGER NOT NULL,
  ret_close        NUMERIC(12,6),
  max_run_up       NUMERIC(12,6),
  max_drawdown     NUMERIC(12,6),
  hit_tp1          BOOLEAN,
  hit_tp2          BOOLEAN,
  hit_tp3          BOOLEAN,
  hit_stop         BOOLEAN,
  t_to_tp1         INTERVAL,
  t_to_stop        INTERVAL,
  label_version    INTEGER NOT NULL DEFAULT 1,
  computed_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (signal_id, horizon_tf, horizon_bars, label_version)
);
SELECT create_hypertable('outcomes', 'computed_at');
```

#### 9. baselines — Negative Samples
```sql
CREATE TABLE baselines (
  id            BIGSERIAL PRIMARY KEY,
  symbol_id     BIGINT NOT NULL REFERENCES symbols(id),
  timeframe     TEXT NOT NULL,
  ts            TIMESTAMPTZ NOT NULL,
  features      JSONB,
  label_version INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX ON baselines (symbol_id, timeframe, ts DESC);
```

#### 10. watch_requests — Scan Configuration
```sql
CREATE TABLE watch_requests (
  id           BIGSERIAL PRIMARY KEY,
  symbol_id    BIGINT NOT NULL REFERENCES symbols(id),
  timeframe    TEXT NOT NULL CHECK (timeframe IN ('1m','5m','15m','1h','4h','5h')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  params       JSONB,
  active       BOOLEAN DEFAULT TRUE
);
```

### Feature Storage Specification

The `signals.features` JSONB field should contain:
- **Technical indicators:** rsi14, macd_hist, atr14, vwap_dist, bb_width, bb_pct
- **Volume metrics:** rel_vol_20 (current vs 20-bar average)
- **Trend indicators:** trend_sma20_pct, trend_sma50_pct, trend_sma200_pct
- **Multi-timeframe:** multi_tf_confirmation (boolean/int)
- **Market microstructure:** spread_bps, session_flag (0=pre, 1=regular, 2=after)
- **Market context (optional):** spy_15m_ret, vix_level

### Labeling Pipeline

For each signal, compute outcomes by:
1. Using price_at_signal as entry point
2. Slicing next N bars from candles table
3. Computing:
   - `ret_close = (close[t+N] - entry) / entry`
   - `max_run_up = (max(high[t..t+N]) - entry) / entry`
   - `max_drawdown = (min(low[t..t+N]) - entry) / entry`
   - Target hits based on thresholds (e.g., TP1=+1.5%, TP2=+3%, TP3=+5%, Stop=-1%)
   - Time-to-event for first threshold crossing

Store outcomes for multiple horizons (5, 15, 60, 240 bars) to support different trading styles.

### Training Data Query Example
```sql
SELECT
  s.id AS signal_id,
  sym.ticker,
  s.timeframe,
  s.fired_at,
  s.side,
  s.price_at_signal,
  (s.features->>'rsi14')::NUMERIC AS rsi14,
  (s.features->>'macd_hist')::NUMERIC AS macd_hist,
  (s.features->>'rel_vol_20')::NUMERIC AS rel_vol_20,
  o.horizon_tf,
  o.horizon_bars,
  o.max_run_up,
  o.max_drawdown,
  o.ret_close,
  o.hit_tp1,
  o.hit_tp2,
  o.hit_tp3,
  o.hit_stop
FROM signals s
JOIN symbols sym ON sym.id = s.symbol_id
JOIN outcomes o ON o.signal_id = s.id
WHERE o.horizon_tf = '15m' AND o.horizon_bars = 20;
```

## 6. MongoDB Compatibility Mapping

If staying on MongoDB temporarily, map as follows:
- `symbols` → symbols collection (unique on ticker+exchange)
- `candles` → candles collection (compound index: symbol_id, timeframe, ts)
- `signals` → signals collection (compound index: symbol_id, timeframe, fired_at)
- `outcomes` → outcomes collection (indexed by signal_id, horizon_tf, horizon_bars)
- All other tables → corresponding collections with document references

JSONB fields translate directly to MongoDB subdocuments. Typed columns become document fields with validation rules.

## 7. Migration Implementation Plan

### Phase 1: Foundation (Week 1)
- Set up managed Postgres + Timescale instance
- Create schema with all tables and hypertables
- Configure connection pooling and credentials management

### Phase 2: Dual-Write Transition (Week 2)
- Implement dual-write logic (MongoDB + Postgres)
- Validate data consistency between systems
- Begin historical data backfill

### Phase 3: Cutover (Week 3)
- Switch API/dashboard reads to Postgres
- Monitor performance and fix edge cases
- Deprecate MongoDB writes

### Phase 4: Enhancement (Optional, Post-Migration)
- Add Redis cache layer for hot data
- Implement S3/Parquet archive for ML training sets
- Deploy automated labeling pipeline

## 8. Immediate Action Items

1. **Finalize feature list** for signals.features (start with RSI, MACD, ATR, VWAP distance, relative volume)
2. **Implement signals + outcomes tables** first; backfill outcomes for small batch to validate pipeline
3. **Deploy labeling ETL** to compute outcomes nightly for new signals
4. **Begin dual-write implementation** with basic_scanner writing to both databases

## 9. Business Impact Summary

This migration will deliver:
- **Reliability:** Millisecond queries even at scale, with ACID guarantees
- **ML Readiness:** Clean training data with proper labels and features
- **Historical Analysis:** Complete signal and outcome history for backtesting
- **Security:** Centralized credential management and automated backups
- **Maintainability:** Single engineer can manage the entire data layer
- **Scalability:** Foundation supports 100x growth without re-architecture

## 10. Technical Recommendations

Given your current setup with two scanners (basic vs ML) feeding Discord alerts via yfinance data, I recommend:

1. **Use signals.source_system** to distinguish 'basic_scanner' vs 'ml_scanner' for provenance tracking
2. **Document yfinance as source** in candles.source field
3. **Support 5-hour candles** by storing '5h' timeframe and generating from 1h/15m base data
4. **Start with Timescale Cloud** for managed hosting to minimize operational overhead
5. **Implement outcomes computation** as async job to avoid blocking signal processing

## Conclusion

Route B (Postgres + TimescaleDB core only) provides the optimal balance of immediate stability and long-term scalability. The proposed schema supports both current human-in-the-loop operations and future ML model training without requiring future migrations. This approach keeps the system manageable for a single engineer while providing enterprise-grade reliability and performance.

The total implementation effort is approximately 2-3 weeks for core migration, with immediate benefits in query performance, data integrity, and ML readiness. This positions Intertwined Investments to scale both operationally and analytically as the trading platform evolves.