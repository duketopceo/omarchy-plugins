"""Pure Presentation.js helpers: compact sizing, surface, contrast, alert (node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    pre = "".join(
        f"const {n}=require({json.dumps(str(PLUGIN / (n + '.js')))});" for n in ("Geom", "Zone", "Presentation")
    )
    js = f"{pre}console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


MAC = "{cutouts:[{connector:'eDP',width:3456,height:2234,top:64}],model:'j316'}"
MAC_SCREEN = "{name:'eDP-1',width:1728,height:1117,physicalWidth:3456,physicalHeight:2234}"
G = f"Geom.compute({MAC},{MAC_SCREEN},0)"


def js(v):
    return str(v).lower()


def test_constants():
    c = run("[Presentation.EAR_MIN,Presentation.EAR_MAX,Presentation.BUBBLE_GAP,Presentation.DOT_SIZE,"
            "Presentation.DOT_GAP,Presentation.DOT_SLOT,Presentation.ALERT_W,Presentation.ALERT_H]")
    assert c == [56, 120, 6, 8, 4, 26, 360, 76]


@pytest.mark.parametrize("has,mode,want", [
    (True, "compact", "notch"), (True, "split", "notch"),
    (True, "alert", "theme"), (True, "expanded", "theme"),
    (False, "compact", "theme"), (False, "split", "theme"),
])
def test_surface(has, mode, want):
    assert run(f"Presentation.surface({js(has)},'{mode}')") == want


def test_contrast_black_white_and_same():
    assert run("Presentation.contrast({r:0,g:0,b:0},{r:1,g:1,b:1})") == pytest.approx(21)
    assert run("Presentation.contrast({r:.5,g:.5,b:.5},{r:.5,g:.5,b:.5})") == pytest.approx(1)


def test_text_on_black():
    assert run("Presentation.textOnBlack({r:1,g:1,b:1},{r:.1,g:.1,b:.1})") == "text"
    assert run("Presentation.textOnBlack({r:.1,g:.1,b:.1},{r:.9,g:.9,b:.9})") == "background"


def test_compact_idle_matches_geom():
    t = run(f"Presentation.compact({G},40,{{bubble:false,dots:0,screenWidth:1728}})")
    g = run(G)
    assert t["width"] == g["compactWidth"]
    assert t["earWidth"] == g["earWidth"] == 56
    assert t["dotSlot"] == 0 and t["textWidth"] == 56 and t["bubble"] is None
    assert t["height"] == g["compactHeight"]


def test_compact_grows_with_text_and_dots():
    g = run(G)
    t = run(f"Presentation.compact({G},90,{{bubble:false,dots:2,screenWidth:1728}})")
    assert t["dotSlot"] == 26
    assert t["earWidth"] == 116
    assert t["width"] == g["cameraWidth"] + 232
    assert t["textWidth"] == 90


def test_compact_ear_capped_at_max():
    g = run(G)
    t = run(f"Presentation.compact({G},400,{{bubble:false,dots:1,screenWidth:1728}})")
    assert t["earWidth"] == 120
    assert t["width"] == g["cameraWidth"] + 240


def test_compact_clamps_to_screen_and_recomputes_ear():
    g = run(G)
    t = run(f"Presentation.compact({G},120,{{bubble:false,dots:0,screenWidth:300}})")
    assert t["width"] == 300 - 16
    assert t["earWidth"] == (284 - g["cameraWidth"]) // 2


def test_compact_without_screen_width_does_not_clamp():
    t = run(f"Presentation.compact({G},120,{{bubble:false,dots:0}})")
    assert t["earWidth"] == 120


def test_compact_bubble():
    t = run(f"Presentation.compact({G},40,{{bubble:true,dots:0,screenWidth:1728}})")
    assert t["bubble"] == {"offset": t["width"] + 6, "size": 28}


def test_alert_size():
    assert run(f"Presentation.alertSize({G})") == {"width": 360, "height": 76}
    assert run("Presentation.alertSize({card:{width:300,height:380}})") == {"width": 300, "height": 76}


@pytest.mark.parametrize("state,fs,card,want", [
    ("closed", False, False, True), ("open", False, False, False),
    ("closed", True, False, False), ("closed", False, True, False),
])
def test_show_alert(state, fs, card, want):
    s = f"{{state:'{state}',fullscreen:{js(fs)},cardShown:{js(card)}}}"
    assert run(f"Presentation.showAlert({s})") is want


@pytest.mark.parametrize("a,b,c,want", [
    (True, False, False, True), (False, False, False, False),
    (True, True, False, False), (True, False, True, False),
])
def test_bubble_visible(a, b, c, want):
    assert run(f"Presentation.bubbleVisible({js(a)},{js(b)},{js(c)})") is want


def test_zone_pill_with_target_covers_bubble():
    g = run(G)
    t = f"Presentation.compact({G},40,{{bubble:true,dots:0,screenWidth:1728}})"
    r = run(f"Zone.rect('pill',{G},{t})")
    tw = run(t)
    w = run(f"Zone.windowSize({G})")["width"]
    assert r["x"] == max(0, (w - tw["width"]) / 2 - 6)
    assert r["width"] == tw["width"] + 12 + 6 + 28
    assert r["height"] == g["compactHeight"] + 6


def test_zone_pill_target_without_bubble_and_card_ignores_target():
    t = f"Presentation.compact({G},90,{{bubble:false,dots:2,screenWidth:1728}})"
    tw = run(t)
    r = run(f"Zone.rect('pill',{G},{t})")
    assert r["width"] == tw["width"] + 12
    assert run(f"Zone.rect('card',{G},{t})") == run(f"Zone.rect('card',{G})")
