"""Hud.js: effective check, per-kind baseline, brief volume/brightness flash."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plugins/io.github.duketopceo.island/Hud.js"

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


def run(steps):
    """Feed (reading, now) pairs through initial/step; report model and identity."""
    script = f"""
    const M = require({json.dumps(str(MOD))});
    const rs = JSON.parse(require("fs").readFileSync(0, "utf8"));
    let m = M.initial();
    let same = [];
    for (const r of rs) {{
      const next = M.step(m, r[0], r[1]);
      same.push(next === m);
      m = next;
    }}
    process.stdout.write(JSON.stringify({{model: m, same: same}}));
    """
    out = subprocess.run(
        ["node", "-e", script], input=json.dumps(steps),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def vol(value, muted=False):
    return {"kind": "volume", "value": value, "muted": muted}


def bri(value, mx=500):
    return {"kind": "brightness", "value": value, "max": mx}


def act(model, now):
    return js("activity", model, now)


def shell(disabled):
    return {"disabledPlugins": disabled, "plugins": []}


def test_effective_needs_osd_disabled_and_hud_on():
    assert js("effective", {"hud": True}, shell([])) is False
    assert js("effective", {"hud": True}, shell(["other"])) is False
    assert js("effective", {"hud": True}, shell(["omarchy.osd"])) is True
    assert js("effective", {"hud": False}, shell(["omarchy.osd"])) is False


def test_effective_accepts_json_text_and_rejects_malformed():
    assert js("effective", {"hud": True}, json.dumps(shell(["omarchy.osd"]))) is True
    assert js("effective", {"hud": True}, "{not json") is False
    assert js("effective", {"hud": True}, None) is False
    assert js("effective", {"hud": True}, {"disabledPlugins": "omarchy.osd"}) is False


def test_first_volume_reading_is_baseline_second_flashes_for_1600ms():
    r = run([[vol(0.30), 1000], [vol(0.46), 2000]])
    assert r["same"] == [False, False]
    a = act(r["model"], 2000)
    assert (a["id"], a["active"], a["priority"], a["kind"]) == ("hud", True, 80, "volume")
    assert (a["text"], a["card"], a["until"]) == ("46%", "Volume 46%", 3600)
    assert a["level"] == 0.46
    assert act(r["model"], 3599)["active"] is True
    assert act(r["model"], 3600)["active"] is False


def test_baseline_alone_is_inactive():
    r = run([[vol(0.30), 1000]])
    assert act(r["model"], 1000)["active"] is False


def test_mute_toggle_with_same_volume_shows_mute():
    r = run([[vol(0.46), 1000], [vol(0.46, True), 2000]])
    a = act(r["model"], 2000)
    assert (a["active"], a["text"], a["card"], a["level"]) == (True, "Mute", "Muted", 0)
    assert a["glyph"] == "\U000f0581"


def test_brightness_after_baseline_shows_percent():
    r = run([[bri(100), 1000], [bri(125), 2000]])
    a = act(r["model"], 2000)
    assert (a["active"], a["kind"], a["text"], a["card"], a["level"]) == (
        True, "brightness", "25%", "Brightness 25%", 0.25)


def test_kinds_have_independent_baselines():
    r = run([[vol(0.30), 1000], [bri(100), 2000]])
    assert act(r["model"], 2000)["active"] is False


def test_same_value_returns_same_object_and_no_new_flash():
    r = run([[vol(0.30), 1000], [vol(0.46), 2000], [vol(0.46), 3000]])
    assert r["same"] == [False, False, True]
    assert r["model"]["until"] == 3600
    r = run([[bri(100), 1000], [bri(100), 2000]])
    assert r["same"] == [False, True]


def test_volume_above_100_shows_real_value_and_clamps_level():
    r = run([[vol(1.0), 1000], [vol(1.2), 2000]])
    a = act(r["model"], 2000)
    assert (a["text"], a["card"], a["level"]) == ("120%", "Volume 120%", 1)


def test_inactive_shape():
    assert act(js("initial"), 5) == {
        "id": "hud", "active": False, "priority": 80, "text": "", "glyph": "", "card": ""}
