"""
Black Reign scanner (rule-based) implemented as a Detector.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import math

from market_data.models.candle import Candle
from market_data.repositories.candle_repository import CandleRepository
from market_data.scanners.interfaces import Detector, Detection
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class BlackReignConfig:
    pb20_min: float = 0.02
    pb20_max: float = 0.07
    pb50_min: float = 0.01
    pb50_max: float = 0.10
    rsi_min: float = 35
    rsi_max: float = 55
    quiet_vol_mult: float = 0.8
    rsi_period: int = 14


class BlackReignScanner(Detector):
    """Detect Black Reign pullback/re-entry signals on base timeframe (default: 15m)."""

    def __init__(
        self,
        *,
        candle_repo: CandleRepository,
        base_timeframe: str = "15m",
        history_limit: int = 300,
        config: BlackReignConfig = BlackReignConfig(),
    ):
        self.candles = candle_repo
        self.base_tf = base_timeframe
        self.history_limit = history_limit
        self.cfg = config

    async def detect(self, symbol_id: int, ticker: str, timeframe: str) -> Optional[Detection]:
        if timeframe != self.base_tf:
            return None
        bars = await self.candles.get_candles(symbol_id, timeframe, limit=self.history_limit)
        if not bars or len(bars) < 200:
            return None
        bars = list(reversed(bars))
        closes = [float(c.close) for c in bars]
        volumes = [float(c.volume or 0) for c in bars]
        idx = len(closes) - 1
        price = closes[idx]
        ts = bars[idx].ts
        if idx < 200:
            return None

        sma20 = self._sma(closes, 20)
        sma50 = self._sma(closes, 50)
        sma200 = self._sma(closes, 200)
        rsi = self._rsi(closes, period=self.cfg.rsi_period)
        macd_hist = self._macd_hist(closes)
        rel_vol_10 = self._rel_vol(volumes, window=10)

        trend = (
            sma20[idx] is not None and sma50[idx] is not None and sma200[idx] is not None
            and price > sma20[idx] > sma50[idx] > sma200[idx]
        )
        dist20 = (price - (sma20[idx] or price)) / (sma20[idx] or price)
        dist50 = (price - (sma50[idx] or price)) / (sma50[idx] or price)
        pb20 = self.cfg.pb20_min <= dist20 <= self.cfg.pb20_max
        pb50 = self.cfg.pb50_min <= dist50 <= self.cfg.pb50_max
        pullback = pb20 or pb50

        rsi_val = rsi[idx] if rsi[idx] is not None else 0
        rsi_reset = self.cfg.rsi_min <= rsi_val <= self.cfg.rsi_max
        macd_reset = macd_hist[idx] is not None and macd_hist[idx - 1] is not None and macd_hist[idx] < macd_hist[idx - 1]

        volquiet = False
        if rel_vol_10[idx] is not None:
            volquiet = volumes[idx] <= self.cfg.quiet_vol_mult * rel_vol_10[idx] * (sum(volumes[idx-9:idx+1])/10 if idx>=9 else 1)

        reversal = price > closes[idx - 1]
        ma_reclaim = (sma20[idx] is not None and price >= sma20[idx]) or (sma50[idx] is not None and price >= sma50[idx])

        fired = trend and pullback and rsi_reset and macd_reset and volquiet and reversal and ma_reclaim
        if not fired:
            return None

        features = {
            "price": price,
            "ts": ts,
            "dist20": dist20,
            "dist50": dist50,
            "rsi14": rsi_val,
            "macd_hist": macd_hist[idx],
            "rel_vol_10": rel_vol_10[idx],
        }
        return Detection(
            symbol_id=symbol_id,
            ticker=ticker,
            timeframe=timeframe,
            fired_at=ts,
            side="LONG",
            entry_price=price,
            features=features,
            metadata={"strategy": "blackreign_v1"},
        )

    @staticmethod
    def _sma(series: List[float], window: int) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(series)
        if len(series) < window:
            return out
        running = sum(series[:window])
        out[window - 1] = running / window
        for i in range(window, len(series)):
            running += series[i] - series[i - window]
            out[i] = running / window
        return out

    @staticmethod
    def _ema(series: List[float], period: int) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(series)
        if not series:
            return out
        alpha = 2 / (period + 1)
        out[0] = series[0]
        for i in range(1, len(series)):
            out[i] = alpha * series[i] + (1 - alpha) * (out[i - 1] if out[i - 1] is not None else series[i - 1])
        return out

    def _macd_hist(self, closes: List[float]) -> List[Optional[float]]:
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = [None if (e12 is None or e26 is None) else e12 - e26 for e12, e26 in zip(ema12, ema26)]
        macd_signal = self._ema([m if m is not None else 0 for m in macd], 9)
        return [None if (m is None or s is None) else m - s for m, s in zip(macd, macd_signal)]

    def _rsi(self, closes: List[float], period: int) -> List[Optional[float]]:
        gains = [0.0]
        losses = [0.0]
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        au = self._ema_wilder(gains, period)
        ad = self._ema_wilder(losses, period)
        rsi: List[Optional[float]] = [None] * len(closes)
        for i in range(len(closes)):
            if au[i] is None or ad[i] is None or ad[i] == 0:
                continue
            rs = au[i] / ad[i] if ad[i] else float("inf")
            rsi[i] = 100 - 100 / (1 + rs)
        return rsi

    @staticmethod
    def _ema_wilder(series: List[float], period: int) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(series)
        if len(series) < period:
            return out
        seed = sum(series[:period]) / period
        out[period - 1] = seed
        alpha = 1 / period
        for i in range(period, len(series)):
            out[i] = out[i - 1] + alpha * (series[i] - out[i - 1])
        return out

    def _rel_vol(self, volumes: List[float], window: int) -> List[Optional[float]]:
        sma = self._sma(volumes, window)
        out: List[Optional[float]] = [None] * len(volumes)
        for i in range(len(volumes)):
            if sma[i]:
                out[i] = volumes[i] / sma[i] if sma[i] else None
        return out
