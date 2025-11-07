#!/usr/bin/env python3
"""
Fetch data for all tickers in the watch list.
"""
import asyncio
from datetime import datetime, timedelta

from market_data.config import get_config
from market_data.client import MassiveClient
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.base_repository import BaseRepository
from market_data.services.data_service import DataService


async def fetch_all():
    """Fetch data for all tickers in watch list"""

    print("=" * 60)
    print("FETCHING ALL WATCH LIST TICKERS")
    print("=" * 60)

    # Initialize
    config = get_config()
    massive_client = MassiveClient(config)

    await BaseRepository.create_pool(config)

    symbol_repo = SymbolRepository(config)
    candle_repo = CandleRepository(config)
    data_service = DataService(massive_client, symbol_repo, candle_repo, config)

    # Get date range (last 2 days)
    to_date = datetime.now().strftime('%Y-%m-%d')
    from_date = (datetime.now() - timedelta(days=2)).strftime('%Y-%m-%d')

    print(f"\nFetching data from {from_date} to {to_date}")
    print(f"Timeframe: 5m")
    print(f"Tickers: {len(config.tickers.watch_list)}\n")

    # Fetch each ticker
    results = []
    for i, ticker in enumerate(config.tickers.watch_list, 1):
        try:
            print(f"[{i}/{len(config.tickers.watch_list)}] Fetching {ticker}...", end=" ", flush=True)

            count = await data_service.fetch_and_store_candles(
                ticker=ticker,
                timeframe="5m",
                from_date=from_date,
                to_date=to_date
            )

            print(f"✓ {count} candles")
            results.append((ticker, count, True))

        except Exception as e:
            print(f"✗ Error: {e}")
            results.append((ticker, 0, False))

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    successful = [r for r in results if r[2]]
    failed = [r for r in results if not r[2]]
    total_candles = sum(r[1] for r in successful)

    print(f"\nSuccessful: {len(successful)}/{len(results)}")
    print(f"Total candles: {total_candles:,}")

    if failed:
        print(f"\nFailed tickers: {', '.join(r[0] for r in failed)}")

    print("\n" + "=" * 60)
    print("✅ Complete! Run explore_data.py to see what you have.")
    print("=" * 60)

    # Cleanup
    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(fetch_all())
