# Hourly Top Tech Stocks Monitor

Automatically fetches and reports on the top 4 tech stocks (AAPL, MSFT, GOOGL, NVDA) every hour.

## Quick Start

Run this command to set up the hourly automation:

```bash
./setup_hourly_cron.sh
```

This will:
- Install a cron job that runs every hour (at :00)
- Create a logs directory for tracking runs
- Test the script immediately

## What It Does

Every hour, the script will:
1. Fetch latest 5-minute candles for AAPL, MSFT, GOOGL, NVDA
2. Calculate 24-hour performance for each stock
3. Send a ranked Discord embed with:
   - Current price
   - 24h percentage change
   - Volume
   - Performance indicators

## Manual Commands

### Run Once Now
```bash
python3 hourly_top_tech.py
```

### Check Cron Status
```bash
crontab -l
```

### View Logs
```bash
tail -f logs/hourly_top_tech.log
```

### Remove Cron Job
```bash
crontab -e
# Delete the line with "hourly_top_tech.py"
```

## Customization

To change the stocks being monitored, edit `hourly_top_tech.py`:

```python
TOP_TECH_STOCKS = ["AAPL", "MSFT", "GOOGL", "NVDA"]  # Change these
```

## Troubleshooting

If the cron job isn't running:

1. Check cron is installed:
   ```bash
   crontab -l
   ```

2. Check logs for errors:
   ```bash
   cat logs/hourly_top_tech.log
   ```

3. Verify environment variables are set:
   - Make sure `.env` file exists in project root
   - Required: `POLYGON_API_KEY`, `DATABASE_URL`, `DISCORD_BOT_TOKEN`, etc.

4. Test manually first:
   ```bash
   python3 hourly_top_tech.py
   ```
