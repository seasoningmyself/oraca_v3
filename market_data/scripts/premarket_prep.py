"""
Pre-market prep script:
  - Refresh the curated universe (price/float filters).
  - Identify active tickers (optionally limited).
  - Check candle recency; backfill missing/stale data for selected timeframes.
  - Optionally prune candles older than a retention window.

Usage examples:
  python -m market_data.scripts.premarket_prep --timeframes 15m 1h --days-back 7 --recency-hours 12 --retention-days 7
  python -m market_data.scripts.premarket_prep --limit 200 --prune
"""
from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set

from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.services.data_service import DataService
from market_data.services.universe_curator import UniverseCurator
from market_data.client import MassiveClient
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Pre-market prep: build universe and backfill recent candles.")
    parser.add_argument("--limit", type=int, help="Limit number of tickers (for testing).")
    parser.add_argument(
        "--timeframes",
        nargs="+",
        help="Timeframes to backfill (default: config.timeframes)",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=7,
        help="How many calendar days to backfill (default: 7)",
    )
    parser.add_argument(
        "--recency-hours",
        type=int,
        default=12,
        help="If latest candle is older than this, trigger backfill (default: 12 hours)",
    )
    parser.add_argument(
        "--retention-days",
        type=int,
        default=0,
        help="If >0 and --prune is set, delete candles older than this many days",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Prune candles older than retention-days",
    )
    return parser.parse_args()


async def refresh_universe(config, limit: Optional[int]) -> List[str]:
    curator = UniverseCurator(config)
    summary = await curator.refresh()
    logger.info("Universe refresh summary: %s", summary)
    universe_repo = UniverseRepository(config)
    entries = await universe_repo.list_by_status(["ACTIVE"])
    tickers = [u.ticker for u in entries]
    if limit:
        tickers = tickers[:limit]
    return tickers


async def ensure_history(
    config,
    tickers: List[str],
    timeframes: List[str],
    days_back: int,
    recency_hours: int,
    retention_days: int,
    prune: bool,
):
    symbol_repo = SymbolRepository(config)
    candle_repo = CandleRepository(config)
    data_service = DataService(
        massive_client=MassiveClient(config),
        symbol_repo=symbol_repo,
        candle_repo=candle_repo,
        config=config,
    )

    backfill_from = (datetime.now(timezone.utc) - timedelta(days=days_back)).date().isoformat()
    backfill_to = datetime.now(timezone.utc).date().isoformat()
    recency_cutoff = datetime.now(timezone.utc) - timedelta(hours=recency_hours)
    prune_cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days) if prune and retention_days > 0 else None

    seen_new: Set[str] = set()
    total_candles = 0

    for ticker in tickers:
        symbol = await symbol_repo.get_or_create(ticker, None)
        for tf in timeframes:
            latest = await candle_repo.get_latest_candle(symbol.id, tf)
            needs_backfill = latest is None or latest.ts < recency_cutoff
            if needs_backfill:
                try:
                    count = await data_service.fetch_and_store_candles(
                        ticker=ticker,
                        timeframe=tf,
                        from_date=backfill_from,
                        to_date=backfill_to,
                    )
                    total_candles += count
                    seen_new.add(ticker)
                    logger.info("Backfilled %s %s: %s candles", ticker, tf, count)
                except Exception as exc:
                    logger.warning("Backfill error for %s %s: %s", ticker, tf, exc)
            if prune_cutoff:
                deleted = await candle_repo.delete_older_than(symbol.id, tf, prune_cutoff)
                if deleted:
                    logger.info("Pruned %s old candles for %s %s", deleted, ticker, tf)

    logger.info("Backfill complete. Candles stored: %s. Tick-processed: %s", total_candles, len(tickers))
    if seen_new:
        logger.info("Tickers backfilled (missing/stale): %s", ", ".join(sorted(seen_new)))


async def main():
    args = parse_args()
    config = get_config()
    timeframes = args.timeframes or config.timeframes

    tickers = await refresh_universe(config, args.limit)
    logger.info("Active universe size: %s", len(tickers))

    await ensure_history(
        config=config,
        tickers=tickers,
        timeframes=timeframes,
        days_back=args.days_back,
        recency_hours=args.recency_hours,
        retention_days=args.retention_days,
        prune=args.prune,
    )
    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
