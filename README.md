# Oraca Trading System

Modular trading system with market data integration and Discord notifications.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add API keys to .env.local
echo "DISCORD_API_KEY_Alert-v1=your_discord_token" >> .env.local
echo "MASSIVE_API_KEY_SSLABS=your_polygon_key" >> .env.local

# 3. Set up database
./setup_database.sh

# 4. Run demo
python3 demo_market_data.py
```

## Modules

### Bot Module (`bot/`)
Discord bot for sending notifications to multiple channels.

**Features:**
- Multi-channel support
- Generic message service
- Clean configuration via YAML

### Market Data Module (`market_data/`)
Fetches market data from Polygon.io, stores in PostgreSQL, displays in Discord.

**Features:**
- Real-time and historical data
- Multi-timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
- Trading signal formatting
- Repository pattern for database access

## Architecture

```
Polygon.io → MassiveClient → DataService → PostgreSQL
                                    ↓
                            DisplayService → Bot → Discord
```

## Requirements

- Python 3.12+
- PostgreSQL 17
- Discord Bot Token
- Polygon.io API Key

## Configuration

All configuration is done via YAML files:
- `bot/config.yaml` - Discord bot settings
- `market_data/config.yaml` - Data sources and tickers

### Manual Watchlist (CSV import)
- Place your CSV (ticker in first column) in `market_data/manual_data/`.
- Import into the DB (replace existing list with `--truncate`):
  ```bash
  PYTHONPATH=. python3 -m market_data.scripts.manual_data.import_watchlist_csv \
    --file market_data/manual_data/your_watchlist.csv --truncate
  ```

### Ingestion + Scanning
- Run the ingestion loop (default: manual watchlist tickers, 15m + 1d bars, 2-day retention, 15m interval):
  ```bash
  PYTHONPATH=. python3 -m market_data.scripts.run_ingestion_loop \
    --timeframes 15m --recency-minutes 120 --retention-days 2 --interval-seconds 900
  ```
- This fetches 1d (for GUI price/volume filters) and 15m (for scanners), triggers scanners, and prunes old candles.

### GUI (universe + signals)
- Start the UI (synchronous, reads DB):
  ```bash
  PYTHONPATH=. flask --app market_data.gui.app run --host 0.0.0.0 --port 8002
  ```
- Browse: `http://127.0.0.1:8002/?price_min=0.4&price_max=50&min_volume=40000`
- Universe table uses latest 1d bars for price/volume; scanner tables show recent signals.

See individual module READMEs for details.
