"""
Massive (Polygon.io) API client wrapper.
Provides a clean interface for fetching market data.
"""
from massive import RESTClient
from typing import List, Optional
from datetime import datetime, timedelta
from decimal import Decimal
from market_data.config import Config
from market_data.models.candle import Candle
from market_data.utils.logger import get_logger


class MassiveClient:
    """
    Wrapper around Massive RESTClient with custom methods
    for fetching and formatting market data.
    """

    def __init__(self, config: Config):
        """
        Initialize Massive client.

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = get_logger(__name__)

        # Initialize Massive REST client
        self.client = RESTClient(api_key=config.massive_api_key)

    def _timeframe_to_multiplier_timespan(self, timeframe: str) -> tuple:
        """
        Convert our timeframe format to Massive's multiplier/timespan format.

        Args:
            timeframe: Our timeframe ('1m', '5m', '15m', '1h', '4h', '1d')

        Returns:
            tuple: (multiplier, timespan)
        """
        mapping = {
            '1m': (1, 'minute'),
            '5m': (5, 'minute'),
            '15m': (15, 'minute'),
            '1h': (1, 'hour'),
            '4h': (4, 'hour'),
            '5h': (5, 'hour'),
            '1d': (1, 'day')
        }

        if timeframe not in mapping:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        return mapping[timeframe]

    async def get_candles(
        self,
        ticker: str,
        symbol_id: int,
        timeframe: str,
        from_date: str,
        to_date: str,
        limit: int = 50000
    ) -> List[Candle]:
        """
        Fetch candles (aggregates/bars) from Massive API.

        Args:
            ticker: Ticker symbol (e.g., 'AAPL', 'BTC-USD')
            symbol_id: Symbol ID from our database
            timeframe: Timeframe ('1m', '5m', '15m', '1h', '4h', '1d')
            from_date: Start date (YYYY-MM-DD format)
            to_date: End date (YYYY-MM-DD format)
            limit: Maximum number of candles to fetch

        Returns:
            List of Candle objects
        """
        multiplier, timespan = self._timeframe_to_multiplier_timespan(timeframe)

        self.logger.info(
            f"Fetching {timeframe} candles for {ticker} from {from_date} to {to_date}"
        )

        candles = []

        try:
            # Fetch aggregates from Massive
            for agg in self.client.list_aggs(
                ticker=ticker,
                multiplier=multiplier,
                timespan=timespan,
                from_=from_date,
                to=to_date,
                limit=limit
            ):
                # Convert Massive aggregate to our Candle model
                candle = Candle(
                    symbol_id=symbol_id,
                    timeframe=timeframe,
                    ts=datetime.fromtimestamp(agg.timestamp / 1000),  # Massive uses ms
                    open=Decimal(str(agg.open)),
                    high=Decimal(str(agg.high)),
                    low=Decimal(str(agg.low)),
                    close=Decimal(str(agg.close)),
                    volume=int(agg.volume),
                    vwap=Decimal(str(agg.vwap)) if hasattr(agg, 'vwap') and agg.vwap else None,
                    trade_count=int(agg.transactions) if hasattr(agg, 'transactions') else None,
                    source='massive',
                    is_adjusted=True
                )
                candles.append(candle)

            self.logger.info(f"Fetched {len(candles)} candles for {ticker}")

        except Exception as e:
            self.logger.error(f"Error fetching candles for {ticker}: {e}")
            raise

        return candles

    async def get_latest_price(self, ticker: str) -> Optional[dict]:
        """
        Get the latest price for a ticker.

        Args:
            ticker: Ticker symbol

        Returns:
            dict with price info or None
        """
        try:
            trade = self.client.get_last_trade(ticker=ticker)

            return {
                'ticker': ticker,
                'price': Decimal(str(trade.price)),
                'size': trade.size,
                'timestamp': datetime.fromtimestamp(trade.sip_timestamp / 1000000000),
                'exchange': trade.exchange if hasattr(trade, 'exchange') else None
            }

        except Exception as e:
            self.logger.error(f"Error fetching latest price for {ticker}: {e}")
            return None

    async def get_previous_close(self, ticker: str) -> Optional[Decimal]:
        """
        Get the previous day's closing price.

        Args:
            ticker: Ticker symbol

        Returns:
            Previous close price or None
        """
        try:
            # Get yesterday's date
            yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

            # Get daily candle
            aggs = list(self.client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=yesterday,
                to=yesterday,
                limit=1
            ))

            if aggs:
                return Decimal(str(aggs[0].close))

            return None

        except Exception as e:
            self.logger.error(f"Error fetching previous close for {ticker}: {e}")
            return None
