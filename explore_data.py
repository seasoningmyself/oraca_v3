#!/usr/bin/env python3
"""
Explore the data in your database.
Shows what information you have at your disposal.
"""
import asyncio
from datetime import datetime, timedelta
from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.candle_repository import CandleRepository


async def explore_data():
    """Explore what data is available in the database"""

    # Initialize
    config = get_config()
    await BaseRepository.create_pool(config)

    symbol_repo = SymbolRepository(config)
    candle_repo = CandleRepository(config)

    print("=" * 60)
    print("ORACA DATA EXPLORER")
    print("=" * 60)

    # 1. Show all symbols
    print("\n📊 SYMBOLS IN DATABASE:")
    print("-" * 60)
    symbols = await symbol_repo.list_all()
    for symbol in symbols:
        print(f"  • {symbol.ticker:6} ({symbol.asset_type}) - Last seen: {symbol.last_seen}")

    # 2. For each symbol, show candle statistics
    print("\n📈 CANDLE DATA AVAILABLE:")
    print("-" * 60)
    for symbol in symbols:
        candles = await candle_repo.get_candles(
            symbol_id=symbol.id,
            timeframe="5m",
            limit=1000
        )

        if candles:
            earliest = min(c.ts for c in candles)
            latest = max(c.ts for c in candles)
            total_volume = sum(c.volume for c in candles)
            avg_volume = total_volume / len(candles)

            print(f"\n{symbol.ticker} - 5m timeframe:")
            print(f"  Candles: {len(candles)}")
            print(f"  Period: {earliest} to {latest}")
            print(f"  Total Volume: {total_volume:,}")
            print(f"  Avg Volume/Candle: {avg_volume:,.0f}")

            # Price statistics
            prices = [c.close for c in candles]
            print(f"  Price Range: ${min(prices)} - ${max(prices)}")
            print(f"  Latest Price: ${candles[0].close}")

    # 3. Show what fields are available
    print("\n🔍 AVAILABLE DATA FIELDS:")
    print("-" * 60)
    if candles:
        sample = candles[0]
        print(f"  Timestamp:    {sample.ts}")
        print(f"  Open:         ${sample.open}")
        print(f"  High:         ${sample.high}")
        print(f"  Low:          ${sample.low}")
        print(f"  Close:        ${sample.close}")
        print(f"  Volume:       {sample.volume:,}")
        print(f"  VWAP:         ${sample.vwap}")
        print(f"  Trade Count:  {sample.trade_count:,}")
        print(f"  Source:       {sample.source}")
        print(f"  Adjusted:     {sample.is_adjusted}")

    # 4. Show what you can do with this data
    print("\n💡 WHAT YOU CAN DO:")
    print("-" * 60)
    print("  1. Calculate technical indicators (SMA, EMA, RSI, MACD)")
    print("  2. Detect trading patterns (support/resistance, trends)")
    print("  3. Generate trading signals (breakouts, reversals)")
    print("  4. Backtest strategies")
    print("  5. Real-time monitoring and alerts")
    print("  6. Volume analysis")
    print("  7. Price action analysis")

    # 5. Show sample queries
    print("\n📝 EXAMPLE QUERIES:")
    print("-" * 60)
    print("  # Get latest 20 candles for AAPL")
    print("  candles = await candle_repo.get_candles(symbol_id=1, timeframe='5m', limit=20)")
    print()
    print("  # Get candles for specific date range")
    print("  candles = await candle_repo.get_candles_by_date_range(")
    print("      symbol_id=1,")
    print("      timeframe='5m',")
    print("      from_date='2025-11-05',")
    print("      to_date='2025-11-06'")
    print("  )")
    print()
    print("  # Calculate simple moving average")
    print("  prices = [c.close for c in candles[-20:]]")
    print("  sma_20 = sum(prices) / len(prices)")

    # Cleanup
    await BaseRepository.close_pool()

    print("\n" + "=" * 60)
    print("Explore complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(explore_data())
