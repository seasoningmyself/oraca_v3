"""
Minute-by-minute ingestion loop:
  - Checks recency and backfills gaps (1-day window) for target timeframes.
  - Triggers scanners after ingest.
  - Optionally prunes old candles (run separately/daily).

Usage:
    PYTHONPATH=. python3 -m market_data.scripts.run_ingestion_loop --timeframes 15m --recency-minutes 120 --retention-days 2 --tickers T1 T2 ...
"""
from __future__ import annotations

import argparse
import asyncio
import time

from market_data.services.ingestion_service import IngestionService


def parse_args():
    parser = argparse.ArgumentParser(description="Run ingestion loop (fetch, backfill gaps, scan).")
    parser.add_argument("--timeframes", nargs="+", default=["15m"], help="Timeframes to ingest (default: 15m)")
    parser.add_argument("--recency-minutes", type=int, default=120, help="If latest bar older than this, backfill (default: 120)")
    parser.add_argument("--retention-days", type=int, default=2, help="Retention window for pruning (default: 2 days)")
    parser.add_argument("--interval-seconds", type=int, default=900, help="Loop interval seconds (default: 900 = 15m)")
    parser.add_argument("--tickers", nargs="+", help="Optional explicit tickers (default: ACTIVE universe)")
    parser.add_argument("--once", action="store_true", help="Run a single ingestion + scan and exit")
    parser.add_argument("--prune", action="store_true", help="Prune after ingestion (defaults to False)")
    return parser.parse_args()


async def main():
    args = parse_args()
    service = IngestionService(
        timeframes=args.timeframes,
        recency_minutes=args.recency_minutes,
        retention_days=args.retention_days,
        tickers=args.tickers,
    )

    async def run_once():
        await service.refresh_once()
        if args.prune:
            await service.prune()

    if args.once:
        await run_once()
    else:
        while True:
            start = time.time()
            await run_once()
            elapsed = time.time() - start
            sleep_for = max(args.interval_seconds - elapsed, 0)
            await asyncio.sleep(sleep_for)

    await service.close()


if __name__ == "__main__":
    asyncio.run(main())
