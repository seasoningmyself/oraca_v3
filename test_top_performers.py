#!/usr/bin/env python3
"""
Test: Calculate top 3 performers over 24 hours and send to Discord.
"""
import asyncio
import discord
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional

# Bot imports
from bot.config import get_config as get_bot_config
from bot.bot_client import BotClient
from bot.services.message_service import MessageService

# Market data imports
from market_data.config import get_config as get_market_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.models.candle import Candle


async def calculate_24h_performance(candle_repo: CandleRepository, symbol_id: int, ticker: str) -> Optional[Dict]:
    """
    Calculate 24-hour performance for a stock.

    Returns:
        Dict with ticker, price_change_pct, current_price, price_24h_ago, volume
    """
    # Get all candles for this symbol (5m timeframe)
    candles = await candle_repo.get_candles(
        symbol_id=symbol_id,
        timeframe="5m",
        limit=500  # ~2 days of 5-min candles
    )

    if not candles or len(candles) < 2:
        return None

    # Candles are ordered by timestamp DESC (newest first)
    current_candle = candles[0]
    current_price = current_candle.close

    # Find candle from ~24 hours ago
    # 24 hours = 288 five-minute candles
    # But we may have gaps (after hours, weekends), so look for closest
    target_time = current_candle.ts - timedelta(hours=24)

    # Find closest candle to 24h ago
    closest_candle = None
    min_diff = timedelta(days=999)

    for candle in candles:
        diff = abs(candle.ts - target_time)
        if diff < min_diff:
            min_diff = diff
            closest_candle = candle

    if not closest_candle:
        return None

    price_24h_ago = closest_candle.close

    # Calculate percentage change
    price_change = current_price - price_24h_ago
    price_change_pct = (price_change / price_24h_ago) * Decimal('100')

    # Calculate total volume over period
    total_volume = sum(c.volume for c in candles)

    return {
        'ticker': ticker,
        'current_price': float(current_price),
        'price_24h_ago': float(price_24h_ago),
        'price_change': float(price_change),
        'price_change_pct': float(price_change_pct),
        'total_volume': int(total_volume),
        'period_hours': min_diff.total_seconds() / 3600  # Actual hours measured
    }


async def test_top_performers():
    """Test: Calculate and send top 3 performers to Discord"""

    print("=" * 60)
    print("TOP PERFORMERS TEST")
    print("=" * 60)

    # Initialize market data
    market_config = get_market_config()
    await BaseRepository.create_pool(market_config)

    symbol_repo = SymbolRepository(market_config)
    candle_repo = CandleRepository(market_config)

    # Initialize bot
    bot_config = get_bot_config()
    bot_client = BotClient(bot_config)
    message_service = MessageService(bot_client, bot_config)

    # Start bot
    bot_task = asyncio.create_task(bot_client.start())
    await asyncio.sleep(3)
    print("✓ Bot connected\n")

    # Get all symbols with data
    print("Calculating performance for all stocks...")
    symbols = await symbol_repo.list_all()

    performances = []
    for symbol in symbols:
        # Only calculate for symbols with data
        if symbol.last_seen:
            print(f"  Analyzing {symbol.ticker}...", end=" ", flush=True)
            perf = await calculate_24h_performance(candle_repo, symbol.id, symbol.ticker)

            if perf:
                performances.append(perf)
                print(f"✓ {perf['price_change_pct']:+.2f}%")
            else:
                print("✗ No data")

    if not performances:
        print("\n❌ No performance data available")
        await bot_client.close()
        await bot_task
        await BaseRepository.close_pool()
        return

    # Sort by performance (descending)
    performances.sort(key=lambda x: x['price_change_pct'], reverse=True)

    # Get top 3
    top_3 = performances[:3]

    print(f"\n✓ Top 3 performers calculated\n")

    # Format Discord message
    print("Sending to Discord...")

    # Create embed fields for top 3
    fields = []
    medals = ["🥇", "🥈", "🥉"]

    for i, perf in enumerate(top_3):
        # Color indicator
        indicator = "🟢" if perf['price_change_pct'] > 0 else "🔴"

        # Format value
        value_lines = [
            f"**Price:** ${perf['current_price']:,.2f}",
            f"**24h Change:** {indicator} {perf['price_change_pct']:+.2f}%",
            f"**Price Change:** ${perf['price_change']:+.2f}",
            f"**Volume:** {perf['total_volume']:,}"
        ]

        fields.append({
            "name": f"{medals[i]} {perf['ticker']}",
            "value": "\n".join(value_lines),
            "inline": True
        })

    # Create Discord embed
    embed = discord.Embed(
        title="📈 Top 3 Performers (24h)",
        description=f"Performance analysis for {len(performances)} stocks",
        color=0x00ff00,  # Green
        timestamp=datetime.now()
    )

    # Add fields
    for field in fields:
        embed.add_field(
            name=field["name"],
            value=field["value"],
            inline=field["inline"]
        )

    embed.set_footer(text="Data from Polygon.io via Massive")

    # Send to Discord
    await message_service.send_alert(
        message="",
        embed=embed
    )

    print("✓ Sent to Discord!")

    # Print summary to console
    print("\n" + "=" * 60)
    print("TOP 3 PERFORMERS")
    print("=" * 60)
    for i, perf in enumerate(top_3, 1):
        print(f"{i}. {perf['ticker']:6} {perf['price_change_pct']:+7.2f}%  "
              f"${perf['current_price']:9,.2f}  Vol: {perf['total_volume']:,}")
    print("=" * 60)

    # Cleanup
    await BaseRepository.close_pool()
    await bot_client.close()
    await bot_task


if __name__ == "__main__":
    asyncio.run(test_top_performers())
