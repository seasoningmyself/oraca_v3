"""
Symbol model - represents a trading instrument.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class Symbol(BaseModel):
    """Symbol (instrument) data model"""
    id: Optional[int] = None
    ticker: str
    exchange: Optional[str] = None
    asset_type: str = "equity"
    currency: str = "USD"
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    class Config:
        from_attributes = True  # For Pydantic v2 ORM mode
