"""
Main entry point for the Discord bot.
Run this file to start the bot.
"""
import asyncio
from bot.config import get_config
from bot.bot_client import BotClient
from bot.services.message_service import MessageService
from bot.utils.logger import setup_logger


async def send_startup_message(message_service: MessageService):
    """Send a startup notification when bot comes online"""
    # Wait a bit for the bot to fully connect
    await asyncio.sleep(2)

    await message_service.send_log("Bot started successfully")
    await message_service.send_general("Oraca Trading Bot is now online!")


async def main():
    """Main entry point"""
    # Load configuration
    config = get_config()

    # Setup logging
    logger = setup_logger(__name__, level=config.logging.level)
    logger.info("Starting Oraca Trading Bot...")

    # Initialize bot client
    bot_client = BotClient(config)

    # Initialize services
    message_service = MessageService(bot_client, config)

    # Store message service in bot client for easy access
    bot_client.message_service = message_service

    # Schedule startup message
    asyncio.create_task(send_startup_message(message_service))

    # Run the bot (this blocks until the bot is stopped)
    await bot_client.start()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        raise
