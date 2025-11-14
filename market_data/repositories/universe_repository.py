"""
Universe repository - database operations for curated symbols.
"""
from datetime import datetime
from typing import Iterable, List, Optional

import json

from market_data.models.universe_symbol import UniverseSymbol
from market_data.repositories.base_repository import BaseRepository


class UniverseRepository(BaseRepository):
    """Repository for reading/writing universe_symbols rows."""

    async def upsert(self, entry: UniverseSymbol) -> UniverseSymbol:
        """
        Insert or update a universe symbol entry.

        Args:
            entry: Universe symbol payload
        """
        query = """
            INSERT INTO universe_symbols (
                symbol_id,
                ticker,
                float_shares,
                preferred_float,
                last_price,
                price_status,
                float_status,
                status,
                status_reason,
                last_price_at,
                float_updated_at,
                refreshed_at,
                temp_exclusion_until,
                metadata,
                updated_at
            )
            VALUES (
                $1, $2, $3, $4, $5,
                $6, $7, $8, $9, $10,
                $11, $12, $13, $14, NOW()
            )
            ON CONFLICT (symbol_id) DO UPDATE
            SET
                float_shares = EXCLUDED.float_shares,
                preferred_float = EXCLUDED.preferred_float,
                last_price = EXCLUDED.last_price,
                price_status = EXCLUDED.price_status,
                float_status = EXCLUDED.float_status,
                status = EXCLUDED.status,
                status_reason = EXCLUDED.status_reason,
                last_price_at = EXCLUDED.last_price_at,
                float_updated_at = EXCLUDED.float_updated_at,
                refreshed_at = EXCLUDED.refreshed_at,
                temp_exclusion_until = EXCLUDED.temp_exclusion_until,
                metadata = EXCLUDED.metadata,
                updated_at = NOW()
            RETURNING
                symbol_id, ticker, float_shares, preferred_float,
                last_price, price_status, float_status, status,
                status_reason, last_price_at, float_updated_at,
                refreshed_at, temp_exclusion_until, metadata,
                created_at, updated_at
        """

        row = await self.fetchrow(
            query,
            entry.symbol_id,
            entry.ticker.upper(),
            entry.float_shares,
            entry.preferred_float,
            entry.last_price,
            entry.price_status,
            entry.float_status,
            entry.status,
            entry.status_reason,
            entry.last_price_at,
            entry.float_updated_at,
            entry.refreshed_at,
            entry.temp_exclusion_until,
            json.dumps(entry.metadata or {}),
        )
        data = dict(row)
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])
        return UniverseSymbol(**data)

    async def list_by_status(self, statuses: Iterable[str]) -> List[UniverseSymbol]:
        """Fetch universe entries that match the provided statuses."""
        query = """
            SELECT
                symbol_id, ticker, float_shares, preferred_float,
                last_price, price_status, float_status, status,
                status_reason, last_price_at, float_updated_at,
                refreshed_at, temp_exclusion_until, metadata
            FROM universe_symbols
            WHERE status = ANY($1::text[])
            ORDER BY last_price DESC NULLS LAST
        """
        rows = await self.fetch(query, list(statuses))
        results = []
        for row in rows:
            data = dict(row)
            if isinstance(data.get("metadata"), str):
                data["metadata"] = json.loads(data["metadata"])
            results.append(UniverseSymbol(**data))
        return results

    async def mark_stale_entries(
        self,
        refreshed_before: datetime,
        status: str,
        reason: str,
    ) -> int:
        """
        Mark entries that were not refreshed in the latest run.

        Args:
            refreshed_before: Timestamp threshold
            status: New status
            reason: Reason stored in status_reason
        """
        query = """
            UPDATE universe_symbols
            SET status = $1,
                status_reason = $2,
                updated_at = NOW()
            WHERE refreshed_at < $3
        """
        result = await self.execute(query, status, reason, refreshed_before)
        # asyncpg returns e.g. "UPDATE 5" -> parse count
        return int(result.split()[-1]) if isinstance(result, str) else 0

    async def count_active(self) -> int:
        """Return the number of active symbols."""
        query = "SELECT COUNT(*) FROM universe_symbols WHERE status = 'ACTIVE'"
        return await self.fetchval(query) or 0
