"""
Universe symbol model - represents curated symbols eligible for scanning.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from pydantic import BaseModel


class UniverseSymbol(BaseModel):
    """Universe entry persisted in the database."""

    symbol_id: int
    ticker: str
    float_shares: Optional[int] = None
    preferred_float: bool = False
    last_price: Optional[Decimal] = None
    price_status: str = "UNKNOWN"
    float_status: str = "UNKNOWN"
    status: str = "ACTIVE"
    status_reason: Optional[str] = None
    last_price_at: Optional[datetime] = None
    float_updated_at: Optional[datetime] = None
    refreshed_at: datetime = datetime.utcnow()
    temp_exclusion_until: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True
