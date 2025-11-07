"""
Data service - Business logic for fetching and storing market data.
"""
from typing import List, Optional
from datetime import datetime
from market_data.client import MassiveClient
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.models.candle import Candle
from market_data.models.symbol import Symbol
from market_data.config import Config
from market_data.utils.logger import get_logger


class DataService:
    """
    Service for handling market data operations.
    Orchestrates fetching from Massive API and storing in database.
    """

    def __init__(
        self,
        massive_client: MassiveClient,
        symbol_repo: SymbolRepository,
        candle_repo: CandleRepository,
        config: Config
    ):
        """
        Initialize data service.

        Args:
            massive_client: Massive API client
            symbol_repo: Symbol repository
            candle_repo: Candle repository
            config: Configuration
        """
        self.massive_client = massive_client
        self.symbol_repo = symbol_repo
        self.candle_repo = candle_repo
        self.config = config
        self.logger = get_logger(__name__)

    async def fetch_and_store_candles(
        self,
        ticker: str,
        timeframe: str,
        from_date: str,
        to_date: str,
        exchange: Optional[str] = None
    ) -> int:
        """
        Fetch candles from Massive API and store in database.

        Args:
            ticker: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            exchange: Exchange name (optional)

        Returns:
            int: Number of candles stored
        """
        self.logger.info(f"Fetching and storing {timeframe} candles for {ticker}")

        # Get or create symbol
        symbol = await self.symbol_repo.get_or_create(ticker, exchange)
        self.logger.info(f"Symbol {ticker} has ID {symbol.id}")

        # Fetch candles from Massive
        candles = await self.massive_client.get_candles(
            ticker=ticker,
            symbol_id=symbol.id,
            timeframe=timeframe,
            from_date=from_date,
            to_date=to_date
        )

        if not candles:
            self.logger.warning(f"No candles fetched for {ticker}")
            return 0

        # Store candles in database
        count = await self.candle_repo.insert_candles(candles)

        # Update symbol last_seen timestamp
        await self.symbol_repo.update_last_seen(symbol.id)

        self.logger.info(f"Stored {count} candles for {ticker}")
        return count

    async def get_latest_candle(
        self,
        ticker: str,
        timeframe: str,
        exchange: Optional[str] = None
    ) -> Optional[Candle]:
        """
        Get the latest candle for a ticker from database.

        Args:
            ticker: Ticker symbol
            timeframe: Timeframe
            exchange: Exchange (optional)

        Returns:
            Latest candle or None
        """
        # Get symbol
        symbol = await self.symbol_repo.get_by_ticker(ticker, exchange)

        if not symbol:
            self.logger.warning(f"Symbol {ticker} not found in database")
            return None

        # Get latest candle
        return await self.candle_repo.get_latest_candle(symbol.id, timeframe)

    async def get_candles(
        self,
        ticker: str,
        timeframe: str,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        limit: int = 1000,
        exchange: Optional[str] = None
    ) -> List[Candle]:
        """
        Get candles for a ticker from database.

        Args:
            ticker: Ticker symbol
            timeframe: Timeframe
            from_ts: Start timestamp (optional)
            to_ts: End timestamp (optional)
            limit: Maximum number of candles
            exchange: Exchange (optional)

        Returns:
            List of candles
        """
        # Get symbol
        symbol = await self.symbol_repo.get_by_ticker(ticker, exchange)

        if not symbol:
            self.logger.warning(f"Symbol {ticker} not found in database")
            return []

        # Get candles
        return await self.candle_repo.get_candles(
            symbol.id,
            timeframe,
            from_ts,
            to_ts,
            limit
        )

    async def get_live_price(self, ticker: str) -> Optional[dict]:
        """
        Get live price for a ticker from Massive API.

        Args:
            ticker: Ticker symbol

        Returns:
            dict with price info or None
        """
        return await self.massive_client.get_latest_price(ticker)

    async def bulk_fetch_and_store(
        self,
        tickers: List[str],
        timeframe: str,
        from_date: str,
        to_date: str
    ) -> dict:
        """
        Fetch and store candles for multiple tickers.

        Args:
            tickers: List of ticker symbols
            timeframe: Timeframe
            from_date: Start date
            to_date: End date

        Returns:
            dict: Summary of results {ticker: count}
        """
        results = {}

        for ticker in tickers:
            try:
                count = await self.fetch_and_store_candles(
                    ticker,
                    timeframe,
                    from_date,
                    to_date
                )
                results[ticker] = count
            except Exception as e:
                self.logger.error(f"Error processing {ticker}: {e}")
                results[ticker] = 0

        return results
