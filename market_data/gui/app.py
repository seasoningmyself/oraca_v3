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


TABLE_TEMPLATE = """
<!doctype html>
<html>
  <head>
    <title>Filtered Tickers</title>
    <style>
      body { font-family: Arial, sans-serif; padding: 20px; }
      table { border-collapse: collapse; width: 100%; }
      th, td { border: 1px solid #ccc; padding: 8px; text-align: left; }
      th { background: #f0f0f0; }
    </style>
  </head>
  <body>
    <h2>Manual Watchlist (price {{ price_min }}-{{ price_max }}, vol >= {{ min_volume }})</h2>
    <p>Matches: {{ matches|length }}</p>
    <table>
      <tr>
        <th>Ticker</th>
        <th>Close</th>
        <th>Volume</th>
        <th>Last Candle</th>
      </tr>
      {% for row in matches %}
      <tr>
        <td>{{ row[0] }}</td>
        <td>{{ "%.4f"|format(row[1]) }}</td>
        <td>{{ row[2] }}</td>
        <td>{{ row[3] }}</td>
      </tr>
      {% endfor %}
    </table>
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


@app.route("/")
def index():
    price_min = float(request.args.get("price_min", 0.40))
    price_max = float(request.args.get("price_max", 50.0))
    min_volume = int(request.args.get("min_volume", 40000))

    matches = asyncio.run(get_matches(price_min, price_max, min_volume))
    return render_template_string(
        TABLE_TEMPLATE,
        matches=matches,
        price_min=price_min,
        price_max=price_max,
        min_volume=min_volume,
    )
