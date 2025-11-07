# Oraca Market Data Module

Modular market data integration for the Oraca trading system. Fetches data from Massive (Polygon.io), stores in PostgreSQL, and displays in Discord.

## Features

- ✅ Massive (Polygon.io) API integration
- ✅ PostgreSQL storage
- ✅ Multi-timeframe support (1m, 5m, 15m, 1h, 4h, 1d)
- ✅ Discord display formatting (price updates, candles, trading signals)
- ✅ Async/await throughout
- ✅ Type-safe with Pydantic models

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API key to .env.local
echo "MASSIVE_API_KEY_SSLABS=your_api_key_here" >> .env.local

# 3. Set up database (one command!)
./setup_database.sh

# 4. Run demo
python3 demo_market_data.py
```

That's it! Check your Discord channel for the messages.

## Configuration

Edit `market_data/config.yaml` to customize tickers:
```yaml
tickers:
  watch_list:
    - AAPL
    - MSFT
    - GOOGL
```

## Usage

```python
from market_data.config import get_config
from market_data.client import MassiveClient
from market_data.services.data_service import DataService

# Initialize
config = get_config()
data_service = DataService(...)

# Fetch and store data
count = await data_service.fetch_and_store_candles(
    ticker="AAPL",
    timeframe="5m",
    from_date="2025-01-01",
    to_date="2025-01-07"
)

# Get latest candle
candle = await data_service.get_latest_candle("AAPL", "5m")
```

## Architecture

```
Massive API → MassiveClient → DataService → Repositories → PostgreSQL
                                                ↓
                                          DisplayService → Discord
```

## Module Structure

- `client.py` - Massive API wrapper
- `services/data_service.py` - Fetch & store logic
- `services/display_service.py` - Discord formatting
- `repositories/` - Database access layer
- `models/` - Pydantic data models
- `config.py` - Configuration management
