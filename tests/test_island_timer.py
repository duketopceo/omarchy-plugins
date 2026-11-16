"""Timer.js: parse, state transitions, remaining/activity text, tick scheduling."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TIMER = ROOT / "plugins/io.github.duketopceo.island/Timer.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

T0 = 1_000_000


def js(fn: str, *args):
    script = f"""
    const T = require({json.dumps(str(TIMER))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(T[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({"fn": fn, "args": list(args)}),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def running(ms=300_000, now=T0):
    return js("start", js("initial"), ms, now)


def test_initial_is_idle():
    m = js("initial")
    assert m["state"] == "idle"


@pytest.mark.parametrize(
    "spec,ms",
    [
        ("90s", 90_000),
        ("5m", 300_000),
        ("1h30m", 5_400_000),
        ("1h", 3_600_000),
        ("2m30s", 150_000),
        ("10", 600_000),
        (" 5M ", 300_000),
        ("24h", 86_400_000),
    ],
)
def test_parse_accepts(spec, ms):
    assert js("parse", spec) == ms


@pytest.mark.parametrize("spec", ["0", "abc", "-5m", "25h", "", "0s", "5x", "m5", "24h1s"])
def test_parse_rejects(spec):
    assert js("parse", spec) == 0


def test_start_sets_running_with_end_time():
    m = running(120_000)
    assert m["state"] == "running"
    assert m["endsAt"] == T0 + 120_000
    assert m["totalMs"] == 120_000


def test_ae3_add_pause_wait_resume():
    m = running(120_000)
    m = js("add", m, 60_000, T0)
    assert js("remaining", m, T0) == 180_000
    # pause with 1:30 left (90 s into a 3 min timer)
    m = js("pause", m, T0 + 90_000)
    assert m["state"] == "paused"
    assert js("remaining", m, T0 + 90_000) == 90_000
    # ten seconds pass while paused: still 1:30
    assert js("remaining", m, T0 + 100_000) == 90_000
    m = js("resume", m, T0 + 100_000)
    assert m["state"] == "running"
    assert js("remaining", m, T0 + 100_000) == 90_000
    assert js("remaining", m, T0 + 110_000) == 80_000


def test_add_while_paused_keeps_it_paused():
    m = js("pause", running(120_000), T0 + 30_000)
    m = js("add", m, 60_000, T0 + 40_000)
    assert m["state"] == "paused"
    assert js("remaining", m, T0 + 50_000) == 150_000


def test_tick_at_end_goes_done_then_idle_after_flash():
    m = running(60_000)
    assert js("tick", m, T0 + 59_999) == m
    d = js("tick", m, T0 + 60_000)
    assert d["state"] == "done"
    assert d["doneUntil"] == T0 + 60_000 + 8000
    assert js("tick", d, T0 + 67_999) == d
    assert js("tick", d, T0 + 68_000)["state"] == "idle"


def test_cancel_from_running_or_paused_goes_idle():
    assert js("cancel", running())["state"] == "idle"
    assert js("cancel", js("pause", running(), T0 + 1000))["state"] == "idle"


def test_invalid_transitions_return_same_object():
    script = f"""
    const T = require({json.dumps(str(TIMER))});
    const idle = T.initial();
    const run = T.start(idle, 60000, 0);
    const pau = T.pause(run, 1000);
    const done = T.tick(run, 60000);
    const same = [
      T.cancel(idle) === idle,
      T.pause(idle, 0) === idle,
      T.resume(run, 0) === run,
      T.pause(pau, 0) === pau,
      T.add(idle, 60000, 0) === idle,
      T.add(done, 60000, 60000) === done,
      T.start(run, 5000, 0) === run,
      T.tick(idle, 0) === idle,
      T.tick(pau, 999999) === pau,
    ];
    process.stdout.write(JSON.stringify(same));
    """
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=20, check=True).stdout
    assert json.loads(out) == [True] * 9


def test_remaining_is_never_negative():
    assert js("remaining", running(1000), T0 + 5000) == 0
    assert js("remaining", js("initial"), T0) == 0


def test_fmt():
    assert js("fmt", 299_000) == "4:59"
    assert js("fmt", 298_001) == "4:59"
    assert js("fmt", 3_725_000) == "1:02:05"
    assert js("fmt", 0) == "0:00"
    assert js("fmt", 59_001) == "1:00"


def test_activity_running_text_and_card():
    a = js("activity", running(300_000), T0 + 1000)
    assert a["id"] == "timer"
    assert a["priority"] == 70
    assert a["active"] is True
    assert a["text"] == "4:59"
    assert a["card"] == "Timer 4:59"
    assert a["glyph"] == "\U000F13AB"
    assert a["paused"] is False
    assert a["state"] == "running"
    assert "until" not in a


def test_activity_over_an_hour_uses_hours():
    a = js("activity", running(3_725_000), T0)
    assert a["text"] == "1:02:05"


def test_activity_paused_shows_frozen_time():
    m = js("pause", running(300_000), T0 + 1000)
    a = js("activity", m, T0 + 60_000)
    assert a["text"] == "4:59"
    assert a["card"] == "Paused 4:59"
    assert a["glyph"] == "\U000F1ADE"
    assert a["paused"] is True
    assert a["state"] == "paused"


def test_activity_done_flash():
    d = js("tick", running(60_000), T0 + 60_000)
    a = js("activity", d, T0 + 61_000)
    assert a["active"] is True
    assert a["text"] == "Done"
    assert a["card"] == "Timer done"
    assert a["glyph"] == "\U000F012C"
    assert a["until"] == T0 + 68_000
    assert a["state"] == "done"


def test_activity_idle_is_inactive():
    a = js("activity", js("initial"), T0)
    assert a == {
        "id": "timer", "active": False, "priority": 70, "text": "", "glyph": "",
        "card": "", "paused": False, "state": "idle",
    }


def test_next_tick_ms():
    m = running(300_000)
    # 300 s left: the display changes after exactly 1 s... at the boundary 300.000 -> 299.xxx
    assert js("nextTickMs", m, T0) == 1000
    assert js("nextTickMs", m, T0 + 250) == 750
    assert js("nextTickMs", m, T0 + 1000) == 1000
    # last second: next change is the end itself
    assert js("nextTickMs", m, T0 + 299_400) == 600
    d = js("tick", m, T0 + 300_000)
    assert js("nextTickMs", d, T0 + 300_000) == 8000
    assert js("nextTickMs", d, T0 + 303_000) == 5000
    assert js("nextTickMs", js("initial"), T0) == 0
    assert js("nextTickMs", js("pause", m, T0 + 10), T0 + 20) == 0
