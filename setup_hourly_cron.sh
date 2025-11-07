#!/bin/bash
# Setup script for hourly tech stocks monitoring

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Python path (use python3)
PYTHON_BIN=$(which python3)

# Log file location
LOG_FILE="$SCRIPT_DIR/logs/hourly_top_tech.log"

# Create logs directory if it doesn't exist
mkdir -p "$SCRIPT_DIR/logs"

# Cron job entry (runs at the top of every hour)
CRON_ENTRY="0 * * * * cd $SCRIPT_DIR && $PYTHON_BIN $SCRIPT_DIR/hourly_top_tech.py >> $LOG_FILE 2>&1"

echo "Setting up hourly cron job..."
echo ""
echo "This will run: $SCRIPT_DIR/hourly_top_tech.py"
echo "Every hour at: :00 (e.g., 1:00, 2:00, 3:00, etc.)"
echo "Logs will be saved to: $LOG_FILE"
echo ""

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "hourly_top_tech.py"; then
    echo "⚠️  Cron job already exists!"
    echo ""
    echo "Current crontab:"
    crontab -l | grep "hourly_top_tech.py"
    echo ""
    read -p "Remove existing entry and reinstall? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        # Remove old entry
        crontab -l | grep -v "hourly_top_tech.py" | crontab -
        echo "✓ Removed old entry"
    else
        echo "Cancelled. No changes made."
        exit 0
    fi
fi

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo ""
echo "✓ Cron job installed successfully!"
echo ""
echo "To verify, run: crontab -l"
echo "To remove, run: crontab -e (and delete the line)"
echo ""
echo "Testing the script now..."
cd "$SCRIPT_DIR"
$PYTHON_BIN "$SCRIPT_DIR/hourly_top_tech.py"

echo ""
echo "✓ Setup complete! The script will run every hour."
echo "Check logs at: $LOG_FILE"
