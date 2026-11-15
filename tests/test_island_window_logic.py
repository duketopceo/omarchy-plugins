"""Pure helpers behind the Island's window, IPC and fullscreen wiring (node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    pre = "".join(
        f"const {n}=require({json.dumps(str(PLUGIN / (n + '.js')))});"
        for n in ("Hover", "Geom", "Zone", "Screens", "Fullscreen", "Entry")
    )
    js = f"{pre}console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


MAC = "{cutouts:[{connector:'eDP',width:3456,height:2234,top:64}],model:'j316'}"
MAC_SCREEN = "{name:'eDP-1',width:1728,height:1117,physicalWidth:3456,physicalHeight:2234}"
UW_SCREEN = "{name:'DP-3',width:3440,height:1440,physicalWidth:3440,physicalHeight:1440}"


# ---- Zone: mask rectangle per Hover.js state (KTD2) ----

def geom(screen):
    return f"Geom.compute({MAC},{screen},0)"


def test_window_size_is_card_plus_slop_and_independent_of_probe():
    a = run(f"Zone.windowSize({geom(MAC_SCREEN)})")
    b = run(f"Zone.windowSize(Geom.compute({{}},{MAC_SCREEN},0))")
    assert a == b == {"width": 720 + 24, "height": 380 + 12}


def test_pill_zone_is_pill_plus_6px_centered():
    g = run(geom(MAC_SCREEN))
    w = run(f"Zone.windowSize({geom(MAC_SCREEN)})")
    r = run(f"Zone.rect('pill',{geom(MAC_SCREEN)})")
    assert r["width"] == g["compactWidth"] + 12
    assert r["height"] == g["compactHeight"] + 6
    assert r["y"] == 0
    assert r["x"] + r["width"] / 2 == w["width"] / 2


def test_card_zone_is_card_plus_12px_and_fills_window():
    w = run(f"Zone.windowSize({geom(UW_SCREEN)})")
    r = run(f"Zone.rect('card',{geom(UW_SCREEN)})")
    assert r == {"x": 0, "y": 0, "width": w["width"], "height": w["height"]}


@pytest.mark.parametrize(
    "state,zone",
    [("closed", "pill"), ("arming", "pill"), ("open", "card"), ("leaving", "card")],
)
def test_every_hover_state_maps_to_its_zone_rect(state, zone):
    m = json.dumps({"state": state})
    got = run(f"Zone.rect(Hover.zoneFor({m}),{geom(MAC_SCREEN)})")
    assert got == run(f"Zone.rect('{zone}',{geom(MAC_SCREEN)})")


def test_flags_never_change_the_zone():
    for flag in ("pinned", "focused", "held", "summoned", "rearmLock", "fullscreen"):
        m = json.dumps({"state": "open", flag: True})
        assert run(f"Hover.zoneFor({m})") == "card"


def test_narrow_screen_zone_stays_inside_window():
    s = "{name:'DP-9',width:400,height:800,physicalWidth:400,physicalHeight:800}"
    w = run(f"Zone.windowSize(Geom.compute({{}},{s},0))")
    for z in ("pill", "card"):
        r = run(f"Zone.rect('{z}',Geom.compute({{}},{s},0))")
        assert r["x"] >= 0 and r["x"] + r["width"] <= w["width"]
        assert r["y"] >= 0 and r["y"] + r["height"] <= w["height"]


def test_visual_rects_are_centered_and_inside_their_zone():
    g = geom(MAC_SCREEN)
    for z in ("pill", "card"):
        v = run(f"Zone.visualRect('{z}',{g})")
        r = run(f"Zone.rect('{z}',{g})")
        assert v["x"] >= r["x"] and v["x"] + v["width"] <= r["x"] + r["width"]
        assert v["y"] == 0 and v["height"] <= r["height"]


def test_contains_is_half_open():
    assert run("Zone.contains({x:0,y:0,width:10,height:5},0,0)") is True
    assert run("Zone.contains({x:0,y:0,width:10,height:5},10,2)") is False
    assert run("Zone.contains({x:0,y:0,width:10,height:5},9,5)") is False


def test_snapshot_reports_state_flags_and_zone():
    out = run(
        f"Zone.snapshot('DP-3',Object.assign(Hover.initial(),{{state:'open',pinned:true}}),"
        f"Zone.rect('card',{geom(UW_SCREEN)}))"
    )
    assert out["screen"] == "DP-3" and out["state"] == "open"
    assert out["flags"]["pinned"] is True and out["flags"]["held"] is False
    assert set(out["rect"]) == {"x", "y", "width", "height"}


# ---- Screens: monitor under the pointer (KTD8) ----

TWO = "[{name:'eDP-1',x:0,y:0,width:1728,height:1117},{name:'DP-3',x:1728,y:0,width:3440,height:1440}]"


def test_parse_cursor_accepts_hyprctl_json_and_rejects_junk():
    assert run("Screens.parseCursor('{\"x\": 1800, \"y\": 12}')") == {"x": 1800, "y": 12}
    assert run("Screens.parseCursor('{\"x\": 10.5, \"y\": 3.5}')") == {"x": 10.5, "y": 3.5}
    for bad in ("''", "'not json'", "'{\"x\":1}'", "'[]'", "'null'", "'{\"x\":\"a\",\"y\":1}'"):
        assert run(f"Screens.parseCursor({bad})") is None


def test_screen_at_picks_the_containing_screen():
    assert run(f"Screens.screenAt({TWO},100,100)") == "eDP-1"
    assert run(f"Screens.screenAt({TWO},1728,0)") == "DP-3"
    assert run(f"Screens.screenAt({TWO},1727,1116)") == "eDP-1"
    assert run(f"Screens.screenAt({TWO},-5,0)") is None
    assert run(f"Screens.screenAt({TWO},1000,1200)") is None


def test_pick_falls_back_to_focused_only_when_position_unknown():
    assert run(f"Screens.pick({TWO},{{x:2000,y:10}},'eDP-1')") == "DP-3"
    assert run(f"Screens.pick({TWO},null,'eDP-1')") == "eDP-1"
    assert run(f"Screens.pick({TWO},{{x:99999,y:10}},'eDP-1')") == "eDP-1"
    assert run(f"Screens.pick({TWO},null,'')") is None
    assert run("Screens.pick([],null,'x')") == "x"


def test_describe_uses_hyprland_physical_size_else_scale():
    want = {"name": "a", "width": 1728, "height": 1117, "physicalWidth": 3456, "physicalHeight": 2234}
    assert run("Screens.describe({name:'a',width:1728,height:1117,devicePixelRatio:2},{width:3456,height:2234})") == want
    assert run("Screens.describe({name:'a',width:1728,height:1117,devicePixelRatio:2},null)") == want
    assert run("Screens.describe({name:'a',width:100,height:50},{width:0,height:0})")["physicalWidth"] == 100


# ---- Fullscreen predicate (KTD6) ----

def test_only_real_fullscreen_counts():
    assert run("Fullscreen.isReal(true,[{fullscreen:2}])") is True
    assert run("Fullscreen.isReal(true,[{fullscreen:3}])") is True      # fullscreen + maximized bits
    assert run("Fullscreen.isReal(true,[{fullscreen:1}])") is False     # maximized only
    assert run("Fullscreen.isReal(true,[{fullscreen:0},{}])") is False
    assert run("Fullscreen.isReal(false,[{fullscreen:2}])") is False    # workspace says no
    assert run("Fullscreen.isReal(true,[])") is False
    assert run("Fullscreen.isReal(true,null)") is False
    assert run("Fullscreen.isReal(true,[null,{fullscreen:'2'}])") is True


def test_refresh_events_match_the_notifications_recipe():
    for n in ("fullscreen", "openwindow", "closewindow", "movewindowv2", "activewindowv2",
              "workspacev2", "focusedmonv2", "changefloatingmode"):
        assert run(f"Fullscreen.isRefreshEvent('{n}')") is True
    for n in ("urgent", "activewindow", "", "toString"):
        assert run(f"Fullscreen.isRefreshEvent('{n}')") is False


# ---- Entry: the raw plugin entry, for a whole-entry write (R21) ----

def test_entry_find_returns_the_raw_entry_or_null():
    text = json.dumps({"plugins": ["x", {"id": "other", "k": 1}, {"id": "me", "openDelay": 10, "custom": True}]})
    assert run(f"Entry.find({json.dumps(text)},'me')") == {"id": "me", "openDelay": 10, "custom": True}
    assert run(f"Entry.find({json.dumps(text)},'nope')") is None
    assert run("Entry.find('garbage','me')") is None
    assert run("Entry.find('','me')") is None


def test_save_merge_keeps_unknown_keys_and_skips_noop_write():
    text = json.dumps({"plugins": [{"id": "me", "openDelay": 140, "closeDelay": 450, "cameraWidth": 0, "custom": [1]}]})
    out = run(
        f"(()=>{{const S=require({json.dumps(str(PLUGIN / 'Settings.js'))});"
        f"const cur=Entry.find({json.dumps(text)},'me');"
        f"const same=S.merge(cur,{{openDelay:140}},'me');"
        f"const edit=S.merge(cur,{{openDelay:300}},'me');"
        f"return {{noop:S.changed(cur,same),edit:S.changed(cur,edit),merged:edit}}}})()"
    )
    assert out["noop"] is False and out["edit"] is True
    assert out["merged"]["custom"] == [1] and out["merged"]["openDelay"] == 300 and out["merged"]["id"] == "me"
