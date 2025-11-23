#!/usr/bin/env python3
"""
Quick smoke-test that prints the current price for five flagship tech stocks
using Polygon.io (via the Massive client wrapper already in this repo).
"""

import asyncio
from datetime import timezone
from typing import List, Optional

from market_data.client import MassiveClient
from market_data.config import get_config


TECH_STOCKS: List[str] = ["AAPL", "MSFT", "GOOGL", "NVDA", "META"]


async def fetch_price(client: MassiveClient, ticker: str) -> Optional[dict]:
    """Fetch the latest trade for a single ticker."""
    return await client.get_latest_price(ticker)


async def main() -> None:
    """Load config, fetch prices in parallel, and print the snapshot."""
    config = get_config()
    client = MassiveClient(config)

    print("=" * 60)
    print("Polygon.io Price Snapshot • Top Tech Names")
    print("=" * 60)
    print("Ticker    Price      Last Update (exchange timestamp)")
    print("-" * 60)

    # Fetch all tickers concurrently to minimize total runtime.
    results = await asyncio.gather(
        *(fetch_price(client, ticker) for ticker in TECH_STOCKS),
        return_exceptions=True,
    )

    for ticker, result in zip(TECH_STOCKS, results):
        if isinstance(result, Exception):
            print(f"{ticker:>5}    error     {result}")
            continue

        if not result or result.get("price") is None:
            print(f"{ticker:>5}    n/a       (no trade returned)")
            continue

        price = float(result["price"])
        timestamp = result["timestamp"].astimezone(timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S UTC"
        )
        exchange = result.get("exchange") or "unknown"
        print(f"{ticker:>5}    ${price:>7.2f}  {timestamp} ({exchange})")

    print("-" * 60)
    print("Note: Requires MASSIVE_II_API_KEY (Polygon) to be set in your env.")


if __name__ == "__main__":
    asyncio.run(main())

