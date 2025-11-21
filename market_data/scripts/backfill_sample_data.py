"""
One-off backfill script to seed candles for a sample of tickers.

Defaults:
    - Pull up to 600 US tickers from Massive.
    - Fetch the last 7 calendar days per selected timeframe.
    - Timeframes default to config.timeframes but can be overridden.

Usage examples:
    python -m market_data.scripts.backfill_sample_data
    python -m market_data.scripts.backfill_sample_data --limit 200 --days 5 --timeframes 15m 1h
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List

from massive import RESTClient

from market_data.client import MassiveClient
from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.services.data_service import DataService
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Backfill sample candles for a set of tickers.")
    parser.add_argument("--limit", type=int, default=600, help="Number of tickers to pull (default: 600)")
    parser.add_argument("--days", type=int, default=7, help="Number of calendar days to backfill (default: 7)")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        help="Timeframes to backfill (default: config.timeframes)",
    )
    return parser.parse_args()


def pick_tickers(rest_client: RESTClient, limit: int) -> List[str]:
    """
    Fetch a list of US tickers from Massive, capped at limit.
    """
    tickers: List[str] = []
    iterator = rest_client.list_tickers(
        market="stocks",
        active=True,
        type="CS",
        order="asc",
        sort="ticker",
        params={"perpage": 1000, "locale": "us"},
    )
    for item in iterator:
        ticker = (item.ticker or "").upper()
        if not ticker:
            continue
        tickers.append(ticker)
        if len(tickers) >= limit:
            break
    return tickers


async def backfill(limit: int, days: int, timeframes: List[str]):
    config = get_config()
    rest_client = RESTClient(api_key=config.massive_api_key, base=config.massive.base_url.rstrip("/"))
    tickers = pick_tickers(rest_client, limit)
    if not tickers:
        logger.error("No tickers fetched; aborting backfill.")
        return

    logger.info("Backfilling %s tickers across timeframes %s for last %s days", len(tickers), timeframes, days)

    symbol_repo = SymbolRepository(config)
    candle_repo = CandleRepository(config)
    data_service = DataService(
        massive_client=MassiveClient(config),
        symbol_repo=symbol_repo,
        candle_repo=candle_repo,
        config=config,
    )

    to_date = datetime.now(timezone.utc).date()
    from_date = (to_date - timedelta(days=days)).isoformat()
    to_date_str = to_date.isoformat()

    total = 0
    for ticker in tickers:
        for timeframe in timeframes:
            try:
                count = await data_service.fetch_and_store_candles(
                    ticker=ticker,
                    timeframe=timeframe,
                    from_date=from_date,
                    to_date=to_date_str,
                )
                total += count
            except Exception as exc:
                logger.warning("Backfill error for %s %s: %s", ticker, timeframe, exc)

    logger.info("Backfill complete. Candles stored: %s", total)
    await BaseRepository.close_pool()


def main():
    args = parse_args()
    config = get_config()
    timeframes = args.timeframes or config.timeframes
    asyncio.run(backfill(limit=args.limit, days=args.days, timeframes=timeframes))


if __name__ == "__main__":
    main()
