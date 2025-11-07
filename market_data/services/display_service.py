"""
Display service - Formats market data for Discord display.
Includes trading signal templates and price update formatting.
"""
import discord
from typing import Optional, List
from decimal import Decimal
from datetime import datetime
from market_data.models.candle import Candle
from market_data.utils.logger import get_logger


class DisplayService:
    """
    Service for formatting market data for Discord display.
    Uses bot's MessageService for actual sending (dependency injection).
    """

    def __init__(self, message_service):
        """
        Initialize display service.

        Args:
            message_service: MessageService instance from bot module
        """
        self.message_service = message_service
        self.logger = get_logger(__name__)

    async def send_trading_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: str,
        stop_loss: str,
        take_profit: str,
        confidence: str = None,
        additional_fields: Optional[list] = None
    ) -> bool:
        """
        Send a formatted trading signal alert (moved from bot).

        Args:
            symbol: Trading pair (e.g., 'BTC/USDT')
            direction: 'LONG' or 'SHORT'
            entry_price: Entry price as string (e.g., '$45,000')
            stop_loss: Stop loss price as string
            take_profit: Take profit price as string
            confidence: Optional confidence percentage (e.g., '85%')
            additional_fields: Optional list of extra fields to add

        Returns:
            bool: True if sent successfully
        """
        # Determine color based on direction
        color = discord.Color.green() if direction.upper() == "LONG" else discord.Color.red()

        # Build fields
        fields = [
            {"name": "Symbol", "value": symbol, "inline": True},
            {"name": "Direction", "value": direction.upper(), "inline": True},
            {"name": "Entry Price", "value": entry_price, "inline": True},
            {"name": "Stop Loss", "value": stop_loss, "inline": True},
            {"name": "Take Profit", "value": take_profit, "inline": True},
        ]

        # Add confidence if provided
        if confidence:
            fields.append({"name": "Confidence", "value": confidence, "inline": True})

        # Add additional fields if provided
        if additional_fields:
            fields.extend(additional_fields)

        # Create embed
        embed = self.message_service.create_embed(
            title=f"Trading Signal: {symbol} {direction.upper()}",
            description="A new trading opportunity has been detected",
            color=color,
            fields=fields
        )

        return await self.message_service.send_alert(f"**Trading Signal: {symbol} {direction.upper()}**", embed)

    async def send_price_update(
        self,
        ticker: str,
        price: Decimal,
        previous_close: Optional[Decimal] = None,
        volume: Optional[int] = None,
        timestamp: Optional[datetime] = None
    ) -> bool:
        """
        Send a simple price update.

        Args:
            ticker: Ticker symbol
            price: Current price
            previous_close: Previous close price (for % change calculation)
            volume: Trading volume
            timestamp: Price timestamp

        Returns:
            bool: True if sent successfully
        """
        # Calculate change percentage if previous close provided
        change_pct = None
        if previous_close and previous_close > 0:
            change_pct = ((price - previous_close) / previous_close) * 100

        # Format message
        message = f"**{ticker}** Price Update\n"
        message += f"Price: ${price:,.2f}"

        if change_pct is not None:
            arrow = "↑" if change_pct >= 0 else "↓"
            color_emoji = "🟢" if change_pct >= 0 else "🔴"
            message += f" {arrow} {abs(change_pct):.2f}% {color_emoji}"

        if volume:
            message += f"\nVolume: {volume:,}"

        if timestamp:
            message += f"\nTime: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

        return await self.message_service.send_general(message)

    async def send_candle_summary(
        self,
        ticker: str,
        candle: Candle,
        timeframe: str
    ) -> bool:
        """
        Send a formatted candle summary.

        Args:
            ticker: Ticker symbol
            candle: Candle data
            timeframe: Timeframe description

        Returns:
            bool: True if sent successfully
        """
        # Determine color based on candle direction
        is_green = candle.close >= candle.open
        color = discord.Color.green() if is_green else discord.Color.red()

        # Calculate change
        change = candle.close - candle.open
        change_pct = (change / candle.open) * 100 if candle.open > 0 else 0

        fields = [
            {"name": "Open", "value": f"${candle.open:,.2f}", "inline": True},
            {"name": "High", "value": f"${candle.high:,.2f}", "inline": True},
            {"name": "Low", "value": f"${candle.low:,.2f}", "inline": True},
            {"name": "Close", "value": f"${candle.close:,.2f}", "inline": True},
            {"name": "Change", "value": f"${change:,.2f} ({change_pct:+.2f}%)", "inline": True},
            {"name": "Volume", "value": f"{candle.volume:,}", "inline": True},
        ]

        if candle.vwap:
            fields.append({"name": "VWAP", "value": f"${candle.vwap:,.2f}", "inline": True})

        embed = self.message_service.create_embed(
            title=f"{ticker} - {timeframe} Candle",
            description=f"Candle ending at {candle.ts.strftime('%Y-%m-%d %H:%M:%S')}",
            color=color,
            fields=fields
        )

        return await self.message_service.send_alert(f"**{ticker}** Candle Update", embed)

    async def send_market_summary(
        self,
        tickers: List[str],
        prices: dict,
        changes: dict
    ) -> bool:
        """
        Send a market summary for multiple tickers.

        Args:
            tickers: List of ticker symbols
            prices: Dict of {ticker: price}
            changes: Dict of {ticker: change_percentage}

        Returns:
            bool: True if sent successfully
        """
        fields = []

        for ticker in tickers:
            if ticker in prices:
                price = prices[ticker]
                change = changes.get(ticker, 0)

                arrow = "↑" if change >= 0 else "↓"
                emoji = "🟢" if change >= 0 else "🔴"

                fields.append({
                    "name": ticker,
                    "value": f"${price:,.2f} {arrow} {abs(change):.2f}% {emoji}",
                    "inline": True
                })

        embed = self.message_service.create_embed(
            title="Market Summary",
            description=f"Latest prices for {len(tickers)} symbols",
            color=discord.Color.blue(),
            fields=fields
        )

        return await self.message_service.send_general("**Market Update**", embed)
