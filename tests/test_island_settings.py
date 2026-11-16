"""Settings.js: resolve / merge / changed for the Island's own shell.json entry."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "plugins/io.github.duketopceo.island/Settings.js"
FIX = ROOT / "tests/fixtures/island"
ID = "io.github.duketopceo.island"

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const S = require({json.dumps(str(SETTINGS))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(S[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({"fn": fn, "args": list(args)}),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


BOOLS = {"dictation": True, "media": True, "charging": True, "hud": True}
DEFAULTS = {"openDelay": 140, "closeDelay": 450, "cameraWidth": 0, **BOOLS}


def test_no_entry_gives_defaults():
    shell = json.loads((FIX / "shell-noentry.json").read_text())
    r = js("resolve", shell, ID)
    assert r == {"entryExists": False, "settings": DEFAULTS}


def test_partial_entry_defaults_missing_keys():
    shell = json.loads((FIX / "shell-valid.json").read_text())
    r = js("resolve", shell, ID)
    assert r["entryExists"] is True
    assert r["settings"] == {**DEFAULTS, "openDelay": 200}


def test_out_of_range_values_are_clamped():
    def entry(**kw):
        return {"plugins": [{"id": ID, **kw}]}

    assert js("resolve", entry(openDelay=-5, closeDelay=10), ID)["settings"]["openDelay"] == 0
    assert js("resolve", entry(openDelay=-5, closeDelay=10), ID)["settings"]["closeDelay"] == 150
    hi = js("resolve", entry(openDelay=9999, closeDelay=9999), ID)["settings"]
    assert (hi["openDelay"], hi["closeDelay"]) == (600, 1500)
    assert js("resolve", entry(cameraWidth=-3), ID)["settings"]["cameraWidth"] == 0
    assert js("resolve", entry(openDelay="abc"), ID)["settings"]["openDelay"] == 140


def test_malformed_shell_json_gives_defaults_without_exception():
    text = (FIX / "shell-malformed.json").read_text()
    assert js("resolve", text, ID) == {"entryExists": False, "settings": DEFAULTS}
    for junk in (None, 5, [], "null", {"plugins": "nope"}, {"plugins": [None, 3]}):
        assert js("resolve", junk, ID) == {"entryExists": False, "settings": DEFAULTS}


def test_resolve_accepts_json_text():
    text = (FIX / "shell-valid.json").read_text()
    assert js("resolve", text, ID)["settings"]["openDelay"] == 200


def test_merge_keeps_every_other_key_and_the_id():
    current = {"id": ID, "openDelay": 200, "closeDelay": 500, "cameraWidth": 190, "extra": "keep"}
    merged = js("merge", current, {"closeDelay": 700}, ID)
    assert merged == {"id": ID, "openDelay": 200, "closeDelay": 700, "cameraWidth": 190, "extra": "keep", **BOOLS}


def test_merge_onto_nothing_fills_defaults_and_id_and_clamps_edit():
    merged = js("merge", None, {"openDelay": 9999}, ID)
    assert merged == {"id": ID, "openDelay": 600, "closeDelay": 450, "cameraWidth": 0, **BOOLS}


def test_changed_detects_difference_only():
    cur = {"id": ID, "openDelay": 140, "closeDelay": 450, "cameraWidth": 0, **BOOLS}
    same = js("merge", cur, {"openDelay": 140}, ID)
    assert js("changed", cur, same) is False
    assert js("changed", cur, js("merge", cur, {"openDelay": 141}, ID)) is True
    assert js("changed", None, same) is True


def test_four_toggles_default_true_with_no_entry():
    shell = json.loads((FIX / "shell-noentry.json").read_text())
    s = js("resolve", shell, ID)["settings"]
    assert {k: s[k] for k in BOOLS} == {"dictation": True, "media": True, "charging": True, "hud": True}


def test_stored_booleans_are_kept_and_non_booleans_fall_back_to_true():
    shell = {"plugins": [{"id": ID, "hud": False, "media": "no", "charging": 0, "dictation": None}]}
    s = js("resolve", shell, ID)["settings"]
    assert (s["hud"], s["media"], s["charging"], s["dictation"]) == (False, True, True, True)


def test_merge_hud_false_keeps_delays_and_id():
    current = {"id": ID, "openDelay": 200, "closeDelay": 500, "cameraWidth": 190}
    merged = js("merge", current, {"hud": False}, ID)
    assert merged == {"id": ID, "openDelay": 200, "closeDelay": 500, "cameraWidth": 190,
                      **BOOLS, "hud": False}
