"""
Candle repository - database operations for candles hypertable.
"""
from typing import List, Optional
from datetime import datetime
from decimal import Decimal
from market_data.repositories.base_repository import BaseRepository
from market_data.models.candle import Candle


class CandleRepository(BaseRepository):
    """Repository for candle-related database operations"""

    async def insert_candle(self, candle: Candle) -> bool:
        """
        Insert a single candle.

        Args:
            candle: Candle to insert

        Returns:
            bool: True if inserted successfully
        """
        query = """
            INSERT INTO candles (
                symbol_id, timeframe, ts, open, high, low, close,
                volume, vwap, trade_count, source, is_adjusted
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (symbol_id, timeframe, ts) DO UPDATE
            SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vwap = EXCLUDED.vwap,
                trade_count = EXCLUDED.trade_count,
                source = EXCLUDED.source,
                is_adjusted = EXCLUDED.is_adjusted
        """
        try:
            await self.execute(
                query,
                candle.symbol_id,
                candle.timeframe,
                candle.ts,
                candle.open,
                candle.high,
                candle.low,
                candle.close,
                candle.volume,
                candle.vwap,
                candle.trade_count,
                candle.source,
                candle.is_adjusted
            )
            return True
        except Exception as e:
            self.logger.error(f"Error inserting candle: {e}")
            return False

    async def insert_candles(self, candles: List[Candle]) -> int:
        """
        Insert multiple candles in batch.

        Args:
            candles: List of candles to insert

        Returns:
            int: Number of candles inserted
        """
        if not candles:
            return 0

        query = """
            INSERT INTO candles (
                symbol_id, timeframe, ts, open, high, low, close,
                volume, vwap, trade_count, source, is_adjusted
            )
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
            ON CONFLICT (symbol_id, timeframe, ts) DO UPDATE
            SET
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                volume = EXCLUDED.volume,
                vwap = EXCLUDED.vwap,
                trade_count = EXCLUDED.trade_count
        """

        count = 0
        for candle in candles:
            try:
                await self.execute(
                    query,
                    candle.symbol_id,
                    candle.timeframe,
                    candle.ts,
                    candle.open,
                    candle.high,
                    candle.low,
                    candle.close,
                    candle.volume,
                    candle.vwap,
                    candle.trade_count,
                    candle.source,
                    candle.is_adjusted
                )
                count += 1
            except Exception as e:
                self.logger.error(f"Error inserting candle {candle.ts}: {e}")

        self.logger.info(f"Inserted {count}/{len(candles)} candles")
        return count

    async def get_candles(
        self,
        symbol_id: int,
        timeframe: str,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Candle]:
        """
        Get candles for a symbol and timeframe.

        Args:
            symbol_id: Symbol ID
            timeframe: Timeframe (e.g., '1m', '5m', '1h')
            from_ts: Start timestamp (optional)
            to_ts: End timestamp (optional)
            limit: Maximum number of candles to return

        Returns:
            List of candles
        """
        conditions = ["symbol_id = $1", "timeframe = $2"]
        params = [symbol_id, timeframe]
        param_count = 2

        if from_ts:
            param_count += 1
            conditions.append(f"ts >= ${param_count}")
            params.append(from_ts)

        if to_ts:
            param_count += 1
            conditions.append(f"ts <= ${param_count}")
            params.append(to_ts)

        query = f"""
            SELECT
                symbol_id, timeframe, ts, open, high, low, close,
                volume, vwap, trade_count, source, is_adjusted
            FROM candles
            WHERE {' AND '.join(conditions)}
            ORDER BY ts DESC
            LIMIT {limit}
        """

        rows = await self.fetch(query, *params)
        return [Candle(**dict(row)) for row in rows]

    async def get_latest_candle(
        self,
        symbol_id: int,
        timeframe: str
    ) -> Optional[Candle]:
        """
        Get the most recent candle for a symbol and timeframe.

        Args:
            symbol_id: Symbol ID
            timeframe: Timeframe

        Returns:
            Latest candle or None
        """
        query = """
            SELECT
                symbol_id, timeframe, ts, open, high, low, close,
                volume, vwap, trade_count, source, is_adjusted
            FROM candles
            WHERE symbol_id = $1 AND timeframe = $2
            ORDER BY ts DESC
            LIMIT 1
        """
        row = await self.fetchrow(query, symbol_id, timeframe)

        if row:
            return Candle(**dict(row))
        return None

    async def get_candle_count(self, symbol_id: int, timeframe: str) -> int:
        """
        Get the number of candles for a symbol and timeframe.

        Args:
            symbol_id: Symbol ID
            timeframe: Timeframe

        Returns:
            Number of candles
        """
        query = """
            SELECT COUNT(*) FROM candles
            WHERE symbol_id = $1 AND timeframe = $2
        """
        return await self.fetchval(query, symbol_id, timeframe)
