"""
Scan orchestrator: runs detectors over tickers/timeframes, applies scorers, and persists signals.
"""
from __future__ import annotations

from typing import List, Optional

from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.signal_repository import SignalRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.scanners.interfaces import Detector, Scorer, Detection
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


class ScanService:
    """Coordinates detectors, scorers, and signal persistence."""

    def __init__(
        self,
        *,
        symbol_repo: SymbolRepository,
        universe_repo: UniverseRepository,
        signal_repo: SignalRepository,
        candle_repo: CandleRepository,
    ):
        self.symbols = symbol_repo
        self.universe = universe_repo
        self.signals = signal_repo
        self.candles = candle_repo

    async def run(
        self,
        detector: Detector,
        scorer: Scorer,
        timeframe: str,
        tickers: Optional[List[str]] = None,
    ) -> int:
        """
        Run a detector over a ticker set (ACTIVE universe if none provided), score, and persist.
        Returns number of signals stored.
        """
        if tickers is None:
            universe_entries = await self.universe.list_by_status(["ACTIVE"])
            tickers = [u.ticker for u in universe_entries]

        stored = 0
        for ticker in tickers:
            symbol = await self.symbols.get_by_ticker(ticker)
            if not symbol:
                continue
            detection = await detector.detect(symbol.id, ticker, timeframe)
            if not detection:
                continue
            score = scorer.score(detection)
            # Merge score into metadata
            metadata = dict(detection.metadata or {})
            metadata["score"] = score
            sig_id = await self.signals.upsert_signal(
                symbol_id=detection.symbol_id,
                timeframe=detection.timeframe,
                fired_at=detection.fired_at,
                strategy=detection.metadata.get("strategy", "unknown"),
                direction=detection.side,
                entry_price=detection.entry_price,
                confidence=None,
                stop_loss=None,
                take_profit=None,
                features=detection.features,
                metadata=metadata,
            )
            if sig_id:
                stored += 1
        logger.info("Scan complete: stored %s signals for timeframe %s", stored, timeframe)
        return stored
