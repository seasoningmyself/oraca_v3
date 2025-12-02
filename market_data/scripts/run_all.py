"""
Run the full daily + intraday flow with sane defaults:
  - Pre-market prep: refresh universe, backfill stale/missing bars, prune retention window.
  - Start the intraday ingestion loop: fetch/append minute data, trigger scanners, prune if desired.

Usage:
    PYTHONPATH=. python3 -m market_data.scripts.run_all

Flags:
    --timeframes ...      (default: 15m)
    --recency-minutes ... (default: 120)
    --retention-days ...  (default: 2)
    --interval-seconds .. (default: 60)
    --prune               (prune during loop)
"""
from __future__ import annotations

import argparse
import asyncio
import time

from market_data.scripts import premarket_prep
from market_data.services.ingestion_service import IngestionService


def parse_args():
    parser = argparse.ArgumentParser(description="Run premarket prep + ingestion loop with defaults.")
    parser.add_argument("--timeframes", nargs="+", default=["15m"])
    parser.add_argument("--recency-minutes", type=int, default=120)
    parser.add_argument("--retention-days", type=int, default=2)
    parser.add_argument("--interval-seconds", type=int, default=60)
    parser.add_argument("--prune", action="store_true", help="Prune during the loop")
    return parser.parse_args()


async def run_loop(args):
    service = IngestionService(
        timeframes=args.timeframes,
        recency_minutes=args.recency_minutes,
        retention_days=args.retention_days,
    )

    async def run_once():
        await service.refresh_once()
        if args.prune:
            await service.prune()

    while True:
        start = time.time()
        await run_once()
        elapsed = time.time() - start
        sleep_for = max(args.interval_seconds - elapsed, 0)
        await asyncio.sleep(sleep_for)


def main():
    args = parse_args()
    # Run premarket prep (refresh universe, backfill/prune) once
    asyncio.run(premarket_prep.main())
    # Start the loop
    asyncio.run(run_loop(args))


if __name__ == "__main__":
    main()
