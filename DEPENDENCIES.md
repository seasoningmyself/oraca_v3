# Dependency Management Guide

This project uses a **modular dependency strategy** to support reusability.

## Structure

```
oraca_v3/
├── requirements.txt           # Project-level (references modules)
└── bot/
    └── requirements.txt       # Bot-specific (standalone)
```

## Installation

### For Development (Recommended)

Install everything for the full project:

```bash
cd oraca_v3
pip install -r requirements.txt
```

This will:
- Install the bot as an editable package (`-e bot/`)
- Include all bot dependencies automatically
- Allow you to `from bot.services import MessageService` anywhere

### Bot Only (Standalone)

If you only want the Discord bot (e.g., in another project):

```bash
cd bot
pip install -r requirements.txt
```

## Adding New Dependencies

### For the Bot Module

Edit `bot/requirements.txt`:

```txt
# Add bot-specific dependencies here
discord.py>=2.3.0
new-library>=1.0.0
```

### For Your Trading/Other Modules

Edit root `requirements.txt`:

```txt
# Trading Engine
pandas>=2.0.0
numpy>=1.24.0

# Database
asyncpg>=0.29.0
```

### For New Modules (Future)

When you create new modules (e.g., `trading/`, `database/`), you can:

**Option 1: Module has own requirements.txt (most modular)**
```
trading/
├── requirements.txt  # Trading-specific deps
└── ...
```

Then reference in root:
```txt
# requirements.txt
-e bot/
-e trading/
```

**Option 2: Add to root requirements.txt**
```txt
# requirements.txt
-e bot/
pandas>=2.0.0  # For trading module
asyncpg>=0.29.0  # For database module
```

## Why This Approach?

### Benefits

✅ **Bot is standalone** - Copy `bot/` to any project and `pip install -r bot/requirements.txt`

✅ **No duplication** - Bot deps defined once in `bot/requirements.txt`

✅ **Clean separation** - Each module owns its dependencies

✅ **Easy to understand** - Root requirements.txt shows all modules

✅ **Editable installs** - Changes to bot/ code immediately available

### Trade-offs

⚠️ **Slightly more complex** - Two requirements files instead of one

⚠️ **Editable install required** - Must use `pip install -r requirements.txt` from root

## Common Commands

```bash
# Install project
pip install -r requirements.txt

# Install bot only
pip install -r bot/requirements.txt

# Install bot as editable (for development)
pip install -e bot/

# Update all dependencies
pip install --upgrade -r requirements.txt

# Check installed packages
pip list

# Export current environment (for reproducibility)
pip freeze > requirements-lock.txt
```

## Troubleshooting

**Problem:** Import error: `ModuleNotFoundError: No module named 'bot'`

**Solution:** Install from root with `-e` flag:
```bash
cd oraca_v3
pip install -r requirements.txt
```

**Problem:** Changes to bot code not reflected

**Solution:** You're likely not using editable install. Reinstall:
```bash
pip install -e bot/
```

**Problem:** Dependency conflicts

**Solution:** Use virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Best Practices

1. **Always use virtual environments**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```

2. **Pin major versions** for stability
   ```txt
   # Good
   discord.py>=2.3.0,<3.0.0

   # Also good
   discord.py==2.3.2  # Exact version
   ```

3. **Document why** you added a dependency
   ```txt
   pandas>=2.0.0  # For OHLCV dataframe processing
   ```

4. **Keep bot/requirements.txt minimal**
   - Only include what the bot actually needs
   - This keeps it lightweight and reusable

5. **Use requirements-lock.txt** for production
   ```bash
   pip freeze > requirements-lock.txt
   ```
   - Exact versions for reproducibility
   - Use in production deployments

## Summary

- **Root `requirements.txt`**: References all modules (`-e bot/`)
- **Module `requirements.txt`**: Standalone deps for that module
- **Install from root**: `pip install -r requirements.txt`
- **Modules are editable**: Changes immediately available
- **Modules are portable**: Copy to other projects easily

This gives you maximum modularity while keeping dependencies organized! 🎯
