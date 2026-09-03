#!/usr/bin/env python3
"""Watchlist quotes JSON for the lukedaduke.ticker panel."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

TICKERS: list[dict[str, str]] = [
    {"sym": "GC=F", "display_sym": "GOLD", "name": "Gold Spot ($/oz)", "cat": "Gold & Precious Metals", "tv": "OANDA:XAUUSD"},
    {"sym": "GDX", "display_sym": "GDX", "name": "VanEck Gold Miners ETF", "cat": "Gold & Precious Metals", "tv": "AMEX:GDX"},
    {"sym": "GDXJ", "display_sym": "GDXJ", "name": "Junior Gold Miners ETF", "cat": "Gold & Precious Metals", "tv": "AMEX:GDXJ"},
    {"sym": "SIL", "display_sym": "SIL", "name": "Silver Miners ETF", "cat": "Gold & Precious Metals", "tv": "AMEX:SIL"},
    {"sym": "NVDA", "display_sym": "NVDA", "name": "NVIDIA", "cat": "Tech, AI & Space", "tv": "NASDAQ:NVDA"},
    {"sym": "TSLA", "display_sym": "TSLA", "name": "Tesla", "cat": "Tech, AI & Space", "tv": "NASDAQ:TSLA"},
    {"sym": "GOOGL", "display_sym": "GOOGL", "name": "Alphabet", "cat": "Tech, AI & Space", "tv": "NASDAQ:GOOGL"},
    {"sym": "MSFT", "display_sym": "MSFT", "name": "Microsoft", "cat": "Tech, AI & Space", "tv": "NASDAQ:MSFT"},
    {"sym": "AAPL", "display_sym": "AAPL", "name": "Apple", "cat": "Tech, AI & Space", "tv": "NASDAQ:AAPL"},
    {"sym": "RKLB", "display_sym": "RKLB", "name": "Rocket Lab", "cat": "Tech, AI & Space", "tv": "NASDAQ:RKLB"},
    {"sym": "DXYZ", "display_sym": "DXYZ", "name": "Destiny Tech100", "cat": "Tech, AI & Space", "tv": "NYSE:DXYZ"},
    {"sym": "URA", "display_sym": "URA", "name": "Global X Uranium", "cat": "Nuclear & Power", "tv": "AMEX:URA"},
    {"sym": "CCJ", "display_sym": "CCJ", "name": "Cameco", "cat": "Nuclear & Power", "tv": "NYSE:CCJ"},
    {"sym": "CEG", "display_sym": "CEG", "name": "Constellation", "cat": "Nuclear & Power", "tv": "NASDAQ:CEG"},
    {"sym": "VST", "display_sym": "VST", "name": "Vistra", "cat": "Nuclear & Power", "tv": "NYSE:VST"},
    {"sym": "XLE", "display_sym": "XLE", "name": "Energy Select Sector", "cat": "Commodities & Energy", "tv": "AMEX:XLE"},
    {"sym": "DBC", "display_sym": "DBC", "name": "DB Commodity Index", "cat": "Commodities & Energy", "tv": "AMEX:DBC"},
    {"sym": "^TNX", "display_sym": "10Y", "name": "10-Yr US Treasury Yield", "cat": "Macro & Rates", "tv": "TVC:US10Y"},
    {"sym": "TLT", "display_sym": "TLT", "name": "20+ Yr Treasury Bond ETF", "cat": "Macro & Rates", "tv": "NASDAQ:TLT"},
]


def format_price(sym: str, price: float) -> str:
    if sym == "^TNX":
        return f"{price:.2f}%"
    if sym == "GC=F":
        return f"${price:,.1f}"
    return f"${price:.2f}"


def parse_chart(sym: str, payload: dict[str, Any]) -> tuple[float, float]:
    result = payload["chart"]["result"][0]
    meta = result["meta"]
    price = float(meta.get("regularMarketPrice") or 0)
    prev = float(meta.get("chartPreviousClose") or price)
    return price, prev


def fetch_yahoo_chart(sym: str, timeout: float = 3.0) -> dict[str, Any]:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=1d"
    req = urllib.request.Request(url, headers={"User-Agent": "omarchy-plugins/2.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def quote_item(
    item: dict[str, str],
    fetch: Callable[[str], dict[str, Any]],
) -> dict[str, Any]:
    base = {
        "symbol": item["display_sym"],
        "raw_sym": item["sym"],
        "name": item["name"],
        "category": item["cat"],
        "tv_sym": item["tv"],
    }
    try:
        payload = fetch(item["sym"])
        price, prev = parse_chart(item["sym"], payload)
        chg_pct = ((price - prev) / prev) * 100 if prev else 0.0
        return {
            **base,
            "price": format_price(item["sym"], price),
            "change": f"{chg_pct:+.2f}%",
            "positive": chg_pct >= 0,
            "raw_chg": chg_pct,
            "ok": True,
        }
    except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            **base,
            "price": "--",
            "change": "--",
            "positive": True,
            "raw_chg": 0.0,
            "ok": False,
            "error": str(exc),
        }


def collect(fetch: Callable[[str], dict[str, Any]] | None = None) -> dict[str, Any]:
    getter = fetch or fetch_yahoo_chart
    items = [quote_item(item, getter) for item in TICKERS]
    failed = [row for row in items if not row.get("ok")]
    gold = next((x for x in items if x["symbol"] == "GOLD"), None)
    nvda = next((x for x in items if x["symbol"] == "NVDA"), None)
    ura = next((x for x in items if x["symbol"] == "URA"), None)
    summary = (
        f"GOLD {gold['price'] if gold else '--'} · "
        f"NVDA {nvda['change'] if nvda else '--'} · "
        f"URA {ura['change'] if ura else '--'}"
    )
    ok = len(failed) < len(items)
    error = None
    if not ok:
        error = "all quotes failed"
    elif failed:
        error = f"{len(failed)} quotes failed"
    return {
        "ok": ok,
        "error": error,
        "summary": summary,
        "items": items,
        "timestamp": int(time.time()),
        "updated_str": time.strftime("%H:%M:%S"),
    }


def main() -> int:
    print(json.dumps(collect()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
