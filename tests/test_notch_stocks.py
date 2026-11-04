"""Stocks.js and the series half of bin/notch-data for the notch island. No network."""
import importlib.machinery
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
SJ = ROOT / "Stocks.js"
needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

T0 = 1_700_000_000
FIXTURE = {
    "series": {"NVDA": {"1M": {
        "t": [T0, T0 + 86400, T0 + 2 * 86400, T0 + 3 * 86400, "bad", T0 + 5 * 86400],
        "o": [10, 11, 12, 11, 1, 13],
        "h": [11, 12, 13, 12, 1, 14],
        "l": [9, 10, 11, 10, 1, 12],
        "c": [10.5, 11.5, 12.5, None, 1, 13.5],
        "v": [100, 200, 300, 400, 0, 500],
        "prev": 10.0, "interval": "1d",
    }}},
}


def run(expr, tz="UTC"):
    js = f"const S=require({json.dumps(str(SJ))});console.log(JSON.stringify({expr}));"
    env = dict(os.environ, TZ=tz)
    out = subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True, env=env).stdout
    return json.loads(out)


def pts(n):
    return [{"t": i * 1000, "o": i, "h": i + 2, "l": i - 1, "c": i + 1, "v": 10} for i in range(n)]


# ------------------------------------------------------------ series

@needs_node
def test_parse_series_drops_bad_rows():
    s = run(f"S.parseSeries({json.dumps(FIXTURE)},'NVDA','1M')")
    assert [p["c"] for p in s["points"]] == [10.5, 11.5, 12.5, 13.5]
    assert s["points"][0]["t"] == T0 * 1000 and s["prev"] == 10.0 and s["interval"] == "1d"


@needs_node
def test_parse_series_text_and_missing():
    assert run(f"S.parseSeries({json.dumps(json.dumps(FIXTURE))},'NVDA','1M')")["points"]
    assert run(f"S.parseSeries({json.dumps(FIXTURE)},'NVDA','1D')") is None
    assert run(f"S.parseSeries({json.dumps(FIXTURE)},'AAPL','1M')") is None
    assert run("S.parseSeries('{nope','NVDA','1M')") is None
    assert run("S.parseSeries(null,'NVDA','1M')") is None


@needs_node
def test_series_change_1d_uses_prev_close_else_first():
    s = {"points": [{"c": 10}, {"c": 12}], "prev": 8}
    c1 = run(f"S.seriesChange({json.dumps(s)},'1D')")
    assert c1["percent"] == pytest.approx(50.0) and c1["value"] == 4
    c2 = run(f"S.seriesChange({json.dumps(s)},'1M')")
    assert c2["percent"] == pytest.approx(20.0)
    assert run("S.seriesChange(null,'1M')") is None


@needs_node
def test_direction_and_tone():
    assert run("[2,-2,0.001,NaN].map(S.direction)") == ["up", "down", "flat", "flat"]
    assert run("S.toneColor(1)") == run("S.COLORS.up")
    assert run("S.toneColor(-1)") == run("S.COLORS.down")


# ------------------------------------------------------------ scaling

@needs_node
def test_scale_points_maps_to_box_and_inverts_y():
    box = {"w": 100, "h": 50, "left": 0, "right": 10, "top": 5, "bottom": 5}
    sc = run(f"(()=>{{const s=S.scalePoints([{{c:0}},{{c:5}},{{c:10}}],{json.dumps(box)},0,10);return {{xs:s.xs,ys:s.ys,plot:s.plot}}}})()")
    assert sc["xs"] == [0, 45, 90]
    assert sc["ys"] == [45, 25, 5]
    assert sc["plot"] == {"left": 0, "top": 5, "width": 90, "height": 40}


@needs_node
def test_scale_single_point_centered():
    sc = run("S.scalePoints([{c:1}],{w:100,h:40,left:0,right:0,top:0,bottom:0},0,2).xs")
    assert sc == [50]


@needs_node
def test_nice_ticks():
    t = run("S.niceTicks(9.3,48,5)")
    assert t["ticks"] == [0, 10, 20, 30, 40, 50] or t["ticks"][0] <= 9.3 and t["ticks"][-1] >= 48
    assert t["min"] == t["ticks"][0] and t["max"] == t["ticks"][-1]
    steps = {round(b - a, 6) for a, b in zip(t["ticks"], t["ticks"][1:])}
    assert len(steps) == 1
    t2 = run("S.niceTicks(100.1,100.9,4)")
    assert t2["ticks"][0] <= 100.1 and t2["ticks"][-1] >= 100.9
    flat = run("S.niceTicks(5,5,4)")
    assert flat["ticks"][0] < 5 < flat["ticks"][-1]
    assert run("S.niceTicks('x',1,4)")["ticks"] == []


@needs_node
def test_value_range_candles_use_high_low():
    p = pts(3)
    line = run(f"S.valueRange({json.dumps(p)},false)")
    cand = run(f"S.valueRange({json.dumps(p)},true)")
    assert cand["min"] < line["min"] and cand["max"] > line["max"]


@needs_node
def test_aggregate_candles():
    a = run(f"S.aggregate({json.dumps(pts(10))},3)")
    assert len(a) == 3
    assert a[0]["o"] == 0 and a[0]["c"] == 4 and a[0]["h"] == 5 and a[0]["l"] == -1 and a[0]["v"] == 40
    assert a[2]["c"] == 10 and a[2]["t"] == 9000
    assert [x["v"] for x in a] == [40, 30, 30]
    assert len(run(f"S.aggregate({json.dumps(pts(4))},10)")) == 4


@needs_node
def test_nearest_crosshair_lookup():
    xs = [0, 10, 20, 30]
    assert run(f"[-5,0,4,6,14,26,99].map(x=>S.nearest({xs},x))") == [0, 0, 0, 1, 1, 3, 3]
    assert run("S.nearest([],3)") == -1
    assert run("S.nearest([7],3)") == 0


@needs_node
def test_scroll_three_rows_per_notch_and_clamp():
    assert run("S.scrollTarget(0,-120,35,10,70)") == 105
    assert run("S.scrollTarget(105,120,35,10,70)") == 0
    assert run("S.scrollTarget(0,120,35,10,70)") == 0
    assert run("S.scrollTarget(0,-1200,35,4,70)") == 70
    assert run("S.scrollTarget(0,-120,35,2,70)") == 0
    assert run("[S.gridRows(6,3),S.gridRows(7,3),S.gridRows(0,3)]") == [2, 3, 0]


@needs_node
def test_spark_values_downsample():
    v = run(f"S.sparkValues({json.dumps(pts(100))},5)")
    assert len(v) == 5 and v[0] == 1 and v[-1] == 100
    assert len(run(f"S.sparkValues({json.dumps(pts(3))},5)")) == 3


# ------------------------------------------------------------ ranges / settings

@needs_node
def test_range_interval_mapping():
    r = run("S.RANGES.map(x=>[x.key,x.interval])")
    assert r == [["1D", "5m"], ["5D", "30m"], ["1M", "1d"], ["6M", "1d"], ["1Y", "1wk"]]
    assert run("S.validRange('9X')") == "1M" and run("S.validRange('1Y')") == "1Y"
    assert json.loads(run("S.requestJson(['1D','zz','1D','1Y'],12.9)")) == {"ranges": ["1D", "1Y"], "at": 12}


@needs_node
def test_watchlist_fallback_and_edit():
    fin = json.dumps({"watchlist": ["nvda", "AAPL", "aapl", "bad sym!"]})
    assert run(f"S.watchlist(null,{json.dumps(fin)})") == ["NVDA", "AAPL"]
    assert run(f"S.watchlist({{'stocks.watchlist':['spy']}},{json.dumps(fin)})") == ["SPY"]
    assert run(f"S.watchlist({{'stocks.watchlist':[]}},{json.dumps(fin)})") == ["NVDA", "AAPL"]
    assert run("S.addSymbol(['A'],' b ')") == ["A", "B"]
    assert run("S.addSymbol(['A'],'a')") == ["A"]
    assert run("S.addSymbol(['A'],'')") == ["A"]
    assert run("S.removeSymbol(['A','B'],'A')") == ["B"]
    n = run("S.addSymbol(Array.from({length:12},(_, i)=>'S'+i),'X')")
    assert len(n) == 12


@needs_node
def test_settings_defaults_and_overrides():
    d = run("S.settings(null,null,'')")
    assert d == {"watchlist": [], "range": "1M", "style": "line", "prepost": False, "cards": 6}
    s = run("S.settings({'stocks.range':'1Y','stocks.style':'candle','stocks.cards':4},{'stocks.prepost':true,'stocks.cards':9},'')")
    assert s["range"] == "1Y" and s["style"] == "candle" and s["prepost"] is True and s["cards"] == 6
    assert run("S.settings({'stocks.range':'zz','stocks.style':'x'},null,'').range") == "1M"


# ------------------------------------------------------------ formatting

@needs_node
def test_formatting():
    assert run("[206.69,1234.5,25000,0.5].map(S.formatPrice)") == ["206.69", "1,234.50", "25,000", "0.5000"]
    assert run("S.formatPrice('x')") == "--"
    assert run("[2.291,-0.844,0.001,0].map(S.formatChange)") == ["+2.29%", "-0.84%", "0.00%", "0.00%"]
    assert run("[1.5,-1.5,0].map(S.formatDelta)") == ["+1.50", "-1.50", "0.00"]
    assert run("[0,999,1500,2500000,3e9].map(S.formatVolume)") == ["--", "999", "1.5K", "2.50M", "3.00B"]


@needs_node
def test_format_time_by_range():
    ms = 1_730_712_900_000  # 2024-11-04 09:35 UTC
    assert run(f"S.formatTime({ms},'1D',false)") == "Nov 4 09:35"
    assert run(f"S.formatTime({ms},'1D',true)") == "09:35"
    assert run(f"S.formatTime({ms},'5D',true)") == "Nov 4"
    assert run(f"S.formatTime({ms},'1M',false)") == "Nov 4"
    assert run(f"S.formatTime({ms},'1Y',true)") == "Nov 24"
    assert run("S.formatTime('x','1D',false)") == "--"
    assert run("S.axisIndices(100,4)") == [0, 33, 66, 99]
    assert run("S.axisIndices(2,4)") == [0, 1]


def test_qml_text_is_plain_and_colors_are_namespaced():
    import re
    for name in ("StocksTab.qml", "CandleChart.qml", "SparkChart.qml"):
        src = (ROOT / name).read_text()
        assert not re.search(r"(?<![.\w])Color\.", src), name
        for m in re.finditer(r"\bText \{", src):
            block = src[m.end(): m.end() + 400]
            assert "textFormat: Text.PlainText" in block, (name, block[:80])


# ------------------------------------------------------------ bin/notch-data

def load_data():
    loader = importlib.machinery.SourceFileLoader("notch_data", str(ROOT / "bin/notch-data"))
    spec = importlib.util.spec_from_loader("notch_data", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


CHART = {"chart": {"result": [{
    "meta": {"chartPreviousClose": 9.5},
    "timestamp": [1, 2, 3, 4],
    "indicators": {"quote": [{
        "open": [1, None, 3, 4], "high": [2, 3, 4, 5], "low": [0, 1, 2, 3],
        "close": [1.5, 2.5, None, 4.5], "volume": [10, None, 30, 40]}]},
}]}}


def test_parse_chart_drops_null_close_and_fills_gaps():
    nd = load_data()
    s = nd.parse_chart(CHART)
    assert s["t"] == [1, 2, 4] and s["c"] == [1.5, 2.5, 4.5]
    assert s["o"] == [1, 2.5, 4] and s["v"] == [10, 0, 40] and s["prev"] == 9.5
    with pytest.raises(ValueError):
        nd.parse_chart({"chart": {"result": None}})
    with pytest.raises(ValueError):
        nd.parse_chart({"chart": {"result": [{"timestamp": [], "indicators": {"quote": [{}]}}]}})


def test_ranges_match_spec():
    nd = load_data()
    assert {k: v[:2] for k, v in nd.RANGES.items()} == {
        "1D": ("1d", "5m"), "5D": ("5d", "30m"), "1M": ("1mo", "1d"), "6M": ("6mo", "1d"), "1Y": ("1y", "1wk")}
    assert nd.RANGES["1D"][2] == 300 and all(v[2] == 3600 for k, v in nd.RANGES.items() if k != "1D")


def test_refresh_series_rate_limits_backs_off_and_keeps_old(monkeypatch, tmp_path):
    nd = load_data()
    monkeypatch.setattr(nd, "SHELL_FILE", str(tmp_path / "shell.json"))
    monkeypatch.setattr(nd, "REQUEST_FILE", str(tmp_path / "req.json"))
    (tmp_path / "shell.json").write_text(json.dumps({"plugins": [{"id": nd.PLUGIN_ID, "stocks.range": "1M"}]}))
    (tmp_path / "req.json").write_text(json.dumps({"ranges": ["1D", "bogus"], "at": __import__("time").time()}))
    urls = []

    def fake(url):
        urls.append(url)
        if "BAD" in url:
            raise OSError("boom")
        return CHART

    monkeypatch.setattr(nd, "get_json", fake)
    cache = {}
    assert nd.refresh_series(cache, ["AAA", "BAD"]) is True
    assert len(urls) == 4 and any("range=1d&interval=5m" in u for u in urls) and any("range=1mo&interval=1d" in u for u in urls)
    assert not any("range=1y" in u for u in urls)
    assert cache["series"]["AAA"]["1M"]["c"] == [1.5, 2.5, 4.5]
    assert cache["series"]["BAD"]["1M"]["failures"] == 1 and cache["series"]["BAD"]["1M"]["retryAt"] > 0
    # second run: fresh data and backoff both suppress fetches
    urls.clear()
    assert nd.refresh_series(cache, ["AAA", "BAD"]) is False and urls == []
    # an error keeps the old series
    cache["series"]["AAA"]["1D"]["fetchedAt"] = 0
    monkeypatch.setattr(nd, "get_json", lambda url: (_ for _ in ()).throw(OSError("down")))
    nd.refresh_series(cache, ["AAA"])
    assert cache["series"]["AAA"]["1D"]["c"] == [1.5, 2.5, 4.5] and cache["series"]["AAA"]["1D"]["failures"] == 1
    # symbol removed from the watchlist is dropped
    nd.refresh_series(cache, ["AAA"])
    assert "BAD" not in cache["series"]


def test_watchlist_prefers_notch_setting(monkeypatch, tmp_path):
    nd = load_data()
    monkeypatch.setattr(nd, "SHELL_FILE", str(tmp_path / "shell.json"))
    monkeypatch.setattr(nd, "FINANCE_FILE", str(tmp_path / "fin.json"))
    (tmp_path / "fin.json").write_text(json.dumps({"watchlist": ["nvda", "aapl"]}))
    assert nd.watchlist_symbols() == ["NVDA", "AAPL"]
    (tmp_path / "shell.json").write_text(json.dumps({"plugins": [{"id": nd.PLUGIN_ID, "stocks.watchlist": ["spy", "qqq"]}]}))
    assert nd.watchlist_symbols() == ["SPY", "QQQ"]


@needs_node
def test_today_percent_uses_quote_not_range():
    assert run("S.todayPercent({changePercent: 2.3}, {percent: -13.48})") == 2.3
    assert run("S.todayPercent({changePercent: null}, {percent: 1.5})") == 1.5
    assert run("S.todayPercent(null, {percent: -0.5})") == -0.5
    assert run("S.todayPercent(null, null)") is None  # NaN -> null in JSON
