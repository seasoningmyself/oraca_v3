"""
Import tickers from a CSV file into manual_watchlist.

Assumptions:
 - CSV file, ticker is the first column on each row.
 - Optional truncate to replace the table contents.

Usage:
  PYTHONPATH=. python3 -m market_data.scripts.manual_data.import_watchlist_csv \
    --file market_data/manual_data/2025-12-02-WatchListScanner.csv --truncate
"""
from __future__ import annotations

import argparse
import asyncio
import csv
from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Import tickers from CSV into manual_watchlist.")
    parser.add_argument("--file", required=True, help="Path to CSV file (ticker in first column).")
    parser.add_argument("--as-of", help="Optional as_of date label (e.g., 2024-12-01). Defaults to today.")
    parser.add_argument("--truncate", action="store_true", help="Truncate manual_watchlist before import.")
    return parser.parse_args()


async def ensure_table(repo: BaseRepository):
    query = """
    CREATE TABLE IF NOT EXISTS manual_watchlist (
        ticker TEXT PRIMARY KEY,
        as_of DATE DEFAULT CURRENT_DATE,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    """
    await repo.execute(query)


async def truncate_table(repo: BaseRepository):
    await repo.execute("TRUNCATE TABLE manual_watchlist;")


async def upsert_tickers(repo: BaseRepository, tickers, as_of: str | None):
    query = """
    INSERT INTO manual_watchlist (ticker, as_of)
    VALUES ($1, COALESCE($2::date, CURRENT_DATE))
    ON CONFLICT (ticker) DO UPDATE
    SET as_of = COALESCE($2::date, manual_watchlist.as_of),
        created_at = NOW();
    """
    count = 0
    for t in tickers:
        await repo.execute(query, t, as_of)
        count += 1
    return count


def extract_tickers(path: str):
    tickers = []
    with open(path, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row or not row[0].strip():
                continue
            tickers.append(row[0].strip().upper())
    return tickers


async def main():
    args = parse_args()
    config = get_config()
    repo = BaseRepository(config)

    await ensure_table(repo)

    if args.truncate:
        await truncate_table(repo)

    tickers = extract_tickers(args.file)
    if not tickers:
        logger.error("No tickers found in file: %s", args.file)
        return

    count = await upsert_tickers(repo, tickers, args.as_of)
    logger.info("Imported %s tickers into manual_watchlist", count)
    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
