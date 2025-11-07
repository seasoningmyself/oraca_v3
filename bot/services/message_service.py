"""
Message service - Business logic layer for sending Discord messages.
Similar to a @Service in Java Spring.
"""
import discord
from typing import Optional
from bot.bot_client import BotClient
from bot.config import Config
from bot.utils.logger import get_logger


class MessageService:
    """
    Service for handling message-related business logic.
    Provides high-level methods for sending messages to different channels.
    """

    def __init__(self, bot_client: BotClient, config: Config):
        """
        Initialize the message service.

        Args:
            bot_client: Discord bot client instance
            config: Configuration object
        """
        self.bot_client = bot_client
        self.config = config
        self.logger = get_logger(__name__)

    async def send_to_channel(
        self,
        channel_name: str,
        message: str,
        embed: Optional[discord.Embed] = None
    ) -> bool:
        """
        Send a message to a named channel from config.

        Args:
            channel_name: Channel name from config (e.g., 'alerts', 'logs', 'general')
            message: Message content
            embed: Optional Discord embed for rich formatting

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            channel_id = self.config.get_channel_id(channel_name)
            result = await self.bot_client.send_message(channel_id, message, embed)
            return result is not None
        except ValueError as e:
            self.logger.error(f"Invalid channel name '{channel_name}': {e}")
            return False
        except Exception as e:
            self.logger.error(f"Error sending message to {channel_name}: {e}", exc_info=True)
            return False

    async def send_alert(self, message: str, embed: Optional[discord.Embed] = None) -> bool:
        """
        Send a trading alert message.

        Args:
            message: Alert message content
            embed: Optional embed with alert details

        Returns:
            bool: True if sent successfully
        """
        self.logger.info(f"Sending alert: {message[:100]}...")
        return await self.send_to_channel("alerts", message, embed)

    async def send_log(self, message: str) -> bool:
        """
        Send a log message.

        Args:
            message: Log message content

        Returns:
            bool: True if sent successfully
        """
        self.logger.debug(f"Sending log: {message[:100]}...")
        return await self.send_to_channel("logs", message)

    async def send_error(self, message: str, embed: Optional[discord.Embed] = None) -> bool:
        """
        Send an error notification.

        Args:
            message: Error message content
            embed: Optional embed with error details

        Returns:
            bool: True if sent successfully
        """
        self.logger.warning(f"Sending error notification: {message[:100]}...")
        return await self.send_to_channel("errors", message, embed)

    async def send_general(self, message: str, embed: Optional[discord.Embed] = None) -> bool:
        """
        Send a general message.

        Args:
            message: Message content
            embed: Optional embed

        Returns:
            bool: True if sent successfully
        """
        return await self.send_to_channel("general", message, embed)

    def create_embed(
        self,
        title: str,
        description: str,
        color: discord.Color = discord.Color.blue(),
        fields: Optional[list] = None
    ) -> discord.Embed:
        """
        Create a Discord embed for rich message formatting.

        Args:
            title: Embed title
            description: Embed description
            color: Embed color
            fields: List of dicts with 'name', 'value', and optional 'inline' keys

        Returns:
            discord.Embed: Configured embed
        """
        embed = discord.Embed(title=title, description=description, color=color)

        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", ""),
                    inline=field.get("inline", False)
                )

        return embed

    async def send_alert_with_details(
        self,
        title: str,
        description: str,
        fields: Optional[list] = None
    ) -> bool:
        """
        Send a formatted alert with details.

        Args:
            title: Alert title
            description: Alert description
            fields: List of field dicts for the embed

        Returns:
            bool: True if sent successfully
        """
        embed = self.create_embed(
            title=title,
            description=description,
            color=discord.Color.gold(),
            fields=fields
        )
        return await self.send_alert(f"**{title}**", embed)

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
        Send a formatted trading signal alert.

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
        embed = self.create_embed(
            title=f"Trading Signal: {symbol} {direction.upper()}",
            description="A new trading opportunity has been detected",
            color=color,
            fields=fields
        )

        return await self.send_alert(f"**Trading Signal: {symbol} {direction.upper()}**", embed)
