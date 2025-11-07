"""
Discord bot client wrapper.
Handles connection, events, and provides clean interface for interacting with Discord.
"""
import discord
from typing import Optional
from bot.config import Config
from bot.utils.logger import setup_logger


class BotClient:
    """
    Wrapper around discord.Client with custom configuration and event handling.
    """

    def __init__(self, config: Config):
        """
        Initialize the bot client.

        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = setup_logger(__name__, level=config.logging.level)

        # Create Discord client with minimal intents
        # For sending messages only, we don't need privileged intents
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)

        # Register event handlers
        self._register_events()

    def _register_events(self):
        """Register Discord event handlers"""

        @self.client.event
        async def on_ready():
            """Called when the bot is ready"""
            self.logger.info(f"Bot connected as {self.client.user}")
            self.logger.info(f"Bot ID: {self.client.user.id}")
            self.logger.info(f"Connected to {len(self.client.guilds)} server(s)")
            self.logger.info(f"Environment: {self.config.app.environment}")

        @self.client.event
        async def on_error(event, *args, **kwargs):
            """Called when an error occurs"""
            self.logger.error(f"Error in event {event}", exc_info=True)

        @self.client.event
        async def on_message(message):
            """Called when a message is received"""
            # Ignore messages from the bot itself
            if message.author == self.client.user:
                return

            self.logger.debug(
                f"Message received from {message.author} in {message.channel}: {message.content}"
            )

    async def get_channel(self, channel_id: int) -> Optional[discord.TextChannel]:
        """
        Get a channel by ID.

        Args:
            channel_id: Discord channel ID

        Returns:
            discord.TextChannel or None if not found
        """
        channel = self.client.get_channel(channel_id)
        if channel is None:
            self.logger.warning(f"Channel with ID {channel_id} not found")
        return channel

    async def send_message(
        self,
        channel_id: int,
        content: str,
        embed: Optional[discord.Embed] = None
    ) -> Optional[discord.Message]:
        """
        Send a message to a specific channel.

        Args:
            channel_id: Discord channel ID
            content: Message content
            embed: Optional Discord embed

        Returns:
            discord.Message or None if failed
        """
        try:
            channel = await self.get_channel(channel_id)
            if channel is None:
                self.logger.error(f"Cannot send message - channel {channel_id} not found")
                return None

            message = await channel.send(content=content, embed=embed)
            self.logger.info(f"Message sent to channel {channel_id}: {content[:50]}...")
            return message

        except discord.Forbidden:
            self.logger.error(f"No permission to send message to channel {channel_id}")
            return None
        except discord.HTTPException as e:
            self.logger.error(f"HTTP error sending message to channel {channel_id}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error sending message: {e}", exc_info=True)
            return None

    async def start(self):
        """Start the bot"""
        try:
            self.logger.info(f"Starting {self.config.app.name}...")
            await self.client.start(self.config.discord_token)
        except discord.LoginFailure:
            self.logger.error("Invalid Discord token")
            raise
        except Exception as e:
            self.logger.error(f"Error starting bot: {e}", exc_info=True)
            raise

    async def close(self):
        """Close the bot connection"""
        self.logger.info("Closing bot connection...")
        await self.client.close()

    def run(self):
        """Run the bot (blocking)"""
        try:
            self.logger.info(f"Running {self.config.app.name}...")
            self.client.run(self.config.discord_token)
        except discord.LoginFailure:
            self.logger.error("Invalid Discord token")
            raise
        except Exception as e:
            self.logger.error(f"Error running bot: {e}", exc_info=True)
            raise
