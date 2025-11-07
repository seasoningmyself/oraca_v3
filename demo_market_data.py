"""
Demo script for Market Data integration.
Shows how to fetch data from Massive API, store in PostgreSQL, and display in Discord.
"""
import asyncio
from datetime import datetime, timedelta

# Bot imports
from bot.config import get_config as get_bot_config
from bot.bot_client import BotClient
from bot.services.message_service import MessageService

# Market data imports
from market_data.config import get_config as get_market_config
from market_data.client import MassiveClient
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.base_repository import BaseRepository
from market_data.services.data_service import DataService
from market_data.services.display_service import DisplayService


async def demo_fetch_and_display():
    """
    Demo: Fetch market data and display in Discord
    """
    print("=" * 60)
    print("ORACA MARKET DATA DEMO")
    print("=" * 60)

    # 1. Initialize bot
    print("\n[1/6] Initializing Discord bot...")
    bot_config = get_bot_config()
    bot_client = BotClient(bot_config)
    message_service = MessageService(bot_client, bot_config)

    # Start bot in background
    bot_task = asyncio.create_task(bot_client.start())
    await asyncio.sleep(3)  # Wait for connection
    print("✓ Bot connected")

    # 2. Initialize market data module
    print("\n[2/6] Initializing market data module...")
    market_config = get_market_config()
    massive_client = MassiveClient(market_config)

    # Create database connection pool
    await BaseRepository.create_pool(market_config)
    print("✓ Database pool created")

    # Create repositories
    symbol_repo = SymbolRepository(market_config)
    candle_repo = CandleRepository(market_config)

    # Create services
    data_service = DataService(massive_client, symbol_repo, candle_repo, market_config)
    display_service = DisplayService(message_service)
    print("✓ Services initialized")

    # 3. Fetch and store market data
    print("\n[3/6] Fetching market data from Massive API...")
    ticker = "AAPL"
    timeframe = "5m"

    # Get last 2 days of data
    to_date = datetime.now().strftime('%Y-%m-%d')
    from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')

    count = await data_service.fetch_and_store_candles(
        ticker=ticker,
        timeframe=timeframe,
        from_date=from_date,
        to_date=to_date
    )
    print(f"✓ Fetched and stored {count} candles for {ticker}")

    # 4. Get latest candle from database
    print("\n[4/6] Retrieving latest candle from database...")
    latest_candle = await data_service.get_latest_candle(ticker, timeframe)

    if latest_candle:
        print(f"✓ Latest {ticker} candle:")
        print(f"  Time: {latest_candle.ts}")
        print(f"  Close: ${latest_candle.close}")
        print(f"  Volume: {latest_candle.volume:,}")
    else:
        print("✗ No candle found")
        return

    # 5. Display in Discord - Candle Summary
    print("\n[5/6] Sending candle summary to Discord...")
    await display_service.send_candle_summary(
        ticker=ticker,
        candle=latest_candle,
        timeframe="5-minute"
    )
    print("✓ Candle summary sent to Discord")

    await asyncio.sleep(2)

    # 6. Display trading signal example
    print("\n[6/6] Sending trading signal to Discord...")
    from decimal import Decimal
    await display_service.send_trading_signal(
        symbol=f"{ticker}/USD",
        direction="LONG",
        entry_price=f"${latest_candle.close:,.2f}",
        stop_loss=f"${latest_candle.close * Decimal('0.98'):,.2f}",
        take_profit=f"${latest_candle.close * Decimal('1.05'):,.2f}",
        confidence="78%",
        additional_fields=[
            {"name": "Timeframe", "value": "5m", "inline": True},
            {"name": "Volume", "value": f"{latest_candle.volume:,}", "inline": True}
        ]
    )
    print("✓ Trading signal sent to Discord")

    # Cleanup
    print("\n[7/7] Cleanup...")
    await BaseRepository.close_pool()
    await bot_client.close()
    await bot_task

    print("\n" + "=" * 60)
    print("DEMO COMPLETE!")
    print("=" * 60)
    print("\nCheck your Discord channel to see:")
    print("  1. Candle summary with OHLCV data")
    print("  2. Trading signal alert")
    print("\nNext steps:")
    print("  - Add more tickers to config.yaml")
    print("  - Fetch data for multiple timeframes")
    print("  - Set up automated data collection")
    print("  - Build trading signal detection logic")


async def demo_live_price():
    """
    Demo: Get live price and display simple update
    """
    print("\nFetching live price...")

    # Initialize
    market_config = get_market_config()
    bot_config = get_bot_config()

    massive_client = MassiveClient(market_config)
    bot_client = BotClient(bot_config)
    message_service = MessageService(bot_client, bot_config)
    display_service = DisplayService(message_service)

    # Start bot
    bot_task = asyncio.create_task(bot_client.start())
    await asyncio.sleep(3)

    # Get live price
    ticker = "AAPL"
    price_info = await massive_client.get_latest_price(ticker)

    if price_info:
        print(f"Latest {ticker} price: ${price_info['price']}")

        # Send to Discord
        await display_service.send_price_update(
            ticker=ticker,
            price=price_info['price'],
            timestamp=price_info['timestamp']
        )
        print("✓ Price update sent to Discord")

    # Cleanup
    await bot_client.close()
    await bot_task


if __name__ == "__main__":
    print("\nOraca Market Data Module Demo")
    print("==============================\n")
    print("Options:")
    print("  1. Full demo (fetch, store, display)")
    print("  2. Live price demo\n")

    choice = input("Enter choice (1 or 2, default=1): ").strip() or "1"

    try:
        if choice == "2":
            asyncio.run(demo_live_price())
        else:
            asyncio.run(demo_fetch_and_display())
    except KeyboardInterrupt:
        print("\n\nDemo stopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
        import traceback
        traceback.print_exc()
        raise
