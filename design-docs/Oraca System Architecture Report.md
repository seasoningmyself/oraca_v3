# Oraca System Architecture Report: Data Pipeline, Scanners, API, and Integrations
**Prepared by:** Ennis M. Salam  
**Client:** Intertwined Investments

## 1. Executive Summary

I have completed a comprehensive analysis of the OraCore/Oraca trading system's data pipeline, scanning engines, API infrastructure, and Discord integration. The system currently operates with two parallel scanner implementations: a production-ready basic scanner that feeds a working dashboard, and a prototype ML-based scanner that is not yet fully integrated. I discovered a critical disconnect where Discord alerts receive randomized mock data rather than real trading signals, despite having functional scanners and stored predictions in MongoDB. This report provides a detailed breakdown of each component and their interconnections.

## 2. Data Source and Collection Pipeline

### Primary Data Source
The entire system uses Yahoo Finance as its sole data provider through the yfinance Python library. I found no Think or Swim integration despite initial assumptions. Yahoo Finance provides free, reliable market data that feeds all system components.

### Data Collection Architecture
The system retrieves market data through two distinct pipelines:

**Production Pipeline (Basic Scanner):**
- Downloads 5 days of 30-minute candles
- Processes high-volume tickers: TSLA, PLTR, SOFI, MARA, RIOT, AMD, GME
- Stores results directly in MongoDB Atlas

**Prototype Pipeline (ML Scanner):**
- Downloads 60 days of 15-minute interval historical data
- Focuses on penny stocks: SHPH, CSTE, POAI, MLGO
- Currently disconnected from production systems

## 3. Scanner Systems Analysis

I identified two separate scanner implementations operating in parallel:

### Basic Math Scanner (Active/Production)
**Location:** Breakout_Plus20_Scanner/run_scanner.py  
**Status:** Currently in production use

The basic scanner implements straightforward breakout detection logic:
- Identifies when current price exceeds the highest price from the last 10 periods
- Confirms breakout with volume exceeding 1.5x average volume
- Calculates ROI as (current_price - breakout_level) / breakout_level
- Writes results to MongoDB collection 'prediction_data'

This scanner runs reliably and feeds real data to the dashboard visualization.

### ML Scanner System (Prototype/Incomplete)
**Location:** oracore_engine.py, oracore_daily_operator.py  
**Status:** Work in progress, not integrated

The ML scanner represents a more sophisticated approach:

**Technical Indicators Calculated:**
- RSI (Relative Strength Index, 14-period)
- MACD (Moving Average Convergence Divergence)
- Simple Moving Averages (20, 50, 200-day)
- ATR (Average True Range)
- Stochastic RSI
- Bollinger Band Width

**Feature Engineering Process:**
The system converts these raw indicators into ML-ready features including RSI values, MACD differences and signals, ATR volatility measures, distance from SMA20 for momentum, Bollinger Band width for volatility, and StochRSI momentum oscillator readings.

**Model Architecture:**
Two pretrained models loaded via joblib:
- Random Forest Classifier generates breakout probability (0-100%)
- Linear Regression predicts target return percentage

**Training Process:**
Models retrain using 120 days of 15-minute interval data from Yahoo Finance with artificial labels based on future price movements. The Random Forest uses 100 estimators for classification while Linear Regression handles profit target estimation. Training labels define breakouts as price increases greater than 10% within the next 5 periods.

## 4. API and Dashboard Infrastructure

I discovered two separate, disconnected components that should be unified:

### Dashboard Component
**Location:** Breakout_Plus20_Scanner/dashboard.py  
**Type:** Dash/Flask web application  
**Function:** Displays visual charts of breakout predictions

The dashboard successfully:
- Reads directly from MongoDB Atlas (OraCore database)
- Presents bar charts showing predicted ROI per ticker
- Updates in real-time without caching
- Runs on localhost (typically http://127.0.0.1:8050)

### API Bridge Component
**Location:** oracore_api_bridge.py  
**Type:** FastAPI REST API  
**Critical Issue:** Returns simulated/random data

I found that the API bridge contains hardcoded random number generation:
```python
breakout_probability=round(random.uniform(0.5, 0.95), 3)
target_return=round(random.uniform(10, 75), 2)
```

This mock API was intended as a placeholder but remains in use. The endpoint (http://127.0.0.1:8000/forecast) serves fake forecasts to the Discord alert system rather than real scanner predictions.

### The Disconnect
The active system flow shows:
- Yahoo Finance data flows to Basic Scanner
- Scanner writes to MongoDB
- Dashboard reads and displays MongoDB data
- Data remains isolated, never reaching Discord

Meanwhile, the broken system flow reveals:
- API Bridge generates random numbers
- Alert Dispatcher polls fake API
- Discord receives meaningless alerts

## 5. Discord Integration Analysis

### Alert Dispatcher Implementation
**Location:** oracore_alert_dispatcher.py  
**Webhook:** Discord webhook URL for channel notifications

The Discord integration implements a monitoring loop that:
- Polls the API endpoint every 60 seconds
- Fetches market forecasts (currently fake data)
- Filters alerts for breakout probability exceeding 75%
- Maintains state to prevent duplicate notifications
- Formats alerts with ticker symbol, breakout probability, and target return

### Alert Format Structure
Alerts follow a consistent format:
```
New Breakout Alert: [TICKER]
Breakout Probability: XX.XX%
Target Return: XX.XX%
```

The system includes deduplication logic that only sends alerts when breakout probability changes for a given ticker, preventing channel spam.

### Integration Gap
While the Discord webhook and alert formatting work correctly, the system receives randomized data from the disconnected API bridge rather than real scanner results from MongoDB. This renders all Discord alerts meaningless despite having functional scanners and stored predictions.

## 6. MongoDB Atlas Configuration

### Database Structure
- **Cloud Host:** cluster0.ncprd8.mongodb.net
- **Database Name:** OraCore
- **Active Collection:** prediction_data
- **Credentials:** Stored in .env file

### Document Schema
```javascript
{
  "ticker": "TSLA",
  "entry_price": 245.32,
  "prediction": 1,
  "simulated_roi": 0.15
}
```

The MongoDB instance successfully stores scanner results but lacks proper indexing and schema validation as noted in the previous database report.

## 7. System Integration Status

### Working Components
1. Yahoo Finance data retrieval via yfinance
2. Basic math scanner with price/volume breakout detection
3. MongoDB Atlas storage of predictions
4. Dashboard visualization of stored predictions

### Disconnected Components
1. ML scanner exists but outputs to local pickle files
2. API bridge returns random data instead of MongoDB results
3. Discord alerts receive fake data from mock API
4. ML models trained but not integrated into production pipeline

### Missing Connections
The critical missing link is between MongoDB stored predictions and the API that feeds Discord. The API bridge should query MongoDB for real scanner results instead of generating random numbers.

## 8. Technical Debt and Issues

### Immediate Problems
1. Discord receives fake/random alerts with no correlation to market reality
2. ML scanner and basic scanner operate on different ticker sets with no coordination
3. API bridge contains hardcoded mock data that was never replaced
4. No connection between sophisticated ML models and any production output

### Architectural Issues
1. Two parallel scanner systems with different logic and ticker lists
2. Disconnected data flow between scanner results and alert system
3. Missing orchestration layer to coordinate components
4. No unified configuration management for tickers and thresholds

## 9. Data Flow Summary

### Current State (Actual)
```
Yahoo Finance -> Basic Scanner -> MongoDB -> Dashboard (visible)
                                           \-> (data trapped here)

Random Generator -> Mock API -> Alert Dispatcher -> Discord (fake alerts)
```

### Intended State (Should Be)
```
Yahoo Finance -> Scanner -> MongoDB -> API -> Alert Dispatcher -> Discord
                                    \-> Dashboard
```

## 10. Recommendations

### Immediate Actions Required
1. Replace mock API bridge with MongoDB query logic
2. Connect Discord alerts to real scanner data
3. Unify scanner ticker lists and scheduling
4. Remove random number generation from production code

### Integration Path
1. Modify oracore_api_bridge.py to query MongoDB prediction_data collection
2. Standardize data format between scanners
3. Implement proper API endpoints for both dashboard and Discord
4. Add monitoring to verify alert accuracy

### Future Enhancements
1. Integrate ML scanner predictions alongside basic scanner
2. Implement A/B testing between scanner strategies
3. Add feedback loop from Discord user reactions to model training
4. Create unified configuration system for all components

## Conclusion

The OraCore/Oraca system contains sophisticated components including ML models, technical indicator calculations, and multiple scanner implementations. However, these components operate in isolation with critical disconnects preventing real trading signals from reaching users through Discord. The most urgent issue is that production Discord alerts contain randomized fake data despite having functional scanners storing real predictions in MongoDB. Fixing the API bridge to query actual MongoDB data would immediately restore system functionality and provide real value to traders monitoring the Discord channel.