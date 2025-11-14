"""
Universe curator service.
Fetches Massive reference data, filters tickers by price band, and persists the curated universe.
"""
from __future__ import annotations
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple

from massive import RESTClient

from market_data.config import Config
from market_data.models.universe_symbol import UniverseSymbol
from market_data.repositories.symbol_repository import SymbolRepository
from market_data.repositories.universe_repository import UniverseRepository
from market_data.utils.logger import get_logger


@dataclass
class PriceSnapshot:
    price: Decimal
    timestamp: Optional[datetime]
    source: str


class UniverseCurator:
    """Coordinates fetching, filtering, and persisting curated symbols."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(__name__)
        self.symbol_repo = SymbolRepository(config)
        self.universe_repo = UniverseRepository(config)
        self.api_key = config.massive_api_key
        self.rest_client = RESTClient(
            api_key=self.api_key,
            base=config.massive.base_url.rstrip("/"),
        )

    async def refresh(self) -> Dict[str, int]:
        """
        Refresh the curated universe.

        Returns:
            Summary counts for logging/monitoring.
        """
        run_started = datetime.now(timezone.utc)

        ticker_map = await asyncio.to_thread(self._fetch_ticker_metadata)
        snapshot_map = await asyncio.to_thread(self._fetch_price_snapshots)

        summary = await self._persist_universe(
            run_started,
            ticker_map,
            snapshot_map,
        )

        retired = await self.universe_repo.mark_stale_entries(
            refreshed_before=run_started,
            status="RETIRED",
            reason="stale_after_refresh",
        )
        summary["retired"] = retired
        self.logger.info(
            "Universe refresh complete: processed=%s active=%s temp_dropped=%s retired=%s skipped_price=%s",
            summary["processed"],
            summary["active"],
            summary["temp_dropped"],
            summary["retired"],
            summary["skipped_price"],
        )
        return summary

    def _fetch_ticker_metadata(self) -> Dict[str, Dict[str, Any]]:
        """Fetch all active US equity tickers."""
        tickers: Dict[str, Dict[str, Any]] = {}
        iterator = self.rest_client.list_tickers(
            market="stocks",
            active=True,
            type="CS",
            order="asc",
            sort="ticker",
            params={
                "perpage": self.config.universe.ticker_page_limit,
                "locale": "us",
            },
        )
        page = 0
        for item in iterator:
            ticker = (item.ticker or "").upper()
            if not ticker:
                continue
            tickers[ticker] = asdict(item)
            page += 1
            if page % self.config.universe.ticker_page_limit == 0:
                self.logger.info("Loaded %s tickers so far", page)

        self.logger.info("Fetched %s ticker metadata rows", len(tickers))
        return tickers

    def _fetch_price_snapshots(self) -> Dict[str, PriceSnapshot]:
        """Fetch latest price snapshots for all stocks."""
        prices: Dict[str, PriceSnapshot] = {}
        snapshots = self.rest_client.get_snapshot_all(
            market_type="stocks",
            include_otc=False,
        ) or []

        for snapshot in snapshots:
            ticker = (snapshot.ticker or "").upper()
            if not ticker:
                continue

            price_info = self._extract_price(snapshot)
            if not price_info:
                continue

            price_value, timestamp, source = price_info
            prices[ticker] = PriceSnapshot(
                price=price_value,
                timestamp=timestamp,
                source=source,
            )

        self.logger.info("Fetched price snapshots for %s tickers", len(prices))
        return prices

    def _extract_price(self, snapshot) -> Optional[Tuple[Decimal, Optional[datetime], str]]:
        """Derive a representative price from a ticker snapshot."""
        if snapshot.last_trade and snapshot.last_trade.price is not None:
            ts = self._safe_epoch(
                getattr(snapshot.last_trade, "sip_timestamp", None)
                or getattr(snapshot.last_trade, "last_updated", None)
            )
            return Decimal(str(snapshot.last_trade.price)), ts, "last_trade"

        if snapshot.min and snapshot.min.close is not None:
            return (
                Decimal(str(snapshot.min.close)),
                self._safe_epoch(snapshot.min.timestamp),
                "min_close",
            )

        if snapshot.day and snapshot.day.close is not None:
            return (
                Decimal(str(snapshot.day.close)),
                self._safe_epoch(snapshot.day.timestamp),
                "day_close",
            )

        if snapshot.prev_day and snapshot.prev_day.close is not None:
            return (
                Decimal(str(snapshot.prev_day.close)),
                self._safe_epoch(snapshot.prev_day.timestamp),
                "prev_day_close",
            )

        return None

    async def _persist_universe(
        self,
        run_started: datetime,
        tickers: Dict[str, Dict[str, Any]],
        price_map: Dict[str, PriceSnapshot],
    ) -> Dict[str, int]:
        """Apply filters and upsert curated symbols."""
        summary = {
            "processed": 0,
            "active": 0,
            "temp_dropped": 0,
            "retired": 0,
            "skipped_price": 0,
        }

        price_min = Decimal(str(self.config.universe.price_min))
        price_max = Decimal(str(self.config.universe.price_max))
        buffer_pct = Decimal(str(self.config.universe.price_buffer_pct))
        buffer_min = price_min * (Decimal("1") - buffer_pct)
        buffer_max = price_max * (Decimal("1") + buffer_pct)

        for ticker, meta in tickers.items():
            price_info = price_map.get(ticker)
            if not price_info:
                summary["skipped_price"] += 1
                continue

            price_status, within_price = self._evaluate_price(
                price_info.price,
                price_min,
                price_max,
                buffer_min,
                buffer_max,
            )
            float_status, within_float = "UNKNOWN", True

            status, status_reason = self._determine_status(
                within_price,
                within_float,
                price_status,
                float_status,
            )

            symbol = await self.symbol_repo.get_or_create(
                ticker=ticker,
                exchange=meta.get("primary_exchange"),
            )

            metadata = {
                "name": meta.get("name"),
                "exchange": meta.get("primary_exchange"),
                "locale": meta.get("locale"),
                "cik": meta.get("cik"),
                "composite_figi": meta.get("composite_figi"),
                "share_class_figi": meta.get("share_class_figi"),
                "price_source": price_info.source,
            }

            entry = UniverseSymbol(
                symbol_id=symbol.id,
                ticker=ticker,
                float_shares=None,
                preferred_float=False,
                last_price=price_info.price,
                price_status=price_status,
                float_status=float_status,
                status=status,
                status_reason=status_reason,
                last_price_at=price_info.timestamp,
                float_updated_at=None,
                refreshed_at=run_started,
                metadata=metadata,
            )

            await self.universe_repo.upsert(entry)
            summary["processed"] += 1
            if status == "ACTIVE":
                summary["active"] += 1
            else:
                summary["temp_dropped"] += 1

        return summary

    @staticmethod
    def _safe_epoch(raw: Optional[int]) -> Optional[datetime]:
        if raw is None:
            return None
        try:
            value = int(raw)
        except (TypeError, ValueError):
            return None

        if value > 1_000_000_000_000:
            seconds = value / 1_000.0
        else:
            seconds = value

        if seconds <= 0:
            return None

        try:
            return datetime.fromtimestamp(seconds, tz=timezone.utc)
        except (OverflowError, ValueError):
            return None

    @staticmethod
    def _evaluate_price(
        price: Decimal,
        price_min: Decimal,
        price_max: Decimal,
        buffer_min: Decimal,
        buffer_max: Decimal,
    ) -> Tuple[str, bool]:
        if price_min <= price <= price_max:
            return "IN_BAND", True
        if buffer_min <= price <= buffer_max:
            return "BUFFER", False
        return "OUT_OF_BAND", False

    @staticmethod
    def _determine_status(
        within_price: bool,
        within_float: bool,
        price_status: str,
        float_status: str,
    ) -> Tuple[str, str]:
        if within_price and within_float:
            return "ACTIVE", "meets_criteria"

        reasons = []
        if not within_price:
            reasons.append(f"price_{price_status.lower()}")
        if not within_float:
            reasons.append(f"float_{float_status.lower()}")
        return "TEMP_DROPPED", ",".join(reasons)


async def refresh_universe(config: Config):
    """Helper for scripts/tests."""
    curator = UniverseCurator(config)
    return await curator.refresh()
