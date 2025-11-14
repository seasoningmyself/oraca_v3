import asyncio
from market_data.config import get_config
from market_data.services.universe_curator import UniverseCurator

async def main():
    curator = UniverseCurator(get_config())
    tickers = await asyncio.to_thread(curator._fetch_ticker_metadata)
    snapshots = await asyncio.to_thread(curator._fetch_price_snapshots)
    print("metadata count:", len(tickers))
    print("snapshot count:", len(snapshots))

asyncio.run(main())