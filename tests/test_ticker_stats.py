from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "plugins/lukedaduke.ticker/bin/market_stats.py"


def load():
    spec = importlib.util.spec_from_file_location("market_stats", STATS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _payload(price: float, prev: float) -> dict:
    return {"chart": {"result": [{"meta": {"regularMarketPrice": price, "chartPreviousClose": prev}}]}}


def test_maps_price_and_change() -> None:
    mod = load()

    def fetch(sym: str) -> dict:
        if sym == "NVDA":
            return _payload(100.0, 80.0)
        return _payload(10.0, 10.0)

    data = mod.collect(fetch=fetch)
    assert data["ok"] is True
    nvda = next(x for x in data["items"] if x["symbol"] == "NVDA")
    assert nvda["price"] == "$100.00"
    assert nvda["change"] == "+25.00%"
    assert nvda["positive"] is True


def test_empty_watchlist_ok_true_when_quotes_succeed() -> None:
    mod = load()
    data = mod.collect(fetch=lambda _sym: _payload(1.0, 1.0))
    assert data["ok"] is True
    assert isinstance(data["items"], list)
    assert len(data["items"]) > 0


def test_network_failure_returns_error() -> None:
    mod = load()

    def fetch(_sym: str) -> dict:
        raise URLError("offline")

    data = mod.collect(fetch=fetch)
    assert data["ok"] is False
    assert data["error"]
    assert data["items"]
    assert all(row["price"] == "--" for row in data["items"])
