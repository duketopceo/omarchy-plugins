"""Model detection and size scaling for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODEL = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Model.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

CUTOUTS = json.dumps({"panels": [
    {"connector": "eDP", "width": 3024, "height": 1964, "top": 64},
    {"connector": "eDP", "width": 3456, "height": 2234, "top": 64},
    {"connector": "eDP", "width": 2560, "height": 1664, "top": 56},
    {"connector": "eDP", "width": 2880, "height": 1864, "top": 56},
]})

# model, physical width, height, cutout px, camera px
PANELS = [
    ("apple,j314c", 3024, 1964, 64, 372),
    ("apple,j316c", 3456, 2234, 64, 372),
    ("apple,j413", 2560, 1664, 56, 322),
    ("apple,j415", 2880, 1864, 56, 322),
    ("apple,j616s", 3456, 2234, 64, 372),
    ("apple,j713", 2560, 1664, 56, 322),
]


def run(expr):
    js = f"const M=require({json.dumps(str(MODEL))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


@pytest.mark.parametrize("model,w,h,top,cam", PANELS)
@pytest.mark.parametrize("scale", [1, 1.5, 2])
def test_cutout_height_and_camera_width_per_scale(model, w, h, top, cam, scale):
    logical = round(w / scale)
    c = f"M.parseCutouts({json.dumps(CUTOUTS)})"
    mode = f"{{width:{w},height:{h},transform:0}}"
    cut = run(f"M.cutoutTop({c},'eDP-1',{logical},{mode})")
    assert cut == -(-top * logical // w)
    assert cut > 0
    camera = run(f"M.cameraWidthFor({json.dumps(model)},{w},{logical})")
    assert camera == round(cam * logical / w)
    island = run(f"M.islandRect({logical},{cut},null,{camera})")
    assert island["notched"] is True
    assert island["width"] == camera + 2 * run(f"M.earWidthFor({logical})")


def test_pre_notch_models_are_virtual():
    for model in ("apple,j313", "apple,j293", "apple,j493"):
        assert run(f"M.isPreNotch({json.dumps(model)})") is True
        # Even on a panel size that matches a cutout entry: no camera gap.
        assert run(f"M.cameraWidthFor({json.dumps(model)},2560,1280)") == 0
    c = f"M.parseCutouts({json.dumps(CUTOUTS)})"
    # M1 Air panel is 2560x1600: no cutout entry, so cutoutTop is 0 and the island is virtual.
    cut = run(f"M.cutoutTop({c},'eDP-1',1280,{{width:2560,height:1600,transform:0}})")
    assert cut == 0
    island = run(f"M.islandRect(1280,{cut},null,0)")
    assert island["notched"] is False and island["width"] == 300


def test_unknown_model_falls_back_to_panel_ratio_or_zero():
    # Unknown model on a known panel: ratio fallback.
    assert run("M.cameraWidthFor('vendor,thing',3456,1728)") == 186
    assert run("M.cameraWidthFor('',3024,1512)") == 186
    # Unknown model on an unknown panel, or bad input: 0 (caller uses SIZES default).
    assert run("M.cameraWidthFor('vendor,thing',3840,1920)") == 0
    assert run("M.cameraWidthFor('apple,j316c',0,0)") == 0
    assert run("M.cameraWidthFor(null,undefined,undefined)") == 0


def test_override_wins():
    assert run("M.cameraWidthFor('apple,j316c',3456,1728,150)") == 150
    assert run("M.cameraWidthFor('apple,j313',2560,1280,150)") == 150


def test_nul_separated_compatible_parse():
    nul = "apple,j316c\\u0000apple,t6001\\u0000apple,arm-platform\\u0000"
    assert run(f"M.parseCompatible('{nul}')") == ["apple,j316c", "apple,t6001", "apple,arm-platform"]
    assert run(f"M.deviceModel('{nul}')") == "j316"
    assert run("M.deviceModel('apple,j413')") == "j413"
    assert run("M.deviceModel('')") == ""
    assert run("M.deviceModel('dell,precision\\u0000intel,x')") == ""
    assert run("M.deviceModel(['apple,j415'])") == "j415"


def test_ear_width_scales_with_screen():
    assert run("M.earWidthFor(1728)") == 96
    assert run("M.earWidthFor(3456)") == 96
    ear13 = run("M.earWidthFor(1280)")
    assert 64 <= ear13 < 96
    assert run("M.earWidthFor(100)") == 64
    assert run("M.earWidthFor(0)") == 96
    # Island stays a sensible share of a 13" screen.
    island = run("M.islandRect(1280,28,null,161)")
    assert island["width"] <= 1280 * 0.26


def test_island_defaults_unchanged_on_16():
    island = run("M.islandRect(1728,32)")
    assert island["width"] == 392
