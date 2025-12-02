"""
Simple Flask UI (synchronous) to list:
  - Universe (manual_watchlist) tickers passing price/volume filters (uses latest 15m candle)
  - Recent signals for Breakout20, Grail, Black Reign (last 24 hours) from the signals table

Run:
    PYTHONPATH=. flask --app market_data.gui.app run --host 0.0.0.0 --port 8001
"""
from __future__ import annotations

import psycopg2
import psycopg2.extras
from flask import Flask, request, render_template_string

from market_data.config import get_config

app = Flask(__name__)


PAGE_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <title>Scanner Dashboard</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; background: #fafafa; }
      h2 { margin-top: 30px; }
      table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
      th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
      th { background: #f0f0f0; }
      .card { background: #fff; padding: 15px; margin-bottom: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Universe (manual watchlist)</h2>
      <p>Price {{ price_min }}-{{ price_max }}, Volume >= {{ min_volume }} | Matches: {{ universe_matches|length }}</p>
      <table>
        <tr><th>Ticker</th><th>Close</th><th>Volume</th><th>Last Candle</th></tr>
        {% for row in universe_matches %}
        <tr>
          <td>{{ row.ticker }}</td>
          <td>{{ "%.4f"|format(row.close) }}</td>
          <td>{{ row.volume }}</td>
          <td>{{ row.ts }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>

    <div class="card">
      <h2>Breakout20 Signals</h2>
      <p>Matches: {{ breakout_hits|length }}</p>
      <table>
        <tr><th>Ticker</th><th>Timeframe</th><th>Price</th><th>Score</th><th>Fired At</th></tr>
        {% for row in breakout_hits %}
        <tr>
          <td>{{ row.ticker }}</td>
          <td>{{ row.timeframe }}</td>
          <td>{{ "%.4f"|format(row.entry_price) }}</td>
          <td>{{ row.metadata.get('score', '') }}</td>
          <td>{{ row.fired_at }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>

    <div class="card">
      <h2>Grail Signals</h2>
      <p>Matches: {{ grail_hits|length }}</p>
      <table>
        <tr><th>Ticker</th><th>Timeframe</th><th>Price</th><th>Score</th><th>Fired At</th></tr>
        {% for row in grail_hits %}
        <tr>
          <td>{{ row.ticker }}</td>
          <td>{{ row.timeframe }}</td>
          <td>{{ "%.4f"|format(row.entry_price) }}</td>
          <td>{{ row.metadata.get('score', '') }}</td>
          <td>{{ row.fired_at }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>

    <div class="card">
      <h2>Black Reign Signals</h2>
      <p>Matches: {{ blackreign_hits|length }}</p>
      <table>
        <tr><th>Ticker</th><th>Timeframe</th><th>Price</th><th>Score</th><th>Fired At</th></tr>
        {% for row in blackreign_hits %}
        <tr>
          <td>{{ row.ticker }}</td>
          <td>{{ row.timeframe }}</td>
          <td>{{ "%.4f"|format(row.entry_price) }}</td>
          <td>{{ row.metadata.get('score', '') }}</td>
          <td>{{ row.fired_at }}</td>
        </tr>
        {% endfor %}
      </table>
    </div>
  </body>
</html>
"""


def get_connection():
    cfg = get_config()
    dsn = cfg.db_dsn
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def load_universe(price_min: float, price_max: float, min_volume: int):
    """
    Load tickers from manual_watchlist and join latest 1d candle.
    """
    sql = """
    SELECT mw.ticker, c.close, c.volume, c.ts
    FROM manual_watchlist mw
    JOIN symbols s ON s.ticker = mw.ticker
    JOIN LATERAL (
        SELECT close, volume, ts
        FROM candles
        WHERE candles.symbol_id = s.id AND candles.timeframe = '1d'
        ORDER BY ts DESC
        LIMIT 1
    ) c ON TRUE
    WHERE c.close BETWEEN %s AND %s
      AND c.volume >= %s
    ORDER BY mw.ticker;
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (price_min, price_max, min_volume))
        rows = cur.fetchall()
    return rows


def load_signals(strategy: str, since_hours: int = 24, limit: int = 200):
    """
    Load recent signals for a strategy from the signals table.
    """
    sql = """
    SELECT s.id, s.symbol_id, sym.ticker, s.timeframe, s.fired_at,
           s.direction, s.entry_price, s.features, s.metadata
    FROM signals s
    JOIN symbols sym ON sym.id = s.symbol_id
    WHERE s.strategy = %s AND s.fired_at >= (NOW() - INTERVAL '%s hours')
    ORDER BY s.fired_at DESC
    LIMIT %s;
    """
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (strategy, since_hours, limit))
        rows = cur.fetchall()
    return rows


@app.route("/")
def index():
    price_min = float(request.args.get("price_min", 0.40))
    price_max = float(request.args.get("price_max", 50.0))
    min_volume = int(request.args.get("min_volume", 40000))

    universe_matches = load_universe(price_min, price_max, min_volume)
    breakout_hits = load_signals("breakout20_v1")
    grail_hits = load_signals("grail_v1")
    blackreign_hits = load_signals("blackreign_v1")

    return render_template_string(
        PAGE_TEMPLATE,
        universe_matches=universe_matches,
        breakout_hits=breakout_hits,
        grail_hits=grail_hits,
        blackreign_hits=blackreign_hits,
        price_min=price_min,
        price_max=price_max,
        min_volume=min_volume,
    )
