"""
Breakout +20% scanner (detector_id/strategy: breakout20_v1).
Designed to run after candle ingestion for a given timeframe and a set of tickers.
Computes indicators over a recent window (e.g., 3 trading days worth of bars) and
emits signals when breakout + volume + momentum conditions are met.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
import math

from market_data.models.candle import Candle
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.signal_repository import SignalRepository
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.client import MassiveClient
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


@dataclass
class SignalCandidate:
    symbol_id: int
    ticker: str
    timeframe: str
    fired_at: datetime
    price: float
    features: Dict[str, float]
    session_flag: int
    score: float


class Breakout20Scanner:
    """Detect breakout20_v1 signals on a recent window of candles."""

    def __init__(
        self,
        *,
        candle_repo: CandleRepository,
        signal_repo: SignalRepository,
        symbol_repo: SymbolRepository,
        universe_repo: UniverseRepository,
        massive_client: MassiveClient,
        history_limit: int = 400,
        mtf_windows: Optional[Dict[str, int]] = None,
    ):
        self.candles = candle_repo
        self.signals = signal_repo
        self.symbols = symbol_repo
        self.universe = universe_repo
        self.history_limit = history_limit
        self.mtf_windows = mtf_windows or {"15m": 250, "1h": 200, "4h": 200}
        self.massive = massive_client

    async def run_for_timeframe(self, timeframe: str, tickers: Optional[List[str]] = None) -> int:
        """
        Scan a timeframe for the provided tickers (or ACTIVE universe) and store signals.

        Returns:
            Number of signals stored.
        """
        if tickers is None:
            universe_entries = await self.universe.list_by_status(["ACTIVE"])
            tickers = [u.ticker for u in universe_entries]

        stored = 0
        for ticker in tickers:
            symbol = await self.symbols.get_by_ticker(ticker)
            if not symbol:
                continue
            candles = await self.candles.get_candles(symbol.id, timeframe, limit=self.history_limit)
            if not candles:
                continue
            # get_candles returns DESC; compute in ascending
            candles = list(reversed(candles))
            candidate = await self._evaluate_symbol(symbol.id, ticker, timeframe, candles)
            if not candidate:
                continue
            metadata = {
                "session_flag": candidate.session_flag,
                "score": candidate.score,
            }
            sig_id = await self.signals.upsert_signal(
                symbol_id=candidate.symbol_id,
                timeframe=timeframe,
                fired_at=candidate.fired_at,
                strategy="breakout20_v1",
                direction="LONG",
                entry_price=candidate.price,
                confidence=None,
                stop_loss=None,
                take_profit=None,
                features=candidate.features,
                metadata=metadata,
            )
            if sig_id:
                stored += 1
        logger.info("Breakout20: stored %s signals for timeframe %s", stored, timeframe)
        return stored

    async def _evaluate_symbol(
        self,
        symbol_id: int,
        ticker: str,
        timeframe: str,
        candles: List[Candle],
    ) -> Optional[SignalCandidate]:
        """
        Compute indicators on the window and return a signal candidate for the latest bar if it fires.
        """
        if len(candles) < 60:
            return None

        closes = [float(c.close) for c in candles]
        highs = [float(c.high) for c in candles]
        lows = [float(c.low) for c in candles]
        vols = [float(c.volume or 0) for c in candles]
        ts_list = [c.ts for c in candles]

        # Compute rolling indicators
        rsi = self._rsi_wilder(closes, period=14)
        macd, macd_signal, macd_hist = self._macd(closes)
        sma9 = self._sma(closes, 9)
        sma20 = self._sma(closes, 20)
        sma50 = self._sma(closes, 50)
        sma200 = self._sma(closes, 200)
        pct_from_sma20 = self._pct_from(close=closes, ma=sma20)
        pct_from_sma50 = self._pct_from(close=closes, ma=sma50)
        pct_from_sma200 = self._pct_from(close=closes, ma=sma200)
        vwap, vwapdist = self._vwap(highs, lows, closes, vols)
        rel_vol_20 = self._rel_vol(vols, window=20)
        vol_spike10 = self._rel_vol(vols, window=10)
        atr14, atrp = self._atr(highs, lows, closes, period=14)
        bb_mid, bb_upper, bb_lower, bb_width, bb_pct = self._bollinger(closes, window=20, dev=2)
        obv = self._obv(closes, vols)
        stoch_rsi = self._stoch_rsi(rsi, window=14)
        trendsma20pct = self._trend_pct(sma20)
        trendsma50pct = self._trend_pct(sma50)
        trendsma200pct = self._trend_pct(sma200)

        idx = len(candles) - 1  # latest bar
        if idx < 200:  # ensure enough history for long MAs
            return None

        close = closes[idx]
        high = highs[idx]
        volume = vols[idx]
        ts = ts_list[idx]

        # HHV breakout (previous 10 highs)
        if idx < 10:
            return None
        hhv10 = max(highs[idx - 10: idx])
        breakout_price = close > hhv10

        # Volume confirm
        rv20 = rel_vol_20[idx] if rel_vol_20[idx] is not None else 0
        volume_ok = rv20 >= 1.5

        # Momentum filters
        rsi_val = rsi[idx] if rsi[idx] is not None else 0
        rsi_ok = 55 <= rsi_val <= 85
        macd_hist_val = macd_hist[idx] if macd_hist[idx] is not None else 0
        macd_hist_prev = macd_hist[idx - 1] if macd_hist[idx - 1] is not None else 0
        macd_ok = macd_hist_val > 0 and (macd_hist_val - macd_hist_prev) > 0
        vwap_dist = vwapdist[idx] if vwapdist[idx] is not None else 0
        vwap_ok = -1.0 <= vwap_dist <= 5.0
        pct_sma20 = pct_from_sma20[idx] if pct_from_sma20[idx] is not None else 0
        pct_sma50 = pct_from_sma50[idx] if pct_from_sma50[idx] is not None else 0
        sma_ok = 2 <= pct_sma20 <= 12 and pct_sma50 >= 0

        # Bollinger width percentile (3rd-75th over last 60 bars)
        bb_width_window = [w for w in bb_width[idx - 59: idx + 1] if w is not None] if idx >= 59 else []
        bb_width_val = bb_width[idx] if bb_width[idx] is not None else None
        bb_ok = False
        if bb_width_val is not None and len(bb_width_window) >= 10:
            p3, p75 = self._percentiles(bb_width_window, [3, 75])
            bb_ok = p3 <= bb_width_val <= p75

        momentum_ok = rsi_ok and macd_ok and vwap_ok and sma_ok and bb_ok

        multitfconfirmation = await self._multitf_confirmation(symbol_id, timeframe)

        fire = breakout_price and volume_ok and momentum_ok
        if not fire:
            return None

        session_flag = self._session_flag(ts)
        features = {
            "close": close,
            "high": high,
            "volume": volume,
            "hhv10": hhv10,
            "rsi14": rsi_val,
            "macd_hist": macd_hist_val,
            "macd_hist_prev": macd_hist_prev,
            "rel_vol_20": rv20,
            "vol_spike10": vol_spike10[idx],
            "vwap": vwap[idx],
            "vwapdist": vwap_dist,
            "pct_from_sma20": pct_sma20,
            "pct_from_sma50": pct_sma50,
            "pct_from_sma200": pct_from_sma200[idx],
            "bb_width": bb_width_val,
            "bb_pct": bb_pct[idx],
            "atr14": atr14[idx],
            "atrp": atrp[idx],
            "obv": obv[idx],
            "stochrsi14": stoch_rsi[idx],
            "trendsma20pct": trendsma20pct[idx],
            "trendsma50pct": trendsma50pct[idx],
            "trendsma200pct": trendsma200pct[idx],
            "multitfconfirmation": multitfconfirmation,
            "session_flag": session_flag,
        }
        spread_bps = await self._spread_bps(ticker)
        if spread_bps is not None:
            features["spread_bps"] = spread_bps
        score = self._score(
            breakout=(close / hhv10 - 1) if hhv10 else 0,
            rel_vol=rv20,
            rsi=rsi_val,
            macd_hist=macd_hist_val,
            bb_pct=bb_pct[idx],
            atrp=atrp[idx],
            multitf=multitfconfirmation,
        )
        return SignalCandidate(
            symbol_id=symbol_id,
            ticker=ticker,
            timeframe=timeframe,
            fired_at=ts,
            price=close,
            features=features,
            session_flag=session_flag,
            score=score,
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

    @staticmethod
    def _ema_wilder(series: List[float], period: int) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(series)
        if len(series) < period:
            return out
        # seed with SMA
        seed = sum(series[:period]) / period
        out[period - 1] = seed
        alpha = 1 / period
        for i in range(period, len(series)):
            out[i] = out[i - 1] + alpha * (series[i] - out[i - 1])
        return out

    def _rsi_wilder(self, closes: List[float], period: int = 14) -> List[Optional[float]]:
        gains = [0.0]
        losses = [0.0]
        for i in range(1, len(closes)):
            change = closes[i] - closes[i - 1]
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        au = self._ema_wilder(gains, period)
        ad = self._ema_wilder(losses, period)
        rsi: List[Optional[float]] = [None] * len(closes)
        for i in range(len(closes)):
            if au[i] is None or ad[i] is None or ad[i] == 0:
                continue
            rs = au[i] / ad[i] if ad[i] else float("inf")
            rsi[i] = 100 - 100 / (1 + rs)
        return rsi

    def _macd(self, closes: List[float]) -> Tuple[List[Optional[float]], List[Optional[float]], List[Optional[float]]]:
        ema12 = self._ema(closes, 12)
        ema26 = self._ema(closes, 26)
        macd = [None if (e12 is None or e26 is None) else e12 - e26 for e12, e26 in zip(ema12, ema26)]
        macd_signal = self._ema([m if m is not None else 0 for m in macd], 9)
        macd_hist = [
            None if (m is None or s is None) else m - s
            for m, s in zip(macd, macd_signal)
        ]
        return macd, macd_signal, macd_hist

    @staticmethod
    def _pct_from(close: float | List[float], ma: List[Optional[float]]) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(ma)
        for i, m in enumerate(ma):
            if m:
                out[i] = 100 * ((close[i] / m) - 1)
        return out

    def _vwap(self, highs: List[float], lows: List[float], closes: List[float], volumes: List[float]) -> Tuple[List[Optional[float]], List[Optional[float]]]:
        vwap: List[Optional[float]] = [None] * len(closes)
        vwapdist: List[Optional[float]] = [None] * len(closes)
        cum_pv = 0.0
        cum_v = 0.0
        for i, (h, l, c, v) in enumerate(zip(highs, lows, closes, volumes)):
            tp = (h + l + c) / 3
            cum_pv += tp * v
            cum_v += v
            if cum_v > 0:
                vwap[i] = cum_pv / cum_v
                vwapdist[i] = 100 * (c / vwap[i] - 1)
        return vwap, vwapdist

    def _rel_vol(self, volumes: List[float], window: int) -> List[Optional[float]]:
        sma = self._sma(volumes, window)
        out: List[Optional[float]] = [None] * len(volumes)
        for i in range(len(volumes)):
            if sma[i]:
                out[i] = volumes[i] / sma[i] if sma[i] else None
        return out

    def _atr(self, highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> Tuple[List[Optional[float]], List[Optional[float]]]:
        trs: List[float] = []
        for i in range(len(closes)):
            if i == 0:
                trs.append(highs[i] - lows[i])
                continue
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1]),
            )
            trs.append(tr)
        atr = self._ema_wilder(trs, period)
        atrp: List[Optional[float]] = [None] * len(closes)
        for i in range(len(closes)):
            if atr[i] and closes[i]:
                atrp[i] = 100 * (atr[i] / closes[i])
        return atr, atrp

    def _bollinger(self, closes: List[float], window: int, dev: float):
        n = len(closes)
        mid: List[Optional[float]] = [None] * n
        upper: List[Optional[float]] = [None] * n
        lower: List[Optional[float]] = [None] * n
        width: List[Optional[float]] = [None] * n
        pct: List[Optional[float]] = [None] * n
        if n < window:
            return mid, upper, lower, width, pct
        for i in range(window - 1, n):
            window_vals = closes[i - window + 1: i + 1]
            mean = sum(window_vals) / window
            var = sum((x - mean) ** 2 for x in window_vals) / window
            std = math.sqrt(var)
            mid[i] = mean
            upper[i] = mean + dev * std
            lower[i] = mean - dev * std
            if mean != 0:
                width[i] = 100 * ((upper[i] - lower[i]) / mean)
            if upper[i] != lower[i]:
                pct[i] = (closes[i] - lower[i]) / (upper[i] - lower[i])
        return mid, upper, lower, width, pct

    def _obv(self, closes: List[float], volumes: List[float]) -> List[Optional[float]]:
        obv: List[Optional[float]] = [None] * len(closes)
        running = 0.0
        obv[0] = 0.0
        for i in range(1, len(closes)):
            delta = closes[i] - closes[i - 1]
            if delta > 0:
                running += volumes[i]
            elif delta < 0:
                running -= volumes[i]
            obv[i] = running
        return obv

    def _stoch_rsi(self, rsi: List[Optional[float]], window: int) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(rsi)
        for i in range(window - 1, len(rsi)):
            window_vals = [x for x in rsi[i - window + 1: i + 1] if x is not None]
            if len(window_vals) < window:
                continue
            rmin = min(window_vals)
            rmax = max(window_vals)
            if rmax == rmin:
                out[i] = 0.0
            else:
                out[i] = (rsi[i] - rmin) / (rmax - rmin)
        return out

    def _trend_pct(self, sma: List[Optional[float]]) -> List[Optional[float]]:
        out: List[Optional[float]] = [None] * len(sma)
        for i in range(1, len(sma)):
            if sma[i] and sma[i - 1]:
                out[i] = 100 * (sma[i] / sma[i - 1] - 1)
        return out

    @staticmethod
    def _percentiles(values: List[float], percentiles: List[int]) -> Tuple[float, float]:
        vals = sorted(values)
        def _pct(p: int) -> float:
            if not vals:
                return 0.0
            k = (len(vals) - 1) * (p / 100)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return vals[int(k)]
            d0 = vals[int(f)] * (c - k)
            d1 = vals[int(c)] * (k - f)
            return d0 + d1
        return _pct(percentiles[0]), _pct(percentiles[1])

    async def _multitf_confirmation(self, symbol_id: int, base_timeframe: str) -> int:
        """
        Check multi-timeframe alignment:
            15m: C > SMA20 & C > SMA50
            1h: C > SMA20
            4h: C >= SMA20
        Returns 1 if all true, else 0. If base_timeframe is not 15m, still attempt using available timeframes.
        """
        # Load 15m, 1h, 4h windows as needed
        tf_map = {"15m": "15m", "1h": "1h", "4h": "4h"}
        needs = ["15m", "1h", "4h"]
        data: Dict[str, List[Candle]] = {}
        for tf in needs:
            limit = self.mtf_windows.get(tf, 200)
            rows = await self.candles.get_candles(symbol_id, tf, limit=limit)
            if rows:
                data[tf] = list(reversed(rows))  # ascending

        # Helper to get latest close and sma20/50
        def latest_tf_vals(tf: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
            bars = data.get(tf)
            if not bars:
                return None, None, None
            closes = [float(c.close) for c in bars]
            sma20 = self._sma(closes, 20)
            sma50 = self._sma(closes, 50)
            idx = len(closes) - 1
            return closes[idx], sma20[idx] if sma20 else None, sma50[idx] if sma50 else None

        c15, sma20_15, sma50_15 = latest_tf_vals("15m")
        c1h, sma20_1h, _ = latest_tf_vals("1h")
        c4h, sma20_4h, _ = latest_tf_vals("4h")

        if c15 is None or sma20_15 is None or sma50_15 is None:
            return 0
        if c1h is None or sma20_1h is None:
            return 0
        if c4h is None or sma20_4h is None:
            return 0

        cond15 = c15 > sma20_15 and c15 > sma50_15
        cond1h = c1h > sma20_1h
        cond4h = c4h >= sma20_4h
        return 1 if (cond15 and cond1h and cond4h) else 0

    async def _spread_bps(self, ticker: str) -> Optional[float]:
        """
        Fetch NBBO and compute spread in basis points.
        spread_bps = ((ask - bid) / ((ask + bid)/2)) * 10_000
        """
        try:
            quote = await self.massive.get_nbbo(ticker)
        except Exception as exc:
            self.logger.warning("NBBO fetch failed for %s: %s", ticker, exc)
            return None
        if not quote:
            return None
        bid = quote.get("bid")
        ask = quote.get("ask")
        if bid is None or ask is None or (ask + bid) == 0:
            return None
        return ((ask - bid) / ((ask + bid) / 2)) * 10_000

    @staticmethod
    def _session_flag(ts: datetime) -> int:
        """
        Approximate session flag: 0=pre, 1=regular, 2=after.
        Uses US regular hours 13:30-20:00 UTC (9:30-16:00 ET).
        """
        ts_utc = ts.astimezone(timezone.utc)
        t = ts_utc.time()
        if t < time(13, 30):
            return 0
        if t >= time(20, 0):
            return 2
        return 1

    @staticmethod
    def _score(
        breakout: float,
        rel_vol: float,
        rsi: float,
        macd_hist: float,
        bb_pct: Optional[float],
        atrp: Optional[float],
        multitf: int,
    ) -> float:
        breakout_score = min(breakout / 0.02, 1) * 40 if breakout else 0
        volume_score = min(max(rel_vol - 1, 0) / 1.0, 1) * 25 if rel_vol is not None else 0
        momentum_bits = []
        if rsi is not None:
            momentum_bits.append(min(max((rsi - 50) / 35, 0), 1))
        momentum_bits.append(1 if macd_hist and macd_hist > 0 else 0)
        if bb_pct is not None:
            momentum_bits.append(1 if 0.3 <= bb_pct <= 0.8 else 0)
        momentum_score = (sum(momentum_bits) / len(momentum_bits) if momentum_bits else 0) * 20
        mtf_score = (1 if multitf else 0) * 10
        risk_score = (1 - min((atrp or 0) / 5, 1)) * 5 if atrp is not None else 0
        return breakout_score + volume_score + momentum_score + mtf_score + risk_score
