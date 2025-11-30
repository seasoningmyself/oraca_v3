from datetime import datetime, timezone, timedelta
from typing import List

from market_data.models.candle import Candle


def make_candle(
    symbol_id: int,
    timeframe: str,
    ts: datetime,
    open_: float,
    high: float,
    low: float,
    close: float,
    volume: int,
) -> Candle:
    return Candle(
        symbol_id=symbol_id,
        timeframe=timeframe,
        ts=ts,
        open=open_,
        high=high,
        low=low,
        close=close,
        volume=volume,
        vwap=None,
        trade_count=None,
        source="test",
        is_adjusted=True,
    )


def make_candle_series(
    symbol_id: int,
    timeframe: str,
    start_ts: datetime,
    bars: List[dict],
) -> List[Candle]:
    """
    bars: list of dicts with keys: open, high, low, close, volume
    """
    candles: List[Candle] = []
    delta = _tf_to_timedelta(timeframe)
    ts = start_ts
    for bar in bars:
        candles.append(
            make_candle(
                symbol_id=symbol_id,
                timeframe=timeframe,
                ts=ts,
                open_=bar["open"],
                high=bar["high"],
                low=bar["low"],
                close=bar["close"],
                volume=bar["volume"],
            )
        )
        ts += delta
    return candles


def _tf_to_timedelta(tf: str) -> timedelta:
    if tf.endswith("m"):
        return timedelta(minutes=int(tf[:-1]))
    if tf.endswith("h"):
        return timedelta(hours=int(tf[:-1]))
    if tf.endswith("d"):
        return timedelta(days=int(tf[:-1]))
    raise ValueError(f"Unsupported timeframe: {tf}")
