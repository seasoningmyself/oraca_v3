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

See individual module READMEs for details.
