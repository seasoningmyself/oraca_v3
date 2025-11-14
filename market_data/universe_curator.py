"""
CLI entry point for running the universe curator job.
"""
import asyncio
from pprint import pprint

from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.services.universe_curator import UniverseCurator
from market_data.utils.logger import get_logger


async def main():
    logger = get_logger(__name__)
    config = get_config()
    curator = UniverseCurator(config)
    summary = await curator.refresh()
    logger.info("Universe curator summary: %s", summary)
    pprint(summary)
    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
