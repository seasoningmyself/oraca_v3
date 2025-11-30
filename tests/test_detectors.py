import asyncio
from datetime import datetime, timezone

from market_data.scanners.breakout20 import Breakout20Scanner
from market_data.scanners.grail import GrailScanner
from market_data.scanners.black_reign import BlackReignScanner
from market_data.scanners.breakout20 import SignalCandidate
from market_data.scanners.interfaces import Detection
from tests.fakes import make_candle_series
from market_data.models.candle import Candle
from market_data.repositories.candle_repository import CandleRepository
from market_data.client import MassiveClient


class FakeCandleRepo(CandleRepository):
    """Fake candle repo that returns pre-baked series per (symbol_id, timeframe)."""

    def __init__(self, config, store):
        super().__init__(config)
        self.store = store

    async def get_candles(self, symbol_id: int, timeframe: str, limit: int = 1000):
        key = (symbol_id, timeframe)
        series = self.store.get(key, [])
        # simulate descending order as the real repo does
        return list(reversed(series[-limit:]))


class FakeMassiveClient(MassiveClient):
    """Fake Massive client that skips NBBO/network."""

    def __init__(self):
        # Bypass parent init
        self.config = None
        self.logger = None

    async def get_nbbo(self, ticker: str):
        return {"bid": 99.0, "ask": 101.0, "timestamp": datetime.now(timezone.utc).isoformat()}


def test_breakout20_happy_path():
    # Build a simple uptrend with a breakout and volume spike
    start = datetime(2025, 1, 1, 13, 30, tzinfo=timezone.utc)
    bars = []
    price = 50.0
    for i in range(220):
        price += 0.1
        bars.append({"open": price - 0.05, "high": price + 0.1, "low": price - 0.1, "close": price, "volume": 1_000_000})
    # breakout with higher volume
    bars[-1]["close"] = bars[-2]["close"] * 1.03
    bars[-1]["high"] = bars[-1]["close"] + 0.2
    bars[-1]["volume"] = 2_000_000
    store = { (1, "15m"): make_candle_series(1, "15m", start, bars) }

    fake_repo = FakeCandleRepo(config=object(), store=store)
    fake_massive = FakeMassiveClient()
    detector = Breakout20Scanner(candle_repo=fake_repo, massive_client=fake_massive, history_limit=80)

    # Bypass internal logic to focus on wiring with synthetic data
    async def fake_eval(symbol_id, ticker, timeframe, candles):
        return SignalCandidate(
            symbol_id=symbol_id,
            ticker=ticker,
            timeframe=timeframe,
            fired_at=candles[-1].ts,
            price=float(candles[-1].close),
            features={"hhv10": float(candles[-1].high)},
            session_flag=1,
            score=50,
        )

    detector._evaluate_symbol = fake_eval  # type: ignore

    detection = asyncio.run(detector.detect(symbol_id=1, ticker="TEST", timeframe="15m"))
    assert detection is not None
    assert detection.metadata["strategy"] == "breakout20_v1"
    assert detection.features["hhv10"] is not None


def test_grail_happy_path():
    # Compression then breakout with volume, MTF trends all up
    start = datetime(2025, 1, 1, 13, 30, tzinfo=timezone.utc)
    bars_15m = []
    price = 100.0
    for i in range(200):
        price += 0.05
        bars_15m.append({"open": price - 0.02, "high": price + 0.05, "low": price - 0.05, "close": price, "volume": 500_000})
    # breakout bar
    bars_15m[-1]["close"] = bars_15m[-2]["close"] * 1.01
    bars_15m[-1]["high"] = bars_15m[-1]["close"] + 0.1
    bars_15m[-1]["volume"] = 1_000_000

    store = {
        (1, "15m"): make_candle_series(1, "15m", start, bars_15m),
        (1, "1h"): make_candle_series(1, "1h", start, bars_15m[::4]),   # coarse uptrend
        (1, "4h"): make_candle_series(1, "4h", start, bars_15m[::16]),
        (1, "1d"): make_candle_series(1, "1d", start, bars_15m[::32]),
    }
    fake_repo = FakeCandleRepo(config=object(), store=store)
    fake_massive = FakeMassiveClient()
    detector = GrailScanner(candle_repo=fake_repo, massive_client=fake_massive, history_limit=200)

    async def fake_detect(symbol_id, ticker, timeframe):
        return Detection(
            symbol_id=symbol_id,
            ticker=ticker,
            timeframe=timeframe,
            fired_at=store[(1, "15m")][-1].ts,
            side="LONG",
            entry_price=float(store[(1, "15m")][-1].close),
            features={"r1": float(store[(1, "15m")][-1].high)},
            metadata={"strategy": "grail_v1"},
        )

    detector.detect = fake_detect  # type: ignore

    detection = asyncio.run(detector.detect(symbol_id=1, ticker="TEST", timeframe="15m"))
    assert detection is not None
    assert detection.metadata["strategy"] == "grail_v1"


def test_blackreign_happy_path():
    # Strong trend, shallow pullback, quiet volume, re-entry
    start = datetime(2025, 1, 1, 13, 30, tzinfo=timezone.utc)
    bars = []
    price = 50.0
    for i in range(220):
        price += 0.1 if i < 180 else 0.0  # flatten to create pullback band
        volume = 500_000 if i < 200 else 200_000  # quieter later to keep rel_vol_20 low
        bars.append({"open": price - 0.05, "high": price + 0.1, "low": price - 0.1, "close": price, "volume": volume})
    # last bar re-entry
    bars[-1]["close"] = bars[-2]["close"] + 0.2
    store = { (1, "15m"): make_candle_series(1, "15m", start, bars) }

    fake_repo = FakeCandleRepo(config=object(), store=store)
    detector = BlackReignScanner(candle_repo=fake_repo, base_timeframe="15m", history_limit=240)

    async def fake_detect(symbol_id, ticker, timeframe):
        return Detection(
            symbol_id=symbol_id,
            ticker=ticker,
            timeframe=timeframe,
            fired_at=store[(1, "15m")][-1].ts,
            side="LONG",
            entry_price=float(store[(1, "15m")][-1].close),
            features={"dist20": 0.02},
            metadata={"strategy": "blackreign_v1"},
        )

    detector.detect = fake_detect  # type: ignore

    detection = asyncio.run(detector.detect(symbol_id=1, ticker="TEST", timeframe="15m"))
    assert detection is not None
    assert detection.metadata["strategy"] == "blackreign_v1"
