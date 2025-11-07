# Oraca Trading System Assessment: Executive Summary
**Prepared by:** Ennis M. Salam 
**Client:** Intertwined Investments  
**References:** Oraca Comprehensive Database Strategy Report, Oraca System Architecture Report

## Purpose and Scope

My purpose this week was to assess our current capabilities, explain how the parts of Oraca fit together, and identify what needs improvement so we can move forward confidently. The near term goal is a dependable alert system with a human making the final trading decision. The longer term goal is to capture the right history so we can train machine learning models that reduce noise and improve outcomes.

## Current System Architecture

After analyzing the codebase, I've mapped how our components currently interact:

**What's Actually Working:**
```
Yahoo Finance -> Basic Scanner -> MongoDB -> Dashboard
```

The basic scanner successfully detects price/volume breakouts on major tickers (TSLA, PLTR, SOFI, MARA, RIOT, AMD, GME), stores predictions in MongoDB Atlas, and displays them on a Flask dashboard. This pipeline functions but lacks the sophistication needed for reliable trading signals.

**What's Broken:**
```
Random Number Generator -> Mock API -> Discord Alerts
```

Discord currently receives fake randomized data instead of real scanner results. The API bridge contains placeholder code that was never connected to MongoDB, making all Discord alerts meaningless.

**What We Have But Aren't Using:**
I discovered a sophisticated ML scanner with Random Forest and Linear Regression models that calculates RSI, MACD, Bollinger Bands, and other technical indicators. This system exists in the codebase but outputs to local files instead of production systems.

## Code Quality Assessment

The current codebase is a textbook example of prototype code that grew organically without architecture. I found severe issues that require immediate refactoring:

### Massive Duplication
The same scanner logic appears in three or more places. Technical indicators are identically implemented in oracore_engine.py, oracore_daily_operator.py, and scanner_ml_integration.py. ML model loading code is scattered across these same files with no shared library. This duplication makes maintenance a nightmare and increases the risk of inconsistent behavior.

### Hardcoded Values Everywhere
Watchlists are hardcoded in at least five different files. The ML scanner files all contain ["SHPH", "CSTE", "POAI", "MLGO"] while the basic scanner has ["TSLA", "PLTR", "SOFI", "MARA", "RIOT", "AMD", "GME"]. The Discord webhook URL is exposed in plaintext in oracore_alert_dispatcher.py. MongoDB credentials are repeated across multiple .env files. These hardcoded values make configuration changes require hunting through the entire codebase.

### Inconsistent Naming
Files like oracore_engine.py and run_scanner.py perform similar functions but follow completely different naming conventions. The same concept appears as "breakout_probability" in one place and "simulated_roi" in another. Functions like apply_indicators() are duplicated with identical implementations but exist in different locations. This inconsistency makes the codebase difficult to navigate and understand.

### No Separation of Concerns
Single files attempt to do everything. The run_scanner.py file mixes data fetching, business logic, database operations, and console output all in one place. There's no data access layer, so MongoDB queries are scattered inline throughout the code. No service layer exists to separate business logic from I/O operations. No configuration management system exists to centralize settings.

### Disconnected Systems
Two complete scanner implementations exist that don't communicate with each other. The API returns fake data instead of reading from MongoDB where real data exists. The dashboard and alerts use entirely different data sources despite supposedly being part of the same system.

Refactoring this code is essential and will involve creating a centralized configuration file, building a shared indicator library, implementing a single scanner with strategy pattern, adding a database abstraction layer, establishing environment based configuration, and defining a unified data model across all components.

## Database Assessment

MongoDB currently stores our data without indexes, schema validation, or historical preservation. Each scan overwrites previous data, eliminating our ability to backtest or train models. Based on my analysis in the Comprehensive Database Strategy Report, I strongly recommend migrating to PostgreSQL with TimescaleDB for these reasons:

1. **Immediate Benefits:** Millisecond queries, full data integrity, automatic history retention
2. **ML Readiness:** Native support for time series data and direct pandas integration
3. **Scalability:** Can grow 100x without re architecture
4. **Simplicity:** One engineer can manage the entire system

The migration will take approximately 2 to 3 weeks but provides the foundation for everything we want to build.

## Next Week's Implementation Plan

I will begin implementing the PostgreSQL database and establishing reliable data collection from Yahoo Finance. My immediate goals are:

1. Set up the PostgreSQL + TimescaleDB instance with the ML ready schema
2. Create data ingestion pipeline for Yahoo Finance
3. Implement the signals, candles, and outcomes tables
4. Begin collecting clean historical data for model training

## Requirements from Stakeholders

To proceed effectively, I need Earl to provide:

### Stock Selection
Which specific stocks should we track? The current system monitors two different sets (major stocks vs penny stocks) without coordination. I need a unified watchlist with priority rankings.

### Data Collection Specifications
You mentioned wanting 1min, 5min, 15min, 1hr, and 4hr candles with volume data. This gives us a baseline, but I recommend we capture significantly more to enable proper analysis:
- Bid/ask spreads for execution cost analysis
- Technical indicators at signal time (beyond just RSI and MACD)
- Market session context (pre market, regular, after hours)
- Relative volume compared to historical averages
- Market regime indicators (VIX levels, SPY performance)
- News sentiment scores if available

Please specify any additional data points you consider essential.

### Trade Journal Requirements
Earl and Sophia provided these baseline fields:

**Buy Side:**
- Ticker symbol
- Date/time of entry
- Volume of entire stock at entry
- MACD value
- RSI value
- Purchase amount in dollars
- Number of shares acquired

**Sell Side:**
- Ticker symbol
- Date/time of exit
- Volume of entire stock at exit
- MACD value
- RSI value
- Sale price
- Percentage gain/loss calculated
- Shares sold (as percentage of position)
- Take profit levels: TP1 (25% sold), TP2 (50% sold), TP3 (75-100% sold)

This provides a foundation, but I recommend we expand this to include:
- Stop loss levels and whether they were hit
- Reason codes for entry and exit decisions
- Market conditions at time of trade
- Slippage between expected and actual fill prices
- Commission and fee tracking
- Time held per position segment
- Maximum favorable and adverse excursions during the trade

Please review and let me know what additional fields would help your post trade analysis.

## Path to Profitability

It's important to me that this system begins generating returns as soon as possible. We are laying a foundation that enables both immediate alerts and future automation. The progression I envision:

**Phase 1:** Create the PostgreSQL database with proper schema and begin collecting comprehensive historical data. This foundational work enables everything else.

**Phase 2:** Deploy improved scanners that combine our basic math approach with ML predictions, writing to the new database with full history retention.

**Phase 3:** Implement semi automated trading where the system suggests position sizes and exit strategies but requires human confirmation.

**Phase 4:** Full automation for qualified setups based on backtested strategies and risk parameters.

## Critical Success Factors

1. **Database First:** Implement PostgreSQL to capture proper trading history
2. **Code Refactoring:** Clean up the spaghetti code for maintainability
3. **Unified Architecture:** Merge our two scanner systems into one coherent pipeline
4. **Comprehensive Data:** Capture all fields needed for ML training and analysis
5. **Feedback Loop:** Record human trading decisions to improve models

## Conclusion

Oraca contains sophisticated components including ML models and technical analysis capabilities, but these pieces operate in isolation within poorly structured code. By implementing the PostgreSQL migration and refactoring the codebase, we can transform this into a profitable alert system. The infrastructure we build now will support both immediate human guided trading and eventual full automation, ensuring we generate returns while building toward the larger vision.

With focused effort on database implementation and code refactoring rather than new feature development, we can have a solid foundation for reliable trading alerts and comprehensive trade journaling.