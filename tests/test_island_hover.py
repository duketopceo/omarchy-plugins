"""Hover.js for the Island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

HOVER = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Hover.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

KEEP = -1  # timer value meaning "leave the running timer alone"


def run(expr):
    js = f"const H=require({json.dumps(str(HOVER))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def drive(events, settings=None):
    """Feed events from initial(); return [{state, timer, model}] after each."""
    return run(
        f"(()=>{{let m=H.initial();const st={json.dumps(settings)};"
        f"return {json.dumps(events)}.map(e=>{{const r=H.step(m,e,st);m=r.model;"
        f"return {{state:m.state,timer:r.timer,model:m}}}})}})()"
    )


def T(hovered):
    return {"type": "timer", "hovered": hovered}


def states(out):
    return [o["state"] for o in out]


def test_ae1_open_then_close():
    out = drive(["enter", T(True), "leave", T(False)])
    assert states(out) == ["arming", "open", "leaving", "closed"]
    assert [o["timer"] for o in out] == [140, 0, 450, 0]


def test_enter_leave_before_open_timer():
    out = drive(["enter", "leave"])
    assert states(out) == ["arming", "closed"] and out[1]["timer"] == 0


def test_ae2_reenter_before_close_timer():
    out = drive(["enter", T(True), "leave", "enter"])
    assert states(out)[-1] == "open" and out[-1]["timer"] == 0


def test_close_timer_rechecks_hovered():
    out = drive(["enter", T(True), "leave", T(True)])
    assert out[-1]["state"] == "open" and out[-1]["timer"] == 0


def test_click_opens_unpinned_then_leave_leaves():
    out = drive(["click", "leave"])
    assert out[0]["state"] == "open" and out[0]["model"]["pinned"] is False
    assert out[1]["state"] == "leaving"


def test_pin_survives_leave_escape_closes_with_rearm():
    out = drive(["click", "pin", "leave", "escape"])
    assert out[1]["model"]["pinned"] is True
    assert out[2]["state"] == "open"
    assert out[3]["state"] == "closed" and out[3]["model"]["pinned"] is False
    assert out[3]["model"]["rearmLock"] is False  # pointer already left


def test_ae5_escape_inside_needs_leave_and_reenter():
    out = drive(["enter", T(True), "escape", "enter", "leave", "enter"])
    assert out[2]["state"] == "closed" and out[2]["model"]["rearmLock"] is True
    assert out[3]["state"] == "closed"
    assert out[4]["model"]["rearmLock"] is False
    assert out[5]["state"] == "arming"


def test_unpin_closes_with_rearm_when_inside():
    out = drive(["enter", T(True), "pin", "unpin"])
    assert out[3]["state"] == "closed" and out[3]["model"]["rearmLock"] is True


def test_ipc_close_inside_sets_rearm():
    out = drive(["enter", T(True), "ipcClose", "enter"])
    assert out[2]["state"] == "closed" and out[2]["model"]["rearmLock"] is True
    assert out[3]["state"] == "closed"


def test_hold_outside_goes_leaving_inside_stays_open():
    out = drive(["click", "holdStart", "leave", "holdEnd"])
    assert out[2]["state"] == "open"
    assert out[3]["state"] == "leaving" and out[3]["timer"] == 450
    out = drive(["enter", T(True), "holdStart", "holdEnd"])
    assert out[3]["state"] == "open"


def test_ae4_summon_leave_ignored_until_enter_then_timeout():
    out = drive(["summon", "leave", T(False)])
    assert out[0]["state"] == "open" and out[0]["timer"] == 5000
    assert out[1]["state"] == "open"
    assert out[2]["state"] == "closed"


def test_summon_enter_leave_is_normal():
    out = drive(["summon", "enter", "leave"])
    assert out[1]["timer"] == 0
    assert out[2]["state"] == "leaving"


def test_summon_held_timeout_defers_then_restarts():
    out = drive(["summon", "holdStart", T(False), "holdEnd"])
    assert out[2]["state"] == "open" and out[2]["timer"] == 0
    assert out[3]["state"] == "open" and out[3]["timer"] == 5000


def test_summon_while_pointer_inside_counts_as_visited():
    # Pointer already on the card when the keybinding fires: no enter edge
    # will come, so the 5 s untouched timeout must not close it (R7, R11).
    out = drive(["enter", T(True), "summon", T(True), "leave"])
    assert out[2]["state"] == "open"
    assert out[3]["state"] == "open"
    assert out[4]["state"] == "leaving"


def test_summon_focuses_pill_click_does_not():
    assert drive(["summon"])[0]["model"]["focused"] is True
    assert drive(["click"])[0]["model"]["focused"] is False
    assert drive(["click", "cardClick"])[1]["model"]["focused"] is True


@pytest.mark.parametrize("setup", [[], ["enter"], ["click"], ["click", "leave"], ["summon"]])
def test_fullscreen_closes_and_ignores_enter(setup):
    out = drive(setup + ["fullscreenOn", "enter"])
    assert out[len(setup)]["state"] == "closed" and out[len(setup)]["timer"] == 0
    assert out[-1]["state"] == "closed"


def test_fullscreen_off_stays_closed_until_fresh_enter():
    out = drive(["fullscreenOn", "enter", "fullscreenOff", T(True), "enter"])
    assert out[2]["state"] == "closed"
    assert out[3]["state"] == "closed"
    assert out[4]["state"] == "arming"


def test_open_delay_zero_opens_immediately():
    out = drive(["enter"], {"openDelay": 0})
    assert out[0]["state"] == "open" and out[0]["timer"] == 0


def test_delays_clamped():
    assert run("H.clampSettings({openDelay:5000,closeDelay:50})") == {
        "openDelay": 600, "closeDelay": 150, "summonTimeout": 5000}
    assert run("H.clampSettings(undefined)") == {"openDelay": 140, "closeDelay": 450, "summonTimeout": 5000}
    out = drive(["enter", T(True), "leave"], {"openDelay": 5000, "closeDelay": 50})
    assert [o["timer"] for o in out] == [600, 0, 150]


def test_unknown_event_leaves_model_unchanged():
    out = drive(["enter", "bogus"])
    assert out[1]["model"] == out[0]["model"] and out[1]["timer"] == KEEP


def test_zone_for():
    assert run("['closed','arming','open','leaving'].map(s=>H.zoneFor({state:s}))") == [
        "pill", "pill", "card", "card"]
