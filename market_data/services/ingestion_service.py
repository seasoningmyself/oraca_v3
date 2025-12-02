"""
IngestionService: fetch fresh candles on a schedule, backfill gaps, trigger scanners, and prune old data.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from market_data.client import MassiveClient
from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.services.data_service import DataService
from market_data.services.scan_service import ScanService
from market_data.scanners.breakout20 import Breakout20Scanner
from market_data.scanners.grail import GrailScanner
from market_data.scanners.black_reign import BlackReignScanner
from market_data.scanners.interfaces import Scorer, Detection
from market_data.scanners.scorer import breakout20_score, grail_score, blackreign_score
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


class IngestionService:
    """
    Handles fresh data ingestion for selected timeframes, gap backfill, scanner triggers, and pruning.
    """

    def __init__(
        self,
        *,
        timeframes: List[str],
        recency_minutes: int = 120,
        retention_days: int = 2,
        tickers: Optional[List[str]] = None,
    ):
        self.config = get_config()
        self.timeframes = timeframes
        self.recency_minutes = recency_minutes
        self.retention_days = retention_days
        self.tickers_override = tickers

        self.symbol_repo = SymbolRepository(self.config)
        self.candle_repo = CandleRepository(self.config)
        self.universe_repo = UniverseRepository(self.config)
        self.data_service = DataService(
            massive_client=MassiveClient(self.config),
            symbol_repo=self.symbol_repo,
            candle_repo=self.candle_repo,
            config=self.config,
        )
        self.scan_service = ScanService(
            symbol_repo=self.symbol_repo,
            universe_repo=self.universe_repo,
            signal_repo=SignalRepository(self.config),
            candle_repo=self.candle_repo,
        )

    async def get_tickers(self) -> List[str]:
        if self.tickers_override:
            return self.tickers_override
        entries = await self.universe_repo.list_by_status(["ACTIVE"])
        return [u.ticker for u in entries]

    async def refresh_once(self):
        tickers = await self.get_tickers()
        now_utc = datetime.now(timezone.utc)
        recency_cutoff = now_utc - timedelta(minutes=self.recency_minutes)

        total_candles = 0
        for t in tickers:
            for tf in self.timeframes:
                latest = await self.candle_repo.get_latest_candle_for_symbol(t, tf) if hasattr(self.candle_repo, "get_latest_candle_for_symbol") else None
                needs_backfill = True
                if latest and latest.ts >= recency_cutoff:
                    needs_backfill = False
                if needs_backfill:
                    to_date = now_utc.date()
                    from_date = (to_date - timedelta(days=1)).isoformat()
                    to_date_str = to_date.isoformat()
                    try:
                        count = await self.data_service.fetch_and_store_candles(
                            ticker=t,
                            timeframe=tf,
                            from_date=from_date,
                            to_date=to_date_str,
                        )
                        total_candles += count
                    except Exception as exc:
                        logger.warning("Backfill error for %s %s: %s", t, tf, exc)

        logger.info("Ingestion complete: candles stored %s", total_candles)
        await self.run_scanners(tickers)

    async def run_scanners(self, tickers: List[str]):
        # Run detectors sequentially; can be optimized later
        # Breakout20
        bdet = Breakout20Scanner(
            candle_repo=self.candle_repo,
            massive_client=MassiveClient(self.config),
            history_limit=400,
        )
        bscore = Breakout20Scorer()
        await self.scan_service.run(detector=bdet, scorer=bscore, timeframe="15m", tickers=tickers)

        # Grail
        gdet = GrailScanner(
            candle_repo=self.candle_repo,
            massive_client=MassiveClient(self.config),
            history_limit=200,
        )
        gscore = GrailScorer()
        await self.scan_service.run(detector=gdet, scorer=gscore, timeframe="15m", tickers=tickers)

        # Black Reign
        brdet = BlackReignScanner(
            candle_repo=self.candle_repo,
            base_timeframe="15m",
            history_limit=240,
        )
        brscore = BlackReignScorer()
        await self.scan_service.run(detector=brdet, scorer=brscore, timeframe="15m", tickers=tickers)

    async def prune(self):
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        tickers = await self.get_tickers()
        deleted = 0
        for t in tickers:
            sym = await self.symbol_repo.get_by_ticker(t)
            if not sym:
                continue
            for tf in self.timeframes:
                try:
                    deleted += await self.candle_repo.delete_older_than(sym.id, tf, cutoff)
                except Exception as exc:
                    logger.warning("Prune error for %s %s: %s", t, tf, exc)
        logger.info("Prune complete: rows deleted %s", deleted)

    async def close(self):
        await BaseRepository.close_pool()
