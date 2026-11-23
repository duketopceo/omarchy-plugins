"""Omacontrol.js: the fixed page list, the IPC argv and availability (node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
MOD = ROOT / "Omacontrol.js"
GLYPHS = ROOT / "Glyphs.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")

PAGES = ["overview", "network", "bluetooth", "audio", "displays", "power", "idle", "keyboard",
         "bindings", "pointer", "theme", "wallpaper", "bar", "workspaces", "windows", "security",
         "disk", "processes", "datetime", "about", "plugins", "packages"]
BASE = ["qs", "-p", "/usr/share/omarchy/shell", "ipc", "call", "omacontrol"]


def js(expr: str):
    script = (f"const O=require({json.dumps(str(MOD))});const G=require({json.dumps(str(GLYPHS))});"
              f"console.log(JSON.stringify({expr}));")
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


def test_page_list_is_the_verified_set():
    assert [p["id"] for p in js("O.PAGES")] == PAGES


@pytest.mark.parametrize("page", PAGES)
def test_command_is_a_fixed_argv(page):
    assert js(f"O.command({json.dumps(page)})") == BASE + ["showPage", page]


def test_open_and_empty_open_without_a_page():
    assert js('O.command("open")') == BASE + ["open"]
    assert js('O.command("")') == BASE + ["open"]
    assert js("O.command()") == BASE + ["open"]


@pytest.mark.parametrize("bad", ["Network", "net work", "network;reboot", "../x", "-h", "$(id)", "hide", "toggle", "show", "nope"])
def test_unknown_ids_are_refused(bad):
    assert js(f"O.command({json.dumps(bad)})") is None


def test_shortcuts_are_listed_pages_with_hints():
    sc = js("O.SHORTCUTS")
    assert [s["id"] for s in sc] == ["network", "bluetooth", "audio", "displays", "power", "keyboard", "theme", "overview"]
    assert all(s["id"] in PAGES for s in sc)
    assert js('O.hint("bluetooth")') == "Open Bluetooth settings"
    assert js('O.hint("overview")') == "Open all settings"
    assert js('O.hint("nope")') == ""


def test_shortcut_glyphs_are_defined():
    # An unknown glyph name falls back to the open-in-new glyph; none may.
    fallback = js('G.glyph("nope")')
    assert all(js(f"G.glyph({json.dumps(s['glyph'])})") != fallback or s["glyph"] == "open"
               for s in js("O.SHORTCUTS"))


def test_available_needs_manifest_and_not_disabled():
    pid = "io.github.twiking.omacontrol"
    off = json.dumps(json.dumps({"disabledPlugins": [pid]}))
    on = json.dumps(json.dumps({"disabledPlugins": ["other"]}))
    assert js(f"O.available({on}, true)") is True
    assert js(f"O.available({on}, false)") is False
    assert js(f"O.available({off}, true)") is False
    assert js('O.available("", true)') is True
    assert js('O.available("not json", true)') is True
    assert js('O.available("{}", true)') is True
