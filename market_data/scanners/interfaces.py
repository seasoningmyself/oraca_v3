"""
Interfaces and data classes for detectors and scorers.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Optional


@dataclass
class Detection:
    symbol_id: int
    ticker: str
    timeframe: str
    fired_at: datetime
    side: str  # 'LONG' or 'SHORT'
    entry_price: float
    features: Dict[str, object]
    metadata: Dict[str, object]


class Detector:
    """Detector interface."""

    async def detect(self, symbol_id: int, ticker: str, timeframe: str) -> Optional[Detection]:
        raise NotImplementedError


class Scorer:
    """Scorer interface."""

    def score(self, detection: Detection) -> float:
        raise NotImplementedError
