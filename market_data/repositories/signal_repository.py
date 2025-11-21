"""
Signal repository - insert and fetch signals.
"""
from typing import Optional, Any, Dict
from datetime import datetime
import json

from market_data.repositories.base_repository import BaseRepository


class SignalRepository(BaseRepository):
    """Repository for signals table operations."""

    async def upsert_signal(
        self,
        *,
        symbol_id: int,
        timeframe: str,
        fired_at: datetime,
        strategy: str,
        direction: str,
        entry_price: Optional[float],
        confidence: Optional[float] = None,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        features: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Insert a signal if one does not already exist for the symbol/timeframe/fired_at/strategy combo.
        Returns signal id (new or existing).
        """
        query = """
        WITH ins AS (
            INSERT INTO signals (
                symbol_id, strategy, direction, fired_at, timeframe,
                confidence, entry_price, stop_loss, take_profit, features, metadata
            )
            SELECT $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11
            WHERE NOT EXISTS (
                SELECT 1 FROM signals
                WHERE symbol_id = $1 AND timeframe = $5 AND fired_at = $4 AND strategy = $2
            )
            RETURNING id
        )
        SELECT id FROM ins
        UNION ALL
        SELECT id FROM signals
        WHERE symbol_id = $1 AND timeframe = $5 AND fired_at = $4 AND strategy = $2
        LIMIT 1;
        """
        row = await self.fetchrow(
            query,
            symbol_id,
            strategy,
            direction,
            fired_at,
            timeframe,
            confidence,
            entry_price,
            stop_loss,
            take_profit,
            json.dumps(features or {}),
            json.dumps(metadata or {}),
        )
        return row["id"] if row else None
