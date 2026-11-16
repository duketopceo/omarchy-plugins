"""Bluetooth.js: audio filter, connect edges, card-only activity."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plugins/io.github.duketopceo.island/Bluetooth.js"

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


def dev(addr, name="Buds", icon="audio-headphones", connected=True, batt=True, battery=0.8):
    return {"address": addr, "name": name, "icon": icon, "connected": connected,
            "batteryAvailable": batt, "battery": battery}


def test_audio_filters_connected_audio_icons():
    devs = [dev("A"), dev("B", connected=False), dev("C", icon="input-keyboard"),
            dev("D", icon="audio-card"), dev("E", icon=None)]
    assert [d["address"] for d in js("audio", devs)] == ["A", "D"]
    assert js("audio", None) == []


def test_initial():
    assert js("initial") == {"seen": False, "addrs": {}}


def test_first_step_is_baseline_then_edges_for_new_connections():
    r = js("step", js("initial"), [dev("A")])
    assert r["edges"] == []
    assert r["model"]["seen"] is True
    r2 = js("step", r["model"], [dev("A"), dev("B", name="Pods", battery=0.5)])
    assert r2["edges"] == [{"address": "B", "name": "Pods", "battery": 0.5}]
    r3 = js("step", r2["model"], [dev("A"), dev("B")])
    assert r3["edges"] == []
    r4 = js("step", r3["model"], [dev("A")])
    assert r4["edges"] == []
    r5 = js("step", r4["model"], [dev("A"), dev("B")])
    assert [e["address"] for e in r5["edges"]] == ["B"]


def test_edge_battery_null_when_unavailable():
    m = js("step", js("initial"), [])["model"]
    r = js("step", m, [dev("A", batt=False, battery=0)])
    assert r["edges"] == [{"address": "A", "name": "Buds", "battery": None}]


def test_unchanged_set_returns_same_model():
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const d = [{{address:"A",name:"x",icon:"audio-card",connected:true,batteryAvailable:false,battery:0}}];
    const r1 = M.step(M.initial(), d);
    const r2 = M.step(r1.model, d);
    process.stdout.write(JSON.stringify(r1.model === r2.model));
    """
    out = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=20, check=True).stdout
    assert out == "true"


def test_activity_inactive_when_empty():
    assert js("activity", []) == {"id": "bluetooth", "active": False, "priority": 20,
                                  "cardOnly": True, "text": "", "glyph": "", "card": ""}


def test_activity_with_battery_and_without():
    a = js("activity", [dev("A", name="AirPods", battery=0.8)])
    assert a["active"] is True and a["cardOnly"] is True and a["priority"] == 20
    assert a["text"] == "80%"
    assert a["card"] == "AirPods 80%"
    assert a["glyph"] == "\U000F02CB"
    b = js("activity", [dev("A", name="Speaker", batt=False)])
    assert b["text"] == "Speaker" and b["card"] == "Speaker"
