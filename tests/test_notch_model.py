"""Model.js for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODEL = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Model.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

CUTOUTS = json.dumps({"panels": [{"connector": "eDP", "width": 3456, "height": 2234, "top": 64}]})


def run(expr):
    js = f"const M=require({json.dumps(str(MODEL))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def test_cutout_on_notched_panel():
    assert run(f"M.cutoutTop(M.parseCutouts({json.dumps(CUTOUTS)}),'eDP-1',1728,{{width:3456,height:2234,transform:0}})") == 32


def test_no_cutout_on_external_or_rotated():
    c = f"M.parseCutouts({json.dumps(CUTOUTS)})"
    assert run(f"M.cutoutTop({c},'DP-3',3440,{{width:3440,height:1440}})") == 0
    assert run(f"M.cutoutTop({c},'eDP-1',1117,{{width:3456,height:2234,transform:1}})") == 0


def test_malformed_cutouts_and_weather():
    assert run("M.parseCutouts('{nope')") == []
    assert run("M.parseWeather('{nope')") is None


def test_idle_slot_rotates_extras_only():
    assert run("[0,6,7,12,13].map(s=>M.idleSlot(s,['weather','watchlist'],6))") == ["weather", "watchlist", "watchlist", "weather", "weather"]
    assert run("M.idleSlot(99,[],6)") == ""
    assert run("M.idleSlot(99,['weather'],6)") == "weather"


def test_idle_cycle_order():
    views = run("[0,23,24,30,31].map(s=>M.idleView(s,['weather'],24,7))")
    assert views == ["clock", "clock", "weather", "weather", "clock"]
    assert run("M.idleView(99,[],24,7)") == "clock"


def test_weather_kinds():
    assert run("[M.weatherKind(0,true),M.weatherKind(0,false),M.weatherKind(63,true),M.weatherKind(73,true),M.weatherKind(95,true)]") == [
        "clear", "night", "rain", "snow", "storm"]


WIDGETS = json.dumps([
    {"id": "a", "section": "left", "x": 8, "width": 100, "visible": True},
    {"id": "b", "section": "left", "x": 108, "width": 50, "visible": True},
    {"id": "m", "section": "right", "x": 1300, "width": 0, "visible": False},
    {"id": "c", "section": "right", "x": 1300, "width": 27, "visible": True},
    {"id": "d", "section": "right", "x": 1327, "width": 27, "visible": True},
])


def test_island_rect_and_blocking():
    island = run("M.islandRect(1728,32)")
    assert island == {"x": 668, "y": 0, "width": 392, "height": 32, "notched": True}
    assert run("M.islandRect(3440,0).width") == 300
    report = run(f"M.layoutReport({WIDGETS},M.islandRect(1728,32))")
    assert report["blocked"] == []
    assert [r["gap"] for r in report["rows"]] == [None, 0, 1142, 0]


def test_expansion_pushes_sections_toward_the_island():
    grown = f"M.expandLayout({WIDGETS},{{m:400,b:600}})"
    report = run(f"M.layoutReport({grown},M.islandRect(1728,32))")
    assert set(report["blocked"]) == {"b", "m"}
    # right section grows leftward: the hidden widget appears left of c
    rows = {r["id"]: r for r in report["rows"]}
    assert rows["m"]["x"] == 900 and rows["c"]["x"] == 1300
