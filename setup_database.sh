#!/bin/bash
# Database Setup Script for Oraca
# Run this once to set up your local PostgreSQL database

set -e  # Exit on error

echo "========================================"
echo "Oraca Database Setup"
echo "========================================"

# PostgreSQL binary path
PG_BIN="/opt/homebrew/opt/postgresql@17/bin"

# Check if PostgreSQL is installed
if [ ! -f "$PG_BIN/psql" ]; then
    echo "❌ PostgreSQL@17 not found. Installing..."
    brew install postgresql@17
    brew services start postgresql@17
    sleep 3
else
    echo "✓ PostgreSQL@17 found"
fi

# Check if PostgreSQL is running
if ! $PG_BIN/psql -d postgres -c "SELECT 1" &> /dev/null; then
    echo "Starting PostgreSQL@17..."
    brew services start postgresql@17
    sleep 3
else
    echo "✓ PostgreSQL is running"
fi

# Drop and recreate database
echo ""
echo "Setting up oracore database..."
$PG_BIN/dropdb oracore 2>/dev/null || echo "(Database didn't exist, creating fresh)"
$PG_BIN/createdb oracore
echo "✓ Database created"

# Run schema
echo "Running schema..."
$PG_BIN/psql -d oracore -f database/init.sql
echo "✓ Schema initialized"

# Verify
echo ""
echo "Verifying setup..."
TABLE_COUNT=$($PG_BIN/psql -d oracore -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'")

if [ "$TABLE_COUNT" -ge 8 ]; then
    echo "✓ All tables created successfully"
    echo ""
    echo "========================================"
    echo "✅ Database setup complete!"
    echo "========================================"
    echo ""
    echo "Database: oracore"
    echo "User: $(whoami)"
    echo "Tables: symbols, candles, signals, alerts, orders, executions, decisions, outcomes"
    echo ""
    echo "You can now run: python3 demo_market_data.py"
else
    echo "❌ Setup failed - expected 8 tables, found $TABLE_COUNT"
    exit 1
fi
