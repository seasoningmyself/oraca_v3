"""
Filter manual_watchlist tickers by price and volume using Massive daily candles.

Criteria:
  - Close between price_min and price_max (default: 0.40–50)
  - Daily volume >= min_volume (default: 40,000)

This fetches the latest daily candle (last 2 calendar days window) per ticker.
Outputs counts and matching tickers.

Usage:
  PYTHONPATH=. python3 -m market_data.scripts.manual_data.filter_manual_watchlist
    --price-min 0.4 --price-max 50 --min-volume 40000 --days 2
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta
from typing import List

from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.client import MassiveClient
from market_data.services.data_service import DataService
from market_data.repositories.candle_repository import CandleRepository
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Filter manual_watchlist by price/volume using Massive daily candles.")
    parser.add_argument("--price-min", type=float, default=0.40)
    parser.add_argument("--price-max", type=float, default=50.0)
    parser.add_argument("--min-volume", type=int, default=40000)
    parser.add_argument("--days", type=int, default=2, help="Lookback window in calendar days for daily candle fetch")
    parser.add_argument("--limit", type=int, help="Limit number of tickers processed (for testing)")
    return parser.parse_args()


async def get_manual_tickers(repo: BaseRepository, limit: int | None) -> List[str]:
    query = "SELECT ticker FROM manual_watchlist ORDER BY ticker"
    if limit:
        query += f" LIMIT {limit}"
    rows = await repo.fetch(query)
    return [row["ticker"] for row in rows]


async def fetch_daily_close_volume(data_service: DataService, ticker: str, days: int):
    # Use last N days to find the most recent daily candle
    to_date = datetime.utcnow().date()
    from_date = to_date - timedelta(days=days)
    candles = await data_service.fetch_and_store_candles(
        ticker=ticker,
        timeframe="1d",
        from_date=from_date.isoformat(),
        to_date=to_date.isoformat(),
    )
    # fetch_and_store_candles returns count; we need the latest candle from DB
    symbol = await data_service.symbol_repo.get_by_ticker(ticker)
    if not symbol:
        return None, None
    latest = await data_service.candle_repo.get_latest_candle(symbol.id, "1d")
    if not latest:
        return None, None
    return float(latest.close), int(latest.volume or 0)


async def main():
    args = parse_args()
    config = get_config()

    base_repo = BaseRepository(config)
    tickers = await get_manual_tickers(base_repo, args.limit)
    logger.info("Manual tickers to process: %s", len(tickers))

    data_service = DataService(
        massive_client=MassiveClient(config),
        symbol_repo=SymbolRepository(config),
        candle_repo=CandleRepository(config),
        config=config,
    )

    matches = []
    for ticker in tickers:
        try:
            close, vol = await fetch_daily_close_volume(data_service, ticker, args.days)
        except Exception as exc:
            logger.warning("Fetch error for %s: %s", ticker, exc)
            continue
        if close is None or vol is None:
            continue
        if args.price_min <= close <= args.price_max and vol >= args.min_volume:
            matches.append((ticker, close, vol))

    print(f"Tickers processed: {len(tickers)}")
    print(f"Matches (price {args.price_min}-{args.price_max}, volume>={args.min_volume}): {len(matches)}")
    for t, c, v in matches:
        print(f"{t}\tclose={c}\tvolume={v}")

    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
