"""
Import tickers from a text file (first column per line) into a manual watchlist table.

Assumptions:
- Input file has one row per stock, fields separated by whitespace or tabs.
- Ticker is the first token on each line.

Usage:
    python -m market_data.scripts.manual_data.import_tickers --file dec-1-stocks.txt
"""
from __future__ import annotations

import argparse
from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Import tickers from a text file into manual_watchlist.")
    parser.add_argument("--file", required=True, help="Path to the text file with tickers (ticker is first token per line).")
    parser.add_argument("--as-of", help="Optional as_of date label (e.g., 2024-12-01). Defaults to today.")
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
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split()
            ticker = parts[0].upper()
            tickers.append(ticker)
    return tickers


async def main():
    args = parse_args()
    config = get_config()
    repo = BaseRepository(config)

    await ensure_table(repo)

    tickers = extract_tickers(args.file)
    if not tickers:
        logger.error("No tickers found in file: %s", args.file)
        return

    count = await upsert_tickers(repo, tickers, args.as_of)
    logger.info("Imported %s tickers into manual_watchlist", count)
    await BaseRepository.close_pool()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
