"""
Financial Modeling Prep client (float shares only).
Lightweight wrapper to fetch float shares with a per-run call budget.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

import requests

from market_data.config import Config
from market_data.utils.logger import get_logger


class FmpClient:
    """Minimal FMP client for float shares."""

    def __init__(self, config: Config):
        if not config.fmp:
            raise ValueError("FMP config missing; ensure market_data/config.yaml has an fmp block")
        self.base_url = config.fmp.base_url.rstrip("/")
        self.api_key = config.fmp_api_key
        self.max_calls = config.fmp.max_calls_per_day
        self.timeout = config.fmp.timeout_seconds
        self.logger = get_logger(__name__)
        self._calls = 0
        self._session = requests.Session()

    def _can_call(self) -> bool:
        return self._calls < self.max_calls

    def _count_call(self):
        self._calls += 1

    def get_float(self, ticker: str) -> Tuple[Optional[int], Optional[datetime], str]:
        """
        Fetch float shares for a single ticker via /stable/shares-float.

        Returns:
            (float_shares, as_of_date, status_reason)
        """
        if not self._can_call():
            return None, None, "limit_reached"

        url = f"{self.base_url}/stable/shares-float"
        params = {"symbol": ticker.upper(), "apikey": self.api_key}
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            self._count_call()
        except Exception as exc:
            self.logger.warning("FMP float request failed for %s: %s", ticker, exc)
            return None, None, "request_error"

        if resp.status_code != 200:
            self.logger.warning(
                "FMP non-200 for %s: status=%s body=%s",
                ticker,
                resp.status_code,
                resp.text[:200],
            )
            return None, None, f"http_{resp.status_code}"

        try:
            payload = resp.json()
        except ValueError:
            return None, None, "invalid_json"

        # Expected FMP shape: [{"symbol": "...", "floatShares": 1234, "date": "2025-02-04 17:01:35"}]
        record = payload[0] if isinstance(payload, list) and payload else None
        if not record:
            return None, None, "empty"

        float_value = record.get("floatShares") or record.get("float_shares") or record.get("float")
        as_of = record.get("date") or record.get("updated") or record.get("period")

        if float_value is None:
            return None, None, "missing_float"

        try:
            float_int = int(float_value)
        except (TypeError, ValueError):
            self.logger.debug("FMP float parse failed for %s: value=%s", ticker, float_value)
            return None, None, "invalid_float"

        as_of_dt: Optional[datetime] = None
        if as_of:
            try:
                as_of_dt = datetime.fromisoformat(str(as_of))
            except ValueError:
                as_of_dt = None

        return float_int, as_of_dt, "ok"

    @property
    def calls_made(self) -> int:
        return self._calls

    def get_float_batch(self, tickers: list) -> dict:
        """
        Fetch float shares for a list of tickers.

        - If one ticker: uses /stable/shares-float with comma param.
        - If multiple: uses /stable/shares-float-all once and filters to requested tickers.

        Returns:
            Dict[ticker] -> (float_shares, as_of_date, status_reason)
        """
        tickers = [t.upper() for t in tickers if t]
        if not tickers:
            return {}

        # For more than one ticker, prefer the all endpoint once and filter results.
        if len(tickers) > 1:
            return self._get_from_all_endpoint(tickers)

        if not self._can_call():
            return {t: (None, None, "limit_reached") for t in tickers}

        symbols = ",".join(tickers)
        url = f"{self.base_url}/stable/shares-float"
        params = {"symbol": symbols, "apikey": self.api_key}
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            self._count_call()
        except Exception as exc:
            self.logger.warning("FMP batch float request failed: %s", exc)
            return {t: (None, None, "request_error") for t in tickers}

        if resp.status_code != 200:
            self.logger.warning(
                "FMP batch non-200: status=%s body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return {t: (None, None, f"http_{resp.status_code}") for t in tickers}

        try:
            payload = resp.json()
        except ValueError:
            return {t: (None, None, "invalid_json") for t in tickers}

        results: dict = {t: (None, None, "missing_float") for t in tickers}
        if isinstance(payload, list):
            for record in payload:
                ticker = (record.get("symbol") or "").upper()
                if not ticker:
                    continue
                float_val = record.get("floatShares") or record.get("float_shares") or record.get("float")
                as_of = record.get("date") or record.get("updated") or record.get("period")

                if float_val is None:
                    results[ticker] = (None, None, "missing_float")
                    continue

                try:
                    float_int = int(float_val)
                except (TypeError, ValueError):
                    results[ticker] = (None, None, "invalid_float")
                    continue

                as_of_dt: Optional[datetime] = None
                if as_of:
                    try:
                        as_of_dt = datetime.fromisoformat(str(as_of))
                    except ValueError:
                        as_of_dt = None

                results[ticker] = (float_int, as_of_dt, "ok")
        return results

    def _get_from_all_endpoint(self, tickers: list) -> dict:
        """Single call to /stable/shares-float-all, filtered to requested tickers."""
        remaining = set(tickers)
        results: dict = {t: (None, None, "missing_float") for t in tickers}

        if not self._can_call():
            return {t: (None, None, "limit_reached") for t in tickers}

        url = f"{self.base_url}/stable/shares-float-all"
        params = {"page": 0, "limit": max(len(tickers), 1000), "apikey": self.api_key}
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            self._count_call()
        except Exception as exc:
            self.logger.warning("FMP all endpoint request failed: %s", exc)
            return {t: (None, None, "request_error") for t in tickers}

        if resp.status_code != 200:
            self.logger.warning(
                "FMP all endpoint non-200: status=%s body=%s",
                resp.status_code,
                resp.text[:200],
            )
            return {t: (None, None, f"http_{resp.status_code}") for t in tickers}

        try:
            payload = resp.json()
        except ValueError:
            return {t: (None, None, "invalid_json") for t in tickers}

        if not isinstance(payload, list):
            return results

        for record in payload:
            ticker = (record.get("symbol") or "").upper()
            if ticker not in remaining:
                continue

            float_val = record.get("floatShares") or record.get("float_shares") or record.get("float")
            as_of = record.get("date") or record.get("updated") or record.get("period")

            if float_val is None:
                results[ticker] = (None, None, "missing_float")
                continue

            try:
                float_int = int(float_val)
            except (TypeError, ValueError):
                results[ticker] = (None, None, "invalid_float")
                continue

            as_of_dt: Optional[datetime] = None
            if as_of:
                try:
                    as_of_dt = datetime.fromisoformat(str(as_of))
                except ValueError:
                    as_of_dt = None

            results[ticker] = (float_int, as_of_dt, "ok")
            remaining.discard(ticker)
            if not remaining:
                break

        return results

    def get_float_all(self, page_size: int = 5000) -> dict:
        """
        Fetch float data for the full universe via paged /stable/shares-float-all.

        Returns:
            Dict[ticker] -> (float_shares, as_of_date, status_reason)
        """
        results: dict = {}
        page = 0
        while self._can_call():
            url = f"{self.base_url}/stable/shares-float-all"
            params = {"page": page, "limit": page_size, "apikey": self.api_key}
            try:
                resp = self._session.get(url, params=params, timeout=self.timeout)
                self._count_call()
            except Exception as exc:
                self.logger.warning("FMP bulk float request failed on page %s: %s", page, exc)
                break

            if resp.status_code != 200:
                self.logger.warning(
                    "FMP bulk non-200 on page %s: status=%s body=%s",
                    page,
                    resp.status_code,
                    resp.text[:200],
                )
                break

            try:
                payload = resp.json()
            except ValueError:
                self.logger.warning("FMP bulk page %s returned invalid JSON", page)
                break

            if not isinstance(payload, list) or not payload:
                break

            for record in payload:
                ticker = (record.get("symbol") or "").upper()
                if not ticker:
                    continue

                float_val = record.get("floatShares") or record.get("float_shares") or record.get("float")
                as_of = record.get("date") or record.get("updated") or record.get("period")

                if float_val is None:
                    results[ticker] = (None, None, "missing_float")
                    continue

                try:
                    float_int = int(float_val)
                except (TypeError, ValueError):
                    results[ticker] = (None, None, "invalid_float")
                    continue

                as_of_dt: Optional[datetime] = None
                if as_of:
                    try:
                        as_of_dt = datetime.fromisoformat(str(as_of))
                    except ValueError:
                        as_of_dt = None

                results[ticker] = (float_int, as_of_dt, "ok")

            page += 1

        if not results:
            self.logger.info("FMP bulk float fetch returned no rows")
        else:
            self.logger.info("FMP bulk float fetched %s tickers across %s calls", len(results), self.calls_made)
        return results
