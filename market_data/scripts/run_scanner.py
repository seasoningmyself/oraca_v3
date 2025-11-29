"""
Run a detector + scorer over a timeframe.

Usage:
    python -m market_data.scripts.run_scanner --detector breakout20 --timeframe 15m --tickers AAPL MSFT
"""
from __future__ import annotations

import argparse
import asyncio

from market_data.client import MassiveClient
from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.signal_repository import SignalRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.scanners.breakout20 import Breakout20Scanner
from market_data.scanners.grail import GrailScanner
from market_data.scanners.black_reign import BlackReignScanner
from market_data.scanners.scorer import (
    breakout20_score,
    grail_score,
    blackreign_score,
)
from market_data.scanners.interfaces import Scorer, Detection
from market_data.services.scan_service import ScanService
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


class Breakout20Scorer(Scorer):
    def score(self, detection: Detection) -> float:
        f = detection.features
        return breakout20_score(
            breakout=f.get("close") / f.get("hhv10") - 1 if f.get("hhv10") else 0,
            rel_vol=f.get("rel_vol_20"),
            rsi=f.get("rsi14"),
            macd_hist=f.get("macd_hist"),
            bb_pct=f.get("bb_pct"),
            atrp=f.get("atrp"),
            multitf=f.get("multitfconfirmation", 0),
        )


class GrailScorer(Scorer):
    def score(self, detection: Detection) -> float:
        f = detection.features
        return grail_score(
            close=f.get("price"),
            r1=f.get("r1"),
            bb_width=f.get("bb_width"),
            bb_width_thresh=f.get("bb_width_thresh") or 0.05,
            rel_vol_20=f.get("rel_vol_20"),
            trend_bits=[
                1 if f.get("trend_d") else 0,
                1 if f.get("trend_h4") else 0,
                1 if f.get("trend_h1") else 0,
                1 if f.get("trend_m15") else 0,
            ],
            macd_hist=f.get("macd_hist"),
            macd_hist_prev1=f.get("macd_hist_prev1"),
            macd_hist_prev2=f.get("macd_hist_prev2"),
            rsi=f.get("rsi14"),
            atrp=f.get("atrp"),
        )


class BlackReignScorer(Scorer):
    def score(self, detection: Detection) -> float:
        f = detection.features
        return blackreign_score(
            trend_macro=bool(f.get("trend_macro")),
            dist20=f.get("dist20") or 0,
            dist50=f.get("dist50") or 0,
            rel_vol_20=f.get("rel_vol_20"),
            rsi=f.get("rsi14"),
            macd_hist=f.get("macd_hist"),
            macd_hist_prev=f.get("macd_hist_prev"),
            reentry_flag=bool(f.get("reentry_flag")),
            ma_reclaim_flag=bool(f.get("ma_reclaim_flag")),
            atrp=f.get("atrp"),
        )


def parse_args():
    parser = argparse.ArgumentParser(description="Run scanner(s) over tickers/timeframe.")
    parser.add_argument("--detector", default="breakout20", help="Detector to run (default: breakout20)")
    parser.add_argument("--timeframe", default="15m", help="Timeframe to scan (default: 15m)")
    parser.add_argument("--history-limit", type=int, default=400, help="History bars to load (detector-specific)")
    parser.add_argument("--tickers", nargs="+", help="Tickers to scan (default: ACTIVE universe)")
    return parser.parse_args()


async def main():
    args = parse_args()
    config = get_config()

    # Repos/services
    candle_repo = CandleRepository(config)
    signal_repo = SignalRepository(config)
    symbol_repo = SymbolRepository(config)
    universe_repo = UniverseRepository(config)
    massive_client = MassiveClient(config)

    # Detector selection
    if args.detector == "breakout20":
        detector = Breakout20Scanner(
            candle_repo=candle_repo,
            massive_client=massive_client,
            history_limit=args.history_limit,
        )
        scorer = Breakout20Scorer()
    elif args.detector == "grail":
        detector = GrailScanner(
            candle_repo=candle_repo,
            massive_client=massive_client,
            history_limit=args.history_limit,
        )
        scorer = Breakout20Scorer()  # reuse simple scoring until a custom one is defined
    elif args.detector == "blackreign":
        detector = BlackReignScanner(
            candle_repo=candle_repo,
            base_timeframe=args.timeframe,
            history_limit=args.history_limit,
        )
        scorer = Breakout20Scorer()  # placeholder scorer
    else:
        raise ValueError(f"Unknown detector: {args.detector}")

    scan_service = ScanService(
        symbol_repo=symbol_repo,
        universe_repo=universe_repo,
        signal_repo=signal_repo,
        candle_repo=candle_repo,
    )
    count = await scan_service.run(
        detector=detector,
        scorer=scorer,
        timeframe=args.timeframe,
        tickers=args.tickers,
    )
    logger.info("Stored %s signals", count)
    await BaseRepository.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
