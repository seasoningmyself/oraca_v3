"""
Grail scanner (rule-based) implemented as a Detector.
Conditions per spec (ASCII version).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional, Dict, Tuple
import math

from market_data.client import MassiveClient
from market_data.models.candle import Candle
from market_data.repositories.candle_repository import CandleRepository
from market_data.scanners.interfaces import Detector, Detection
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class GrailConfig:
    compression_threshold: float = 0.05  # BB width as fraction of SMA20
    breakout_clearance: float = 0.002    # e.g., 0.2% above R1
    volume_multiplier: float = 1.5
    r1_lookback: int = 10
    r2_lookback: int = 50
    rsi_min: float = 45
    rsi_max: float = 60
    rsi_period: int = 14


class GrailScanner(Detector):
    """Detect Grail signals on M15 with MTF checks."""

    def __init__(
        self,
        *,
        candle_repo: CandleRepository,
        massive_client: MassiveClient,
        history_limit: int = 200,
        mtf_windows: Optional[Dict[str, int]] = None,
        config: GrailConfig = GrailConfig(),
    ):
        self.candles = candle_repo
        self.massive = massive_client
        self.history_limit = history_limit
        self.mtf_windows = mtf_windows or {"15m": 200, "1h": 150, "4h": 150, "1d": 150}
        self.cfg = config

    async def detect(self, symbol_id: int, ticker: str, timeframe: str) -> Optional[Detection]:
        if timeframe != "15m":
            return None  # Grail defined on 15m base

        # Load base TF and MTF bars
        base = await self._load_bars(symbol_id, "15m", self.mtf_windows["15m"])
        d_bars = await self._load_bars(symbol_id, "1d", self.mtf_windows["1d"])
        h4_bars = await self._load_bars(symbol_id, "4h", self.mtf_windows["4h"])
        h1_bars = await self._load_bars(symbol_id, "1h", self.mtf_windows["1h"])

        if not base or not d_bars or not h4_bars or not h1_bars:
            return None

        # Base calculations
        closes = [float(c.close) for c in base]
        highs = [float(c.high) for c in base]
        vols = [float(c.volume or 0) for c in base]
        if len(closes) < max(self.cfg.r2_lookback, 60):
            return None
        idx = len(closes) - 1
        price = closes[idx]
        ts = base[idx].ts

        sma20 = self._sma(closes, 20)
        sma50 = self._sma(closes, 50)
        bb_width = self._bb_width(closes, window=20, dev=2)
        macd_hist = self._macd_hist(closes)
        rsi = self._rsi(closes, period=self.cfg.rsi_period)
        rel_vol_10 = self._rel_vol(vols, window=10)

        # Multi-timeframe trend
        trend_d = self._latest_trend(d_bars, 20)
        trend_h4 = self._latest_trend(h4_bars, 20)
        trend_h1 = self._latest_trend(h1_bars, 20)
        trend_m15 = price > (sma20[idx] or 0)
        mtf = sum([trend_d, trend_h4, trend_h1, trend_m15]) >= 3

        # Compression
        comp = False
        if bb_width[idx] is not None:
            comp = bb_width[idx] <= self.cfg.compression_threshold * 100  # bb_width already percentage

        # Momentum coil
        macd_coil = macd_hist[idx] is not None and macd_hist[idx - 1] is not None and macd_hist[idx - 2] is not None
        macd_coil = macd_coil and macd_hist[idx] > macd_hist[idx - 1] > macd_hist[idx - 2]
        rsi_val = rsi[idx] if rsi[idx] is not None else 0
        rsi_coil = self.cfg.rsi_min <= rsi_val <= self.cfg.rsi_max

        # Breakout trigger
        r1 = max(highs[idx - self.cfg.r1_lookback: idx]) if idx >= self.cfg.r1_lookback else None
        r2 = max(highs[idx - self.cfg.r2_lookback: idx]) if idx >= self.cfg.r2_lookback else None
        breakout = r1 is not None and price >= r1 * (1 + self.cfg.breakout_clearance)
        avg_vol10 = sum(vols[idx - 9: idx + 1]) / 10 if idx >= 9 else 0
        vol_ok = avg_vol10 > 0 and vols[idx] >= self.cfg.volume_multiplier * avg_vol10
        ret_pot = (r2 - price) / price if r2 else 0
        upside_ok = ret_pot >= 0.20

        fired = mtf and comp and macd_coil and rsi_coil and breakout and vol_ok and upside_ok
        if not fired:
            return None

        features = {
            "price": price,
            "ts": ts,
            "trend_d": trend_d,
            "trend_h4": trend_h4,
            "trend_h1": trend_h1,
            "trend_m15": trend_m15,
            "bb_width": bb_width[idx],
            "macd_hist": macd_hist[idx],
            "rsi14": rsi_val,
            "rel_vol_10": rel_vol_10[idx],
            "r1": r1,
            "r2": r2,
            "ret_pot": ret_pot,
        }
        return Detection(
            symbol_id=symbol_id,
            ticker=ticker,
            timeframe="15m",
            fired_at=ts,
            side="LONG",
            entry_price=price,
            features=features,
            metadata={"strategy": "grail_v1"},
        )

    async def _load_bars(self, symbol_id: int, timeframe: str, limit: int) -> Optional[List[Candle]]:
        bars = await self.candles.get_candles(symbol_id, timeframe, limit=limit)
        return list(reversed(bars)) if bars else None

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

    def _macd_hist(self, closes: List[float]) -> List[Optional[float]]:
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = [None if (e12 is None or e26 is None) else e12 - e26 for e12, e26 in zip(ema12, ema26)]
        macd_signal = self._ema([m if m is not None else 0 for m in macd], 9)
        return [None if (m is None or s is None) else m - s for m, s in zip(macd, macd_signal)]

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

    def _bb_width(self, closes: List[float], window: int, dev: float) -> List[Optional[float]]:
        n = len(closes)
        width: List[Optional[float]] = [None] * n
        if n < window:
            return width
        for i in range(window - 1, n):
            window_vals = closes[i - window + 1: i + 1]
            mean = sum(window_vals) / window
            var = sum((x - mean) ** 2 for x in window_vals) / window
            std = math.sqrt(var)
            upper = mean + dev * std
            lower = mean - dev * std
            if mean != 0:
                width[i] = 100 * ((upper - lower) / mean)
        return width

    def _rel_vol(self, volumes: List[float], window: int) -> List[Optional[float]]:
        sma = self._sma(volumes, window)
        out: List[Optional[float]] = [None] * len(volumes)
        for i in range(len(volumes)):
            if sma[i]:
                out[i] = volumes[i] / sma[i] if sma[i] else None
        return out

    def _latest_trend(self, bars: List[Candle], window: int) -> bool:
        closes = [float(c.close) for c in bars]
        sma = self._sma(closes, window)
        idx = len(closes) - 1
        return sma[idx] is not None and closes[idx] > sma[idx]
