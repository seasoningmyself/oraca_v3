#!/usr/bin/env python3
"""
Hourly Top Tech Stocks Monitor
Fetches data for top 4 tech stocks and sends performance to Discord
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
from market_data.client import MassiveClient
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.services.data_service import DataService

# Top 5 tech stocks
TOP_TECH_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]


async def calculate_24h_performance(candle_repo: CandleRepository, symbol_id: int, ticker: str) -> Optional[Dict]:
    """Calculate 24-hour performance for a stock."""
    candles = await candle_repo.get_candles(
        symbol_id=symbol_id,
        timeframe="5m",
        limit=500
    )

    if not candles or len(candles) < 2:
        return None

    current_candle = candles[0]
    current_price = current_candle.close
    target_time = current_candle.ts - timedelta(hours=24)

    # Find closest candle to 24h ago
    closest_candle = min(candles, key=lambda c: abs(c.ts - target_time))
    price_24h_ago = closest_candle.close

    price_change = current_price - price_24h_ago
    price_change_pct = (price_change / price_24h_ago) * Decimal('100')
    total_volume = sum(c.volume for c in candles)

    return {
        'ticker': ticker,
        'current_price': float(current_price),
        'price_24h_ago': float(price_24h_ago),
        'price_change': float(price_change),
        'price_change_pct': float(price_change_pct),
        'total_volume': int(total_volume),
    }


async def main():
    """Fetch latest data for top 5 tech stocks and send performance to Discord"""
    print(f"[{datetime.now()}] Starting hourly top tech monitor...")

    # Initialize configs
    market_config = get_market_config()
    bot_config = get_bot_config()

    # Create pool
    await BaseRepository.create_pool(market_config)

    # Initialize services
    massive_client = MassiveClient(market_config)
    symbol_repo = SymbolRepository(market_config)
    candle_repo = CandleRepository(market_config)
    data_service = DataService(massive_client, symbol_repo, candle_repo, market_config)

    bot_client = BotClient(bot_config)
    message_service = MessageService(bot_client, bot_config)

    # Start bot
    bot_task = asyncio.create_task(bot_client.start())
    await asyncio.sleep(3)

    try:
        # 1. Fetch latest data for top 5 tech stocks
        print(f"Fetching data for {', '.join(TOP_TECH_STOCKS)}...")
        to_date = datetime.now().strftime('%Y-%m-%d')
        from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')

        for ticker in TOP_TECH_STOCKS:
            try:
                count = await data_service.fetch_and_store_candles(
                    ticker=ticker,
                    timeframe="5m",
                    from_date=from_date,
                    to_date=to_date
                )
                print(f"  ✓ {ticker}: {count} candles")
            except Exception as e:
                print(f"  ✗ {ticker}: {e}")

        # 2. Calculate performance for all 5 stocks
        print("Calculating performance...")
        performances = []

        for ticker in TOP_TECH_STOCKS:
            symbol = await symbol_repo.get_by_ticker(ticker)
            if symbol and symbol.last_seen:
                perf = await calculate_24h_performance(candle_repo, symbol.id, ticker)
                if perf:
                    performances.append(perf)
                    print(f"  {ticker}: {perf['price_change_pct']:+.2f}%")

        if not performances:
            print("No performance data available")
            return

        # 3. Sort by performance
        performances.sort(key=lambda x: x['price_change_pct'], reverse=True)

        # 4. Create Discord embed
        fields = []
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

        for i, perf in enumerate(performances):
            indicator = "🟢" if perf['price_change_pct'] > 0 else "🔴"

            value_lines = [
                f"**Price:** ${perf['current_price']:,.2f}",
                f"**24h Change:** {indicator} {perf['price_change_pct']:+.2f}%",
                f"**Volume:** {perf['total_volume']:,}"
            ]

            fields.append({
                "name": f"{medals[i]} {perf['ticker']}",
                "value": "\n".join(value_lines),
                "inline": True
            })

        embed = discord.Embed(
            title="📊 Top Tech Stocks Performance (24h)",
            description=f"Hourly update for {len(performances)} tech stocks",
            color=0x00ff00 if performances[0]['price_change_pct'] > 0 else 0xff0000,
            timestamp=datetime.now()
        )

        for field in fields:
            embed.add_field(name=field["name"], value=field["value"], inline=field["inline"])

        embed.set_footer(text="Automated Hourly Report • Data from Polygon.io")

        # 5. Send to Discord
        await message_service.send_alert(message="", embed=embed)
        print(f"✓ Sent to Discord at {datetime.now()}")

    finally:
        # Cleanup
        await BaseRepository.close_pool()
        await bot_client.close()
        await bot_task


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
