from market_data.services.scan_service import ScanService
from market_data.scanners.interfaces import Detection, Detector, Scorer


class DummyDetector(Detector):
    def __init__(self, detection: Detection):
        self.detection = detection
        self.calls = 0

    async def detect(self, symbol_id: int, ticker: str, timeframe: str):
        self.calls += 1
        return self.detection


class DummyScorer(Scorer):
    def __init__(self, score: float):
        self.value = score
        self.calls = 0

    def score(self, detection: Detection) -> float:
        self.calls += 1
        return self.value


class FakeSignalRepo:
    def __init__(self):
        self.calls = 0
        self.last_payload = None

    async def upsert_signal(
        self,
        *,
        symbol_id,
        timeframe,
        fired_at,
        strategy,
        direction,
        entry_price,
        confidence,
        stop_loss,
        take_profit,
        features,
        metadata,
    ):
        self.calls += 1
        self.last_payload = {
            "symbol_id": symbol_id,
            "timeframe": timeframe,
            "fired_at": fired_at,
            "strategy": strategy,
            "direction": direction,
            "entry_price": entry_price,
            "features": features,
            "metadata": metadata,
        }
        return 123


class FakeSymbolRepo:
    def __init__(self, mapping):
        self.mapping = mapping

    async def get_by_ticker(self, ticker, exchange=None):
        return self.mapping.get(ticker)


class FakeUniverseRepo:
    def __init__(self, tickers):
        self.tickers = tickers

    async def list_by_status(self, statuses):
        return [type("U", (), {"ticker": t}) for t in self.tickers]


class FakeCandleRepo:
    pass


def test_scan_service_orchestrator():
    # Dummy detection
    detection = Detection(
        symbol_id=1,
        ticker="TEST",
        timeframe="15m",
        fired_at="2025-01-01T00:00:00Z",
        side="LONG",
        entry_price=100.0,
        features={"foo": "bar"},
        metadata={"strategy": "dummy"},
    )
    detector = DummyDetector(detection)
    scorer = DummyScorer(42.0)
    signal_repo = FakeSignalRepo()
    symbol_repo = FakeSymbolRepo({"TEST": type("S", (), {"id": 1})})
    universe_repo = FakeUniverseRepo(["TEST"])
    candle_repo = FakeCandleRepo()

    service = ScanService(
        symbol_repo=symbol_repo,
        universe_repo=universe_repo,
        signal_repo=signal_repo,
        candle_repo=candle_repo,
    )

    import asyncio

    count = asyncio.run(service.run(detector=detector, scorer=scorer, timeframe="15m", tickers=["TEST"]))

    assert count == 1
    assert detector.calls == 1
    assert scorer.calls == 1
    assert signal_repo.calls == 1
    payload = signal_repo.last_payload
    assert payload["strategy"] == "dummy"
    assert payload["direction"] == detection.side
    assert payload["features"]["foo"] == "bar"
    assert payload["metadata"]["score"] == 42.0
