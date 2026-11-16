"""Alert.js: one transient alert at a time, per-window gate, alert builders (node)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Alert.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    const v = typeof M[a.fn] === "function" ? M[a.fn].apply(null, a.args) : M[a.fn];
    process.stdout.write(JSON.stringify(v === undefined ? null : v));
    """
    out = subprocess.run(["node", "-e", script], input=json.dumps({"fn": fn, "args": list(args)}),
                         capture_output=True, text=True, timeout=20, check=True).stdout
    return json.loads(out)


def cp(n: int) -> str:
    return chr(n)


A = {"kind": "timer", "title": "T", "detail": "d", "glyph": "g"}


def test_constants_and_glyphs():
    assert js("ALERT_MS") == 3000
    g = js("GLYPHS")
    assert g["charging"] == cp(0xF0084)
    assert g["timer"] == cp(0xF012C)
    assert g["bluetooth"] == cp(0xF02CB)
    assert g["dnd"] == cp(0xF009B)
    assert g["mic"] == cp(0xF036D)


def test_initial():
    assert js("initial") == {"current": None, "seq": 0}


def test_push_sets_current_with_window_and_null_level():
    m = js("push", js("initial"), A, 1000)
    assert m["seq"] == 1
    assert m["current"] == {"id": 1, "kind": "timer", "title": "T", "detail": "d",
                            "glyph": "g", "level": None, "at": 1000, "until": 4000}


def test_push_keeps_numeric_level_and_latest_wins():
    m = js("push", js("initial"), dict(A, level=0.62), 0)
    assert m["current"]["level"] == 0.62
    m2 = js("push", m, dict(A, title="B"), 500)
    assert m2["seq"] == 2 and m2["current"]["id"] == 2 and m2["current"]["title"] == "B"
    assert m2["current"]["until"] == 3500


def test_current_expires():
    m = js("push", js("initial"), A, 1000)
    assert js("current", m, 3999)["id"] == 1
    assert js("current", m, 4000) is None
    assert js("current", js("initial"), 0) is None


def test_gate_rules():
    m = js("push", js("initial"), A, 0)
    assert js("gate", js("initial"), 0, False, 0) == {"show": False, "blockedId": 0}
    assert js("gate", m, 0, False, 100) == {"show": True, "blockedId": 0}
    assert js("gate", m, 0, True, 100) == {"show": False, "blockedId": 1}
    assert js("gate", m, 1, False, 100) == {"show": False, "blockedId": 1}
    assert js("gate", m, 0, True, 5000) == {"show": False, "blockedId": 0}


def test_builders():
    assert js("charging", 62, 0)["detail"] == "62%"
    c = js("charging", 62, 4320)
    assert c["title"] == "Charging" and c["detail"] == "62% · 1h 12m to full"
    assert c["level"] == 0.62 and c["kind"] == "charging" and c["glyph"] == cp(0xF0084)
    assert js("timerDone")["title"] == "Timer done"
    assert js("timerDone")["detail"] == "Your Island timer finished"
    b = js("bluetooth", "Buds", None)
    assert b["title"] == "Buds" and b["detail"] == "Connected" and b["kind"] == "bluetooth"
    assert js("bluetooth", "Buds", 0.8)["detail"] == "Connected · 80%"
    assert js("dnd", True)["detail"] == "On" and js("dnd", False)["detail"] == "Off"
    assert js("dnd", True)["title"] == "Do Not Disturb"
    assert js("mic", True)["detail"] == "Muted" and js("mic", False)["detail"] == "On"
    assert js("mic", True)["title"] == "Microphone"
