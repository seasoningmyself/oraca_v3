"""
Candle model - represents OHLCV bar data.
"""
from datetime import datetime
from typing import Optional
from decimal import Decimal
from pydantic import BaseModel


class Candle(BaseModel):
    """Candle (OHLCV bar) data model"""
    symbol_id: int
    timeframe: str  # '1m', '5m', '15m', '1h', '4h', '5h', '1d'
    ts: datetime
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    vwap: Optional[Decimal] = None
    trade_count: Optional[int] = None
    source: str = "massive"
    is_adjusted: bool = True

    class Config:
        from_attributes = True  # For Pydantic v2 ORM mode

    def to_dict(self):
        """Convert to dictionary for database insertion"""
        return {
            "symbol_id": self.symbol_id,
            "timeframe": self.timeframe,
            "ts": self.ts,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
            "trade_count": self.trade_count,
            "source": self.source,
            "is_adjusted": self.is_adjusted
        }
