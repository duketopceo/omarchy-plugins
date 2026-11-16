"""Controls.js: hover, pressed and disabled looks and the hint position (node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

DIR = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def js(mod: str, expr: str):
    script = f"const M=require({json.dumps(str(DIR / mod))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


def look(**s):
    return js("Controls.js", f"M.look({json.dumps(s)})")


def test_idle_has_no_fill_and_full_scale():
    v = look(enabled=True, hovered=False, pressed=False, selected=False)
    assert v == {"fill": "none", "scale": 1, "opacity": 1, "pointer": True, "hint": False}


def test_hover_fills_and_asks_for_the_hint():
    v = look(enabled=True, hovered=True, pressed=False, selected=False)
    assert v["fill"] == "hover" and v["hint"] is True and v["scale"] == 1


def test_pressed_darkens_scales_and_hides_the_hint():
    v = look(enabled=True, hovered=True, pressed=True, selected=False)
    assert v["fill"] == "pressed" and v["scale"] == 0.96 and v["hint"] is False


def test_selected_keeps_its_fill_on_hover():
    assert look(enabled=True, hovered=True, pressed=False, selected=True)["fill"] == "selected"
    assert look(enabled=True, hovered=False, pressed=False, selected=True)["fill"] == "selected"


def test_disabled_is_dim_with_no_hover_press_pointer_or_hint():
    v = look(enabled=False, hovered=True, pressed=True, selected=False)
    assert v == {"fill": "none", "scale": 1, "opacity": 0.35, "pointer": False, "hint": False}


def test_look_tolerates_missing_input():
    assert js("Controls.js", "M.look(null)")["pointer"] is False


A = {"x": 100, "y": 200, "w": 40, "h": 24}
HINT = {"w": 80, "h": 20}
CARD = {"w": 640, "h": 300}


def pos(a, hint=HINT, card=CARD, gap=4):
    return js("Controls.js", f"M.hintPos({json.dumps(a)},{json.dumps(hint)},{json.dumps(card)},{gap})")


def test_hint_sits_centered_above_the_control():
    assert pos(A) == {"x": 80, "y": 176}


def test_hint_goes_below_when_there_is_no_room_above():
    assert pos({**A, "y": 6}) == {"x": 80, "y": 34}


def test_hint_is_clamped_inside_the_card_on_both_sides():
    assert pos({**A, "x": 0})["x"] == 4
    assert pos({**A, "x": 620})["x"] == 640 - 80 - 4


def test_hint_never_leaves_the_card_vertically():
    p = pos({**A, "y": 290})
    assert 4 <= p["y"] <= 300 - 20 - 4


def test_control_hints_say_what_a_press_does():
    g = lambda action, a: js("Glyphs.js", f"M.controlHint({json.dumps(action)},{json.dumps(a)})")
    assert g("toggle", {"playing": True}) == "Pause"
    assert g("toggle", {"playing": False}) == "Play"
    assert g("pause", None) == "Pause timer"
    assert g("join", None) == "Join meeting"
    assert g("stop", {"id": "screenrec"}) == "Stop recording"
    assert g("nope", None) == ""
