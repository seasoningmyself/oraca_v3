"""
Quick utility to refresh the universe and print counts of ACTIVE tickers.
No candle fetching/backfill is performed.
"""
from __future__ import annotations

import asyncio

from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.services.universe_curator import UniverseCurator


async def main():
    config = get_config()
    curator = UniverseCurator(config)
    summary = await curator.refresh()

    universe_repo = UniverseRepository(config)
    active = await universe_repo.list_by_status(["ACTIVE"])
    print("Universe refresh summary:", summary)
    print("ACTIVE tickers:", len(active))

    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
