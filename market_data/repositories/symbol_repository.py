"""
Symbol repository - database operations for symbols table.
"""
from typing import Optional, List
from datetime import datetime
from market_data.repositories.base_repository import BaseRepository
from market_data.models.symbol import Symbol


class SymbolRepository(BaseRepository):
    """Repository for symbol-related database operations"""

    async def get_by_ticker(self, ticker: str, exchange: Optional[str] = None) -> Optional[Symbol]:
        """
        Get a symbol by ticker and optionally exchange.

        Args:
            ticker: Ticker symbol
            exchange: Exchange name (optional)

        Returns:
            Symbol or None if not found
        """
        query = """
            SELECT id, ticker, exchange, asset_type, currency, first_seen, last_seen
            FROM symbols
            WHERE ticker = $1 AND COALESCE(exchange, '') = COALESCE($2, '')
        """
        row = await self.fetchrow(query, ticker.upper(), exchange or '')

        if row:
            return Symbol(**dict(row))
        return None

    async def create(self, symbol: Symbol) -> Symbol:
        """
        Create a new symbol.

        Args:
            symbol: Symbol to create

        Returns:
            Symbol with id populated
        """
        query = """
            INSERT INTO symbols (ticker, exchange, asset_type, currency, first_seen)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (ticker, exchange) DO UPDATE
            SET last_seen = NOW()
            RETURNING id, ticker, exchange, asset_type, currency, first_seen, last_seen
        """
        row = await self.fetchrow(
            query,
            symbol.ticker.upper(),
            symbol.exchange or '',
            symbol.asset_type,
            symbol.currency,
            datetime.utcnow()
        )

        return Symbol(**dict(row))

    async def get_or_create(self, ticker: str, exchange: Optional[str] = None) -> Symbol:
        """
        Get an existing symbol or create if it doesn't exist.

        Args:
            ticker: Ticker symbol
            exchange: Exchange name (optional)

        Returns:
            Symbol
        """
        existing = await self.get_by_ticker(ticker, exchange)
        if existing:
            return existing

        # Create new symbol
        new_symbol = Symbol(
            ticker=ticker.upper(),
            exchange=exchange or ''
        )
        return await self.create(new_symbol)

    async def list_all(self) -> List[Symbol]:
        """
        List all symbols.

        Returns:
            List of symbols
        """
        query = """
            SELECT id, ticker, exchange, asset_type, currency, first_seen, last_seen
            FROM symbols
            ORDER BY ticker
        """
        rows = await self.fetch(query)
        return [Symbol(**dict(row)) for row in rows]

    async def update_last_seen(self, symbol_id: int):
        """
        Update the last_seen timestamp for a symbol.

        Args:
            symbol_id: Symbol ID
        """
        query = "UPDATE symbols SET last_seen = NOW() WHERE id = $1"
        await self.execute(query, symbol_id)
