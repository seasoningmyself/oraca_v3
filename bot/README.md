# Discord Notification Bot

A modular Discord bot for sending notifications and alerts to multiple channels. Self-contained, reusable, drop into any Python project.

## Installation

**From project root:**
```bash
pip install -r requirements.txt  # Installs bot as editable package
```

**Standalone:**
```bash
pip install -r bot/requirements.txt
```

**Copy to another project:**
```bash
cp -r bot/ /path/to/new/project/
```

## Quick Start

### 1. Configuration

Edit `bot/config.yaml`:
```yaml
discord:
  token_env: DISCORD_BOT_TOKEN
  channels:
    general: 1234567890
    alerts: 1234567890
    logs: 1234567890
    errors: 1234567890
```

Get channel IDs: Discord Settings → Advanced → Developer Mode → Right-click channel → Copy ID

### 2. Environment Variables

Create `.env.local`:
```bash
DISCORD_BOT_TOKEN=your_token_here
```

### 3. Usage

```python
import asyncio
from bot.config import get_config
from bot.bot_client import BotClient
from bot.services.message_service import MessageService

async def main():
    config = get_config()
    bot_client = BotClient(config)
    message_service = MessageService(bot_client, config)

    # Start bot
    asyncio.create_task(bot_client.start())
    await asyncio.sleep(2)

    # Send messages
    await message_service.send_alert("🚀 Alert message")
    await message_service.send_log("System started")
    await message_service.send_error("Error occurred")

    # Rich formatting
    await message_service.send_alert_with_details(
        title="Trading Signal",
        description="BTC Long opportunity",
        fields=[
            {"name": "Entry", "value": "$45k", "inline": True},
            {"name": "Stop", "value": "$44k", "inline": True},
        ]
    )

asyncio.run(main())
```

## Integration Patterns

### Pattern 1: Dependency Injection (Recommended)

```python
class TradingEngine:
    def __init__(self, notifier: MessageService):
        self.notifier = notifier

    async def on_signal(self, signal):
        await self.notifier.send_alert(f"Signal: {signal}")

# Usage
notifier = MessageService(bot_client, config)
engine = TradingEngine(notifier=notifier)
```

### Pattern 2: Background Task

```python
async def main():
    bot_client = BotClient(config)
    notifier = MessageService(bot_client, config)

    # Start bot in background
    asyncio.create_task(bot_client.start())
    await asyncio.sleep(2)

    # Your application logic
    while True:
        result = await check_something()
        if result:
            await notifier.send_alert(result)
        await asyncio.sleep(60)
```

## Configuration Options

### Custom Config Path
```python
config = get_config(config_path="/custom/path/config.yaml")
```

### Environment Variable Override
```bash
export BOT_CONFIG_PATH=/path/to/config.yaml
```

### Programmatic Config
```python
from bot.config import Config, DiscordConfig, ChannelConfig, set_config

config = Config(
    discord=DiscordConfig(
        token_env="MY_TOKEN",
        channels=ChannelConfig(general=123, alerts=456, logs=789, errors=101)
    ),
    ...
)
set_config(config)
```

## Architecture

```
Your App → MessageService (business logic) → BotClient (Discord wrapper) → discord.py
```

**Layered approach:**
- `MessageService`: High-level methods (send_alert, send_log, etc.)
- `BotClient`: Connection management, low-level Discord API
- Clean separation for testing and maintainability

## Project Structure

```
bot/
├── config.yaml              # Configuration
├── config.py                # Config loader
├── bot_client.py            # Discord client wrapper
├── main.py                  # Standalone entry point
├── services/
│   └── message_service.py   # Business logic
└── utils/
    └── logger.py            # Logging
```

## Run Standalone

```bash
python -m bot.main
```

## Run Example

```bash
python -m bot.example_usage
```

## Adding Channels

1. Add to `config.yaml`:
   ```yaml
   channels:
     new_channel: 1234567890
   ```

2. Use it:
   ```python
   await message_service.send_to_channel("new_channel", "Hello!")
   ```

## Troubleshooting

**"Channel not found"**: Verify bot is in server and has permissions

**"Invalid token"**: Check `.env.local` has correct token and variable name matches `config.yaml`

**Import error**: Install as editable package: `pip install -e bot/`

## Dependencies

- discord.py >= 2.3.0
- python-dotenv >= 1.0.0
- pyyaml >= 6.0.0
- pydantic >= 2.0.0


---

**Version:** 1.0.0
**Author:** Ennis M. Salam
**Minimal, modular, reusable.**
