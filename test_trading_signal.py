"""
Test script for trading signal template.
Sends sample trading signals to Discord.
"""
import asyncio
from bot.config import get_config
from bot.bot_client import BotClient
from bot.services.message_service import MessageService


async def test_trading_signals():
    """Send test trading signals"""

    # Initialize
    config = get_config()
    bot_client = BotClient(config)
    message_service = MessageService(bot_client, config)

    # Start bot
    bot_task = asyncio.create_task(bot_client.start())
    await asyncio.sleep(3)  # Wait for connection

    print("Sending test trading signals...\n")

    # Test 1: BTC Long Signal (like the original)
    print("1. Sending BTC LONG signal...")
    await message_service.send_trading_signal(
        symbol="BTC/USDT",
        direction="LONG",
        entry_price="$45,000",
        stop_loss="$44,000",
        take_profit="$47,000",
        confidence="85%"
    )
    await asyncio.sleep(2)

    # Test 2: ETH Short Signal (with red color)
    print("2. Sending ETH SHORT signal...")
    await message_service.send_trading_signal(
        symbol="ETH/USDT",
        direction="SHORT",
        entry_price="$2,500",
        stop_loss="$2,600",
        take_profit="$2,300",
        confidence="78%"
    )
    await asyncio.sleep(2)

    # Test 3: Signal with additional fields
    print("3. Sending signal with extra info...")
    await message_service.send_trading_signal(
        symbol="SOL/USDT",
        direction="LONG",
        entry_price="$98.50",
        stop_loss="$95.00",
        take_profit="$105.00",
        confidence="92%",
        additional_fields=[
            {"name": "Timeframe", "value": "1H", "inline": True},
            {"name": "Strategy", "value": "Momentum", "inline": True},
            {"name": "Risk/Reward", "value": "1:2.5", "inline": True},
        ]
    )
    await asyncio.sleep(2)

    # Test 4: Signal without confidence
    print("4. Sending signal without confidence...")
    await message_service.send_trading_signal(
        symbol="MATIC/USDT",
        direction="LONG",
        entry_price="$0.85",
        stop_loss="$0.82",
        take_profit="$0.92"
    )

    print("\nAll trading signals sent!")

    # Close bot
    await bot_client.close()
    await bot_task


if __name__ == "__main__":
    try:
        asyncio.run(test_trading_signals())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error: {e}")
        raise
