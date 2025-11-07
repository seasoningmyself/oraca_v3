"""
Example usage of the Discord bot's MessageService.
This shows how other parts of your application can send messages to Discord.
"""
import asyncio
from bot.config import get_config
from bot.bot_client import BotClient
from bot.services.message_service import MessageService


async def example_send_messages():
    """Example of how to use the message service"""

    # Load configuration
    config = get_config()

    # Initialize bot client
    bot_client = BotClient(config)

    # Initialize message service
    message_service = MessageService(bot_client, config)

    # Start the bot in the background
    bot_task = asyncio.create_task(bot_client.start())

    # Wait for bot to connect
    await asyncio.sleep(3)

    print("Sending test messages...")

    # Example 1: Send a simple alert
    await message_service.send_alert("BTC signal fired!")

    # Example 2: Send a log message
    await message_service.send_log("System check completed successfully")

    # Example 3: Send an alert with rich formatting
    await message_service.send_alert_with_details(
        title="Trading Signal: BTC Long",
        description="A new trading opportunity has been detected",
        fields=[
            {"name": "Symbol", "value": "BTC/USDT", "inline": True},
            {"name": "Direction", "value": "LONG", "inline": True},
            {"name": "Entry Price", "value": "$45,000", "inline": True},
            {"name": "Stop Loss", "value": "$44,000", "inline": True},
            {"name": "Take Profit", "value": "$47,000", "inline": True},
            {"name": "Confidence", "value": "85%", "inline": True},
        ]
    )

    # Example 4: Send to a specific channel
    await message_service.send_to_channel(
        "general",
        "This is a message to the general channel!"
    )

    # Example 5: Send an error notification
    await message_service.send_error("API connection failed - retrying...")

    print("All messages sent!")

    # Close the bot
    await bot_client.close()
    await bot_task


if __name__ == "__main__":
    """
    Run this script to test sending messages.
    Usage: python -m bot.example_usage
    """
    try:
        asyncio.run(example_send_messages())
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")
        raise
