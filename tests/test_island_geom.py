"""Geom.js: camera width, cutout match, compact pill and card sizes (node-driven)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GEOM = ROOT / "plugins/io.github.duketopceo.island/Geom.js"
CUTOUTS = json.loads(
    (ROOT / "tests/fixtures/island/root/usr/share/omarchy-platform/display-cutouts.json").read_text()
)["panels"]

pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def js(fn: str, *args):
    script = f"""
    const G = require({json.dumps(str(GEOM))});
    const a = JSON.parse(require("fs").readFileSync(0, "utf8"));
    process.stdout.write(JSON.stringify(G[a.fn].apply(null, a.args)));
    """
    out = subprocess.run(
        ["node", "-e", script],
        input=json.dumps({"fn": fn, "args": list(args)}),
        capture_output=True, text=True, timeout=20, check=True,
    ).stdout
    return json.loads(out)


def screen(name="eDP-1", w=1728, h=1117, pw=3456, ph=2234):
    return {"name": name, "width": w, "height": h, "physicalWidth": pw, "physicalHeight": ph}


def probe(model, cutouts=CUTOUTS):
    return {"cutouts": cutouts, "model": model}


def test_mbp16_j316_camera_from_model_table_at_scale_2():
    g = js("compute", probe("j316"), screen(), 0)
    assert g["hasCutout"] is True
    assert g["cameraWidth"] == 186  # 372 physical px / scale 2
    assert g["cutoutTop"] == 64


def test_air_model_uses_322_table():
    s = screen(w=1280, h=832, pw=2560, ph=1664)
    assert js("compute", probe("j613"), s, 0)["cameraWidth"] == 161


def test_unknown_model_panel_width_in_table_uses_table_value():
    s = screen(w=1512, h=982, pw=3024, ph=1964)
    g = js("compute", probe("j999"), s, 0)
    assert g["hasCutout"] is True
    assert g["cameraWidth"] == 186  # panel-width table 3024 -> 372 physical


def test_unknown_model_panel_width_outside_table_is_12_percent():
    cut = [{"connector": "eDP", "width": 3000, "height": 2000, "top": 60}]
    s = screen(w=1500, h=1000, pw=3000, ph=2000)
    g = js("compute", probe("j999", cut), s, 0)
    assert g["hasCutout"] is True
    assert g["cameraWidth"] == 180  # 12% of 3000 = 360 physical, /2


def test_cutout_match_tolerates_4px_and_requires_connector_prefix():
    assert js("compute", probe("j316"), screen(pw=3454, ph=2236), 0)["hasCutout"] is True
    assert js("compute", probe("j316"), screen(pw=3450, ph=2234), 0)["hasCutout"] is False
    s = screen(name="DP-3", w=3456, h=2234, pw=3456, ph=2234)
    assert js("compute", probe("j316"), s, 0)["hasCutout"] is False


def test_no_cutout_gives_virtual_pill_defaults():
    s = screen(name="DP-3", w=3440, h=1440, pw=3440, ph=1440)
    g = js("compute", probe("j316"), s, 0)
    assert g["hasCutout"] is False
    assert g["cameraWidth"] == 160
    assert g["compactWidth"] == 160 + 2 * 56
    assert g["compactHeight"] == 28


def test_pre_notch_model_has_no_cutout():
    assert js("compute", probe("j293"), screen(), 0)["hasCutout"] is False


def test_rotated_output_has_no_cutout():
    assert js("compute", probe("j316"), screen(w=1117, h=1728), 0)["hasCutout"] is False


def test_override_wins_over_table_and_over_virtual():
    assert js("compute", probe("j316"), screen(), 200)["cameraWidth"] == 200
    s = screen(name="DP-3", w=3440, h=1440, pw=3440, ph=1440)
    assert js("compute", probe("j316"), s, 150)["cameraWidth"] == 150


def test_compact_width_ear_cap_floor_and_screen_clamp():
    g = js("compute", probe("j316"), screen(), 0)
    assert g["compactWidth"] == 186 + 2 * 56
    assert g["earWidth"] == 56
    assert js("compactWidth", 80, 1728) == 220
    assert js("compactWidth", 186, 200) == 184  # screen width minus 16 margin


def test_card_size_is_fixed_720x380():
    assert js("cardSize", 1728) == {"width": 720, "height": 380}
    assert js("cardSize", 1280) == {"width": 720, "height": 380}


def test_card_width_clamps_to_screen_width_minus_margin():
    assert js("cardSize", 600) == {"width": 584, "height": 380}
    assert js("cardSize", 736)["width"] == 720
    assert js("cardSize", 735)["width"] == 719
