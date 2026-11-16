"""Dnd.js: notification-silencing state parse, availability, edge detection (node)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Dnd.js"
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


def test_parse():
    assert js("parse", '{"dnd": true}') is True
    assert js("parse", '{"dnd": false}') is False
    assert js("parse", '{"dnd": "true"}') is False
    assert js("parse", "") is False
    assert js("parse", "garbage{") is False
    assert js("parse", "[1]") is False
    assert js("parse", "null") is False


def test_available():
    assert js("available", '{"disabledPlugins": ["omarchy.notifications"]}') is False
    assert js("available", '{"disabledPlugins": ["other"]}') is True
    assert js("available", "{}") is True
    assert js("available", "") is True
    assert js("available", "garbage") is True
    assert js("available", '{"disabledPlugins": "omarchy.notifications"}') is True


def test_glyph():
    assert js("GLYPH") == chr(0xF009B)


def test_step_edges():
    m = js("initial")
    assert m == {"seen": False, "on": False}
    first = js("step", m, True)
    assert first["edge"] == "" and first["model"] == {"seen": True, "on": True}
    same = js("step", first["model"], True)
    assert same["edge"] == "" and same["model"] == first["model"]
    off = js("step", first["model"], False)
    assert off["edge"] == "off" and off["model"] == {"seen": True, "on": False}
    assert js("step", off["model"], True)["edge"] == "on"
    quiet = js("step", m, False)
    assert quiet["edge"] == "" and quiet["model"] == {"seen": True, "on": False}
