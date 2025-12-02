"""
Simple Flask UI to list manual_watchlist tickers that pass price/volume filters.

Filters (defaults):
    - price between 0.40 and 50
    - daily volume >= 40,000

It uses the latest 1d candle stored in the DB per ticker. Run:
    PYTHONPATH=. flask --app market_data.gui.app run

Pass query params to override filters, e.g.:
    http://localhost:5000/?price_min=0.5&price_max=20&min_volume=100000
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import List, Tuple

from flask import Flask, request, render_template_string

from market_data.config import get_config
from market_data.repositories.base_repository import BaseRepository
from market_data.repositories.candle_repository import CandleRepository
from market_data.repositories.symbol_repository import SymbolRepository

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
          <td>{{ row[0] }}</td>
          <td>{{ "%.4f"|format(row[1]) }}</td>
          <td>{{ row[2] }}</td>
          <td>{{ row[3] }}</td>
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


async def fetch_manual_tickers(repo: BaseRepository) -> List[str]:
    rows = await repo.fetch("SELECT ticker FROM manual_watchlist ORDER BY ticker")
    return [r["ticker"] for r in rows]


async def latest_close_vol(candle_repo: CandleRepository, symbol_repo: SymbolRepository, ticker: str) -> Tuple[float | None, int | None, str | None]:
    sym = await symbol_repo.get_or_create(ticker, None)
    candle = await candle_repo.get_latest_candle(sym.id, "1d")
    if not candle:
        return None, None, None
    ts_str = candle.ts.isoformat()
    return float(candle.close), int(candle.volume or 0), ts_str


async def get_matches(price_min: float, price_max: float, min_volume: int):
    config = get_config()
    base_repo = BaseRepository(config)
    candle_repo = CandleRepository(config)
    symbol_repo = SymbolRepository(config)

    tickers = await fetch_manual_tickers(base_repo)
    matches = []
    for t in tickers:
        close, vol, ts = await latest_close_vol(candle_repo, symbol_repo, t)
        if close is None or vol is None:
            continue
        if price_min <= close <= price_max and vol >= min_volume:
            matches.append((t, close, vol, ts))

    await BaseRepository.close_pool()
    return matches


# Placeholder hooks for scanner results (no DB integration yet)
def get_scanner_hits(scanner: str):
    # TODO: fetch from signals table when wired
    return []


@app.route("/")
def index():
    price_min = float(request.args.get("price_min", 0.40))
    price_max = float(request.args.get("price_max", 50.0))
    min_volume = int(request.args.get("min_volume", 40000))

    matches = asyncio.run(get_matches(price_min, price_max, min_volume))
    breakout_hits = get_scanner_hits("breakout20")
    grail_hits = get_scanner_hits("grail")
    blackreign_hits = get_scanner_hits("blackreign")
    return render_template_string(
        PAGE_TEMPLATE,
        universe_matches=matches,
        breakout_hits=breakout_hits,
        grail_hits=grail_hits,
        blackreign_hits=blackreign_hits,
        price_min=price_min,
        price_max=price_max,
        min_volume=min_volume,
    )
