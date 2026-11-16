"""Glyphs.js: which control a card row shows per activity, and its label (node)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Glyphs.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const G = require({json.dumps(str(MOD))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(G[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(["node", "-e", script], input=json.dumps({"fn": fn, "args": list(args)}),
                         capture_output=True, text=True, timeout=20, check=True).stdout
    return json.loads(out)


@pytest.mark.parametrize("activity,control", [
    ({"id": "dictation", "active": True, "state": "recording"}, "stop"),
    ({"id": "dictation", "active": True, "state": "transcribing"}, ""),
    ({"id": "media", "active": True, "canTogglePlaying": True}, "toggle"),
    ({"id": "media", "active": True, "canTogglePlaying": False}, ""),
    ({"id": "timer", "active": True, "state": "running"}, "pause"),
    ({"id": "timer", "active": True, "state": "paused"}, "resume"),
    ({"id": "timer", "active": True, "state": "done"}, ""),
    ({"id": "charging", "active": True}, ""),
    ({"id": "hud", "active": True}, ""),
    ({"id": "media", "active": False, "canTogglePlaying": True}, ""),
    ({"id": "calendar", "active": True, "url": "https://meet.google.com/abc-defg-hij"}, "join"),
    ({"id": "calendar", "active": True, "url": ""}, ""),
    ({"id": "calendar", "active": False, "url": "https://meet.google.com/abc-defg-hij"}, ""),
    (None, ""),
])
def test_primary_control(activity, control):
    assert js("primaryControl", activity) == control


def test_join_label():
    assert js("controlLabel", "join", {"id": "calendar"}) == "Join"


def test_screenrec_gets_a_stop_control():
    assert js("primaryControl", {"id": "screenrec", "active": True, "state": "recording"}) == "stop"
    assert js("primaryControl", {"id": "screenrec", "active": False, "state": "recording"}) == ""


def test_media_toggle_label_shows_what_a_press_does():
    playing = js("controlLabel", "toggle", {"playing": True})
    paused = js("controlLabel", "toggle", {"playing": False})
    assert playing == "\U000F03E4"  # pause
    assert paused == "\U000F040A"   # play


def test_add_label_and_unknown_action():
    assert js("controlLabel", "add", None) == "+1 min"
    assert js("controlLabel", "nope", None) == ""
