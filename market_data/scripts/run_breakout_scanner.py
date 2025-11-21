"""
Run the breakout20_v1 scanner over a recent window.

Usage:
    python -m market_data.scripts.run_breakout_scanner --timeframe 15m --history-limit 400 --tickers AAPL MSFT
    python -m market_data.scripts.run_breakout_scanner --timeframe 15m  (uses ACTIVE universe)
"""
from __future__ import annotations

import argparse
import asyncio

from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.signal_repository import SignalRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.scanners.breakout20 import Breakout20Scanner
from market_data.client import MassiveClient
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Run breakout20_v1 scanner.")
    parser.add_argument("--timeframe", default="15m", help="Timeframe to scan (default: 15m)")
    parser.add_argument(
        "--history-limit",
        type=int,
        default=400,
        help="Number of most-recent bars to load (default: 400)",
    )
    parser.add_argument(
        "--tickers",
        nargs="+",
        help="Specific tickers to scan (default: ACTIVE universe)",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    config = get_config()
    candle_repo = CandleRepository(config)
    signal_repo = SignalRepository(config)
    symbol_repo = SymbolRepository(config)
    universe_repo = UniverseRepository(config)
    massive_client = MassiveClient(config)

    scanner = Breakout20Scanner(
        candle_repo=candle_repo,
        signal_repo=signal_repo,
        symbol_repo=symbol_repo,
        universe_repo=universe_repo,
        massive_client=massive_client,
        history_limit=args.history_limit,
    )
    count = await scanner.run_for_timeframe(args.timeframe, tickers=args.tickers)
    logger.info("Scanner finished: %s signals stored", count)
    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
