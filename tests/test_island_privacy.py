"""Privacy.js: mic-in-use detection from PipeWire records, dot colour, camera line."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "plugins/io.github.duketopceo.island/Privacy.js"

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


def rec(props, stream=True, sink=False):
    return {"isStream": stream, "isSink": sink, "props": props}


EFFECT = rec({"media.class": "Stream/Input/Audio", "node.name": "audio_effect.j316-mic", "node.passive": True})
VIRTUAL = rec({"media.class": "Stream/Input/Audio", "node.name": "input.omarchy_asahi_mic",
               "node.passive": True, "node.virtual": True})
PEAK = rec({"application.name": "Quickshell Peak Detect", "media.category": "Monitor",
            "media.class": "Stream/Input/Audio", "stream.monitor": True, "stream.capture.sink": False})
PWREC = rec({"application.name": "pw-record", "media.class": "Stream/Input/Audio"})


def test_host_records_not_counted():
    assert js("micInUse", [EFFECT, VIRTUAL, PEAK]) is False


def test_real_capture_counted():
    assert js("micInUse", [EFFECT, PWREC]) is True


def test_string_booleans_and_other_exclusions():
    assert js("micInUse", [rec({"media.class": "Stream/Input/Audio", "node.passive": "true"})]) is False
    assert js("micInUse", [rec({"media.class": "Stream/Input/Audio", "stream.monitor": "true"})]) is False
    assert js("micInUse", [rec({"media.class": "Stream/Input/Audio", "stream.capture.sink": "true"})]) is False
    assert js("micInUse", [rec({"media.class": "Stream/Output/Audio"})]) is False
    assert js("micInUse", [rec({"media.class": "Stream/Input/Audio"}, stream=False)]) is False
    assert js("micInUse", [rec({"media.class": "Stream/Input/Audio"}, sink=True)]) is False
    assert js("micInUse", [rec({"media.class": "Stream/Input/Audio", "node.passive": "false"})]) is True


def test_empty_and_bad_input():
    assert js("micInUse", []) is False
    assert js("micInUse", None) is False


def test_dot_color():
    mic = js("dotColor", "mic", {"h": 0.6, "s": 0.2, "l": 0.9})
    assert mic["h"] == pytest.approx(30 / 360)
    assert mic["s"] == pytest.approx(0.55)
    assert mic["l"] == pytest.approx(0.65)
    cam = js("dotColor", "camera", {"h": -1, "s": 0.8, "l": 0.1})
    assert cam["h"] == pytest.approx(130 / 360)
    assert cam["s"] == pytest.approx(0.8)
    assert cam["l"] == pytest.approx(0.45)
    mid = js("dotColor", "mic", {"h": 0.1, "s": 0.7, "l": 0.5})
    assert mid["l"] == pytest.approx(0.5)


def test_parse_camera():
    assert js("parseCamera", '{"inUse": true, "apps": ["firefox"]}') == {"inUse": True, "apps": ["firefox"]}
    assert js("parseCamera", '{"inUse": false, "apps": []}') == {"inUse": False, "apps": []}
    for bad in ("", "garbage", "{", "null", "[1]", None):
        assert js("parseCamera", bad) == {"inUse": False, "apps": []}
