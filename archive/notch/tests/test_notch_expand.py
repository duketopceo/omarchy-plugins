"""Expand.js for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

EXPAND = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Expand.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const E=require({json.dumps(str(EXPAND))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def drive(events):
    """Feed events from collapsed; return [(state, timer)] after each."""
    return run(
        f"(()=>{{let s='collapsed';return {json.dumps(events)}.map(e=>{{const r=E.step(s,e);s=r.state;return [r.state,r.timer]}})}})()"
    )


def test_hover_then_timer_expands():
    assert drive(["enter", "timer"]) == [["arming", 150], ["open", 0]]


def test_quick_pass_does_not_expand():
    assert drive(["enter", "leave", "timer"]) == [["arming", 150], ["collapsed", 0], ["collapsed", 0]]


def test_leave_collapses_after_delay():
    assert drive(["enter", "timer", "leave", "timer"]) == [
        ["arming", 150], ["open", 0], ["leaving", 300], ["collapsed", 0]]


def test_reenter_cancels_collapse():
    out = drive(["enter", "timer", "leave", "enter", "timer"])
    assert out[3] == ["open", 0] and out[4] == ["open", 0]


def test_expanded_flag():
    assert run("['collapsed','arming','open','leaving'].map(E.isExpanded)") == [False, False, True, True]


def test_calendar_leap_february():
    grid = run("E.monthGrid(2024,1,0)")  # Feb 2024 starts Thursday, 29 days
    flat = [d for row in grid for d in row if d]
    assert flat == list(range(1, 30))
    assert grid[0] == [0, 0, 0, 0, 1, 2, 3]
    assert all(len(r) == 7 for r in grid)


def test_calendar_non_leap_february_and_monday_start():
    assert run("E.daysInMonth(2023,1)") == 28
    assert run("E.daysInMonth(1900,1)") == 28 and run("E.daysInMonth(2000,1)") == 29
    # Feb 2021 starts Monday and has 28 days: exactly four Monday-first rows
    grid = run("E.monthGrid(2021,1,1)")
    assert len(grid) == 4 and grid[0][0] == 1 and grid[3][6] == 28


def test_calendar_november_2026_and_six_rows():
    grid = run("E.monthGrid(2026,10,0)")  # Nov 1 2026 is a Sunday
    assert grid[0][0] == 1 and grid[-1][:2] == [29, 30]
    assert len(run("E.monthGrid(2026,7,0)")) == 6  # Aug 2026: Sat start, 31 days


def test_weekday_labels():
    assert run("E.weekdayLabels(1)") == ["M", "T", "W", "T", "F", "S", "S"]


def test_panel_sizing():
    assert run("E.panelSize(1728)") == {"width": 460, "height": 240}
    assert run("E.panelSize(300)") == {"width": 284, "height": 240}
    assert run("E.panelSize(0)")["width"] == 460


def test_panel_size_per_tab():
    assert run("E.panelSize(1728, {w: 720, h: 380})") == {"width": 720, "height": 380}
    assert run("E.panelSize(1728, null)") == {"width": 460, "height": 240}
    assert run("E.panelSize(1280, {w: 720, h: 380})")["width"] == 720
    assert run("E.panelSize(600, {w: 720, h: 380})")["width"] == 584


def test_lines():
    w = {"place": "Provo", "temperature": 46, "unit": "°F", "kind": "night"}
    assert run(f"E.weatherLine({json.dumps(w)})") == "Provo  46°F  Clear"
    assert run("E.weatherLine(null)") == ""
    assert run("E.quotesLine(undefined)") == ""
    assert run("E.quotesLine([{symbol:'AAPL',price:190.5,changePercent:1.234}])") == "AAPL 190.50 +1.2%"
    assert run("E.parseWisp('{nope')") is None
    assert run("E.parseWisp('{\"status\":\"idle\"}')") == {"status": "idle"}
    assert run("E.parseNord('{\"cli\":true,\"logged_in\":true,\"status\":{\"state\":\"connected\"}}')") == "connected"
    assert run("E.parseNord('junk')") == "unavailable"


def test_quotes_line_respects_a_small_limit():
    q = [{"symbol": s, "price": 10, "changePercent": 1} for s in ("AAA", "BBB", "CCC", "DDD")]
    assert len(run(f"E.quotesLine({json.dumps(q)},2)").split("   ")) == 2
    assert len(run(f"E.quotesLine({json.dumps(q)})").split("   ")) == 3


MODEL = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Model.js"


def model(expr):
    js = f"const M=require({json.dumps(str(MODEL))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


BAR = [
    {"section": "left", "x": 8, "width": 239, "visible": True},
    {"section": "right", "x": 1478, "width": 250, "visible": True},
]


def test_max_ear_width_from_live_room():
    # 1728 wide, camera 186, base ear 96: island x 675..1053; room 428 left, 425 right.
    room = model(f"M.sideRoom({json.dumps(BAR)}, {{x: 675, width: 378}}, 1728)")
    assert room == {"left": 428, "right": 425}
    # base 96 + (min room 425 - margin 12) = 509, capped
    assert model(f"M.maxEarWidth({json.dumps(BAR)}, 1728, 186, 96, 12, 1000)") == 509
    assert model(f"M.maxEarWidth({json.dumps(BAR)}, 1728, 186, 96, 12, 280)") == 280
    # no geometry yet, or no room: keep the base ear
    assert model("M.maxEarWidth([], 1728, 186, 96, 12, 280)") == 168
    crowded = [{"section": "right", "x": 1060, "width": 20, "visible": True}]
    assert model(f"M.maxEarWidth({json.dumps(crowded)}, 1728, 186, 96, 12, 280)") == 96


def test_ear_width_fit():
    assert model("M.earWidthFit(0, 96, 280)") == 96
    assert model("M.earWidthFit(150.2, 96, 280)") == 151
    assert model("M.earWidthFit(900, 96, 280)") == 280
