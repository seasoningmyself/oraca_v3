"""
Check float/outstanding_shares coverage for a sample of tickers from FMP.

Pulls up to `limit` tickers from /stable/shares-float-all (single page)
and reports how many have non-null floatShares and outstandingShares.

Usage:
    python -m market_data.scripts.float_coverage --limit 1000
"""
from __future__ import annotations

import argparse
import requests

from market_data.config import get_config
from market_data.utils.logger import get_logger


logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Check float/outstanding coverage from FMP.")
    parser.add_argument("--limit", type=int, default=1000, help="Number of tickers to fetch (single page).")
    return parser.parse_args()


def main():
    args = parse_args()
    config = get_config()
    api_key = config.fmp_api_key
    base = config.fmp.base_url.rstrip("/")
    url = f"{base}/stable/shares-float-all"

    fetched = []
    page = 0
    while len(fetched) < args.limit:
        params = {"page": page, "limit": min(1000, args.limit - len(fetched)), "apikey": api_key}
        resp = requests.get(url, params=params, timeout=config.fmp.timeout_seconds)
        if resp.status_code != 200:
            logger.error("FMP request failed on page %s: %s %s", page, resp.status_code, resp.text[:200])
            break
        payload = resp.json()
        if not isinstance(payload, list) or not payload:
            break
        fetched.extend(payload)
        page += 1

    total = len(fetched)
    float_hits = sum(1 for r in fetched if r.get("floatShares") is not None)
    outstanding_hits = sum(1 for r in fetched if r.get("outstandingShares") is not None)

    print(f"Total tickers fetched: {total} (requested up to {args.limit})")
    if total:
        print(f"FloatShares present: {float_hits} ({float_hits/total*100:.2f}%)")
        print(f"OutstandingShares present: {outstanding_hits} ({outstanding_hits/total*100:.2f}%)")
    else:
        print("No data returned from FMP.")


if __name__ == "__main__":
    main()
