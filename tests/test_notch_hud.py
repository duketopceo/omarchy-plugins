"""Hud.js (volume / brightness HUD) and its settings wiring, run through node."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = (
        f"const H=require({json.dumps(str(NOTCH / 'Hud.js'))});"
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"const A=require({json.dumps(str(NOTCH / 'Activity.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def reading(vol=None, muted=False, bri=None):
    v = "null" if vol is None else f"{{volume:{vol},muted:{str(muted).lower()}}}"
    b = "null" if bri is None else f"{{percent:{bri},device:'apple-panel-bl'}}"
    return f"{{volume:{v},brightness:{b}}}"


def test_parse_volume_and_mute():
    assert run("H.parseVolume('Volume: 0.83')") == {"volume": 83, "muted": False}
    assert run("H.parseVolume('Volume: 0.40 [MUTED]')") == {"volume": 40, "muted": True}
    assert run("H.parseVolume('Volume: 1.50')")["volume"] == 150
    assert run("H.parseVolume('Volume: 9.00')")["volume"] == 150
    assert run("H.parseVolume('')") is None and run("H.parseVolume('garbage')") is None


def test_parse_brightness_internal_backlight_only():
    assert run("H.parseBrightness('apple-panel-bl,backlight,150,30%,500')") == {"percent": 30, "device": "apple-panel-bl"}
    assert run("H.parseBrightness('input3::capslock,leds,0,0%,1')") is None   # not a backlight
    assert run("H.parseBrightness('')") is None


def test_parse_probe_tolerates_missing_backlight_and_wpctl():
    both = run("H.parseProbe('V Volume: 0.50\\nB apple-panel-bl,backlight,75,15%,500\\n')")
    assert both["volume"]["volume"] == 50 and both["brightness"]["percent"] == 15
    assert run("H.parseProbe('V Volume: 0.50\\n')")["brightness"] is None   # docked, no backlight
    assert run("H.parseProbe('')") == {"volume": None, "brightness": None}


def test_probe_script_is_read_only_and_backlight_scoped():
    script = run("H.probeArgs()")[2]
    assert "get-volume" in script and "-c backlight" in script
    assert not re.search(r"set-volume|set-mute|brightnessctl\s+(-q\s+)?set", script)


def test_first_reading_is_baseline_not_a_hud():
    m = run(f"H.step(H.initial(),{reading(50, bri=30)},1000)")
    assert m["seen"] and m["until"] == 0 and not run(f"H.active(H.step(H.initial(),{reading(50)},1000),1001,'notch')")


def test_volume_change_shows_hud_then_expires():
    base = f"H.step(H.initial(),{reading(50)},1000)"
    ch = f"H.step({base},{reading(60)},2000)"
    m = run(ch)
    assert m["kind"] == "volume" and m["text"] == "Volume 60%" and m["level"] == 60 and m["until"] == 2000 + 1600
    assert run(f"H.active({ch},2500,'notch')") is True
    assert run(f"H.active({ch},3700,'notch')") is False


def test_mute_state_and_unmute():
    base = f"H.step(H.initial(),{reading(50)},1000)"
    muted = run(f"H.step({base},{reading(50, muted=True)},2000)")
    assert muted["text"] == "Muted" and muted["muted"] is True and muted["level"] == 0
    back = run(f"H.step(H.step({base},{reading(50, muted=True)},2000),{reading(50)},3000)")
    assert back["text"] == "Volume 50%" and back["muted"] is False


def test_unchanged_reading_returns_same_model():
    assert run(f"(()=>{{const m=H.step(H.initial(),{reading(50, bri=30)},1000);return H.step(m,{reading(50, bri=30)},2000)===m}})()") is True


def test_brightness_change_shows_brightness_hud():
    base = f"H.step(H.initial(),{reading(50, bri=30)},1000)"
    m = run(f"H.step({base},{reading(50, bri=45)},2000)")
    assert m["kind"] == "brightness" and m["text"] == "Brightness 45%" and m["level"] == 45


def test_brightness_absent_never_errors_or_flashes():
    base = f"H.step(H.initial(),{reading(50)},1000)"          # docked, no backlight
    m = run(f"H.step({base},{reading(50)},2000)")
    assert m["kind"] == "" and m["brightness"] is None


def test_only_notch_owner_shows():
    ch = f"H.step(H.step(H.initial(),{reading(50)},1000),{reading(70)},2000)"
    assert run(f"H.active({ch},2100,'omarchy')") is False
    assert run(f"H.active({ch},2100,'notch')") is True
    assert run("H.owner({hudOwner:'notch'})") == "notch"
    assert run("H.owner({hudOwner:'junk'})") == "omarchy" and run("H.owner(null)") == "omarchy"


def test_setting_defaults_to_omarchy_and_documents_the_osd():
    assert run("S.resolve(null).hudOwner") == "omarchy"
    assert run("S.resolve({hudOwner:'notch'}).hudOwner") == "notch"
    assert run("S.resolve({hudOwner:'x'}).hudOwner") == "omarchy"
    f = run("S.field('hudOwner')")
    assert "omarchy.osd" in f["detail"] and f["detailWhen"] == "notch" and "Omarchy" in f["hint"]


def test_hud_outranks_dictation_and_is_one_activity():
    pick = run("A.pick([{id:'dictation',active:true,priority:90,text:'rec'},{id:'hud',active:true,priority:H.HUD_PRIORITY,text:'Volume 60%'}]).id")
    assert pick == "hud"


def test_qml_runs_only_when_notch_owns_the_popup():
    qml = (NOTCH / "Island.qml").read_text()
    assert 'HudActivity { id: hud; enabled: root.settings.hudOwner === "notch" }' in qml
    act = (NOTCH / "HudActivity.qml").read_text()
    assert "pactl" in act and "running: ha.enabled" in act
