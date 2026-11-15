"""Watchlist.js for the notch island, run through node. No network."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
WL = ROOT / "Watchlist.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

FIXTURE = json.dumps({
    "weather": {"temperature": 60},
    "quotes": {"items": [
        {"symbol": "NVDA", "price": 206.69, "changePercent": 2.291},
        {"symbol": "AAPL", "price": 1234.5, "changePercent": -0.84},
        {"symbol": "BAD", "price": None, "changePercent": 1},
        {"symbol": "", "price": 1, "changePercent": 1},
        {"symbol": "SPY", "price": 500, "changePercent": 0.02},
        {"symbol": "GDX", "price": 60.1, "changePercent": 1.0},
    ]},
})


def run(expr):
    js = f"const W=require({json.dumps(str(WL))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def test_parse_quotes_skips_bad_items():
    q = run(f"W.parseQuotes({json.dumps(FIXTURE)})")
    assert [x["symbol"] for x in q] == ["NVDA", "AAPL", "SPY", "GDX"]


def test_parse_quotes_malformed():
    assert run("W.parseQuotes('{nope')") == []
    assert run("W.parseQuotes('{}')") == []
    assert run("W.parseQuotes('')") == []


def test_format_price():
    assert run("[206.69,1234.5,25000,0.5,12].map(W.formatPrice)") == ["206.69", "1,234.50", "25,000", "0.5000", "12.00"]
    assert run("W.formatPrice('x')") == "--"


def test_format_change():
    assert run("[2.291,-0.84,0.02,-0.04,0].map(W.formatChange)") == ["+2.3%", "-0.8%", "0.0%", "0.0%", "0.0%"]


def test_direction():
    assert run("[2.3,-0.8,0.02,0,NaN].map(W.direction)") == ["up", "down", "flat", "flat", "flat"]


def test_per_slide():
    assert run("[W.perSlide(true,5),W.perSlide(false,5),W.perSlide(false,1)]") == [1, 2, 1]


def test_rotation_wraps():
    assert run("W.slideCount(4,1)") == 4 and run("W.slideCount(5,2)") == 3 and run("W.slideCount(0,2)") == 0
    names = run("[0,1,2,3,4,-1].map(i=>W.slide(['A','B','C','D'],i,1)[0])")
    assert names == ["A", "B", "C", "D", "A", "D"]
    assert run("[0,1,2].map(i=>W.slide(['A','B','C'],i,2))") == [["A", "B"], ["C"], ["A", "B"]]
    assert run("W.slide([],3,2)") == []


def test_helper_parse_spark():
    """bin/notch-data's response parser on a fixture (no network)."""
    import importlib.machinery
    import importlib.util
    loader = importlib.machinery.SourceFileLoader("notch_data", str(ROOT / "bin/notch-data"))
    spec = importlib.util.spec_from_loader("notch_data", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    data = {"spark": {"result": [
        {"symbol": "NVDA", "response": [{"meta": {"regularMarketPrice": 206.69, "regularMarketChangePercent": 2.291}}]},
        {"symbol": "AAPL", "response": [{"meta": {"regularMarketPrice": 110, "previousClose": 100}}]},
        {"symbol": "ZZZ", "response": [{"meta": {}}]},
    ]}}
    out = mod.parse_spark(data, ["AAPL", "NVDA", "ZZZ"])
    assert [q["symbol"] for q in out] == ["AAPL", "NVDA"]
    assert round(out[0]["changePercent"], 6) == 10.0
