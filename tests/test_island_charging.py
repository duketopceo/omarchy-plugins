"""Charging.js: sysfs reading parse, brief charging notice, activity text."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plugins/io.github.duketopceo.island/Charging.js"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(M[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({"fn": fn, "args": list(args)}),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def run(readings):
    """Feed (status, capacity, timeToFull, now) tuples through initial/step."""
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const rs = JSON.parse(require("fs").readFileSync(0, "utf8"));
    let m = M.initial();
    let same = [];
    for (const r of rs) {{
      const next = M.step(m, M.parse({{status: r[0], capacity: r[1], timeToFull: r[2]}}), r[3]);
      same.push(next === m);
      m = next;
    }}
    process.stdout.write(JSON.stringify({{model: m, same: same}}));
    """
    out = subprocess.run(
        ["node", "-e", script], input=json.dumps(readings),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def act(model, now):
    return js("activity", model, now)


def test_parse_trims_status_and_reads_numbers():
    assert js("parse", {"status": "Charging\n", "capacity": "62\n", "timeToFull": "4320\n"}) == {
        "status": "Charging", "capacity": 62, "timeToFull": 4320}


def test_parse_garbage_capacity_rejects_the_reading():
    assert js("parse", {"status": "Charging", "capacity": "abc", "timeToFull": "0"}) is None
    assert js("parse", {"status": "Charging", "capacity": "101", "timeToFull": "0"}) is None
    assert js("parse", {"status": "Charging", "capacity": "-1", "timeToFull": "0"}) is None


def test_parse_time_to_full_garbage_or_missing_is_zero():
    assert js("parse", {"status": "Charging", "capacity": "50", "timeToFull": "x"})["timeToFull"] == 0
    assert js("parse", {"status": "Charging", "capacity": "50"})["timeToFull"] == 0
    assert js("parse", {"status": "Charging", "capacity": "50", "timeToFull": "0"})["timeToFull"] == 0


def test_first_reading_charging_is_baseline_and_inactive():
    r = run([["Charging", "62", "4320", 1000]])
    assert act(r["model"], 1000)["active"] is False


def test_discharging_then_charging_is_active_for_six_seconds():
    r = run([["Discharging", "62", "0", 1000], ["Charging", "62", "4320", 5000]])
    assert act(r["model"], 5000)["active"] is True
    assert act(r["model"], 10999)["active"] is True
    assert act(r["model"], 11000)["active"] is False
    assert r["model"]["until"] == 11000


def test_not_charging_then_charging_is_active():
    r = run([["Not charging", "80", "0", 1000], ["Charging", "80", "0", 2000]])
    assert act(r["model"], 2000)["active"] is True


def test_charging_then_charging_makes_no_new_notice():
    r = run([["Discharging", "62", "0", 1000], ["Charging", "62", "4320", 2000],
             ["Charging", "63", "4200", 9000]])
    assert r["model"]["until"] == 8000
    assert act(r["model"], 9000)["active"] is False


def test_unplug_and_replug_notices_again():
    r = run([["Charging", "62", "0", 1000], ["Discharging", "62", "0", 2000],
             ["Charging", "62", "0", 3000]])
    assert act(r["model"], 3000)["active"] is True


def test_null_reading_leaves_the_model_unchanged():
    r = run([["Discharging", "62", "0", 1000], ["Charging", "abc", "0", 2000]])
    assert r["same"] == [False, True]
    assert act(r["model"], 2000)["active"] is False


def test_unchanged_reading_returns_the_same_model():
    # An idle battery is polled every 5 s; an identical reading must not
    # produce a new model (that would redraw every window each poll).
    r = run([["Discharging", "62", "0", 1000], ["Discharging", "62", "0", 6000],
             ["Discharging", "61", "0", 11000]])
    assert r["same"] == [False, True, False]


def test_activity_with_time_to_full_over_an_hour():
    r = run([["Discharging", "62", "0", 1000], ["Charging", "62", "4320", 2000]])
    a = act(r["model"], 2000)
    assert (a["id"], a["priority"], a["text"]) == ("charging", 30, "62%")
    assert a["card"] == "62% · 1h 12m to full"
    assert a["until"] == 8000
    assert a["glyph"] == "\U000f0084"


def test_activity_minutes_only_and_percent_only():
    r = run([["Discharging", "40", "0", 1000], ["Charging", "40", "2700", 2000]])
    assert act(r["model"], 2000)["card"] == "40% · 45m to full"
    r = run([["Discharging", "40", "0", 1000], ["Charging", "40", "0", 2000]])
    assert act(r["model"], 2000)["card"] == "40%"


def test_inactive_shape():
    a = act(js("initial"), 5)
    assert a == {"id": "charging", "active": False, "priority": 30, "text": "", "glyph": "", "card": ""}
