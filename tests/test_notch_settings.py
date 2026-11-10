"""Settings.js registry, setup layout and sections for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

# Panel body is 380 high; the Settings tab loses the tab strip (36) and its 28 px header.
SETTINGS_AVAIL = 380 - 32 - 36 - 14 - 28 - 8


def run(expr):
    js = (
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"const C=require({json.dumps(str(NOTCH / 'Capabilities.js'))});"
        f"const T=require({json.dumps(str(NOTCH / 'Tabs.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


# ---------------------------------------------------------------- U1 setup layout

def test_six_modules_first_run_keep_done_inside_the_card():
    lay = run(f"S.setupLayout(6,true,{SETTINGS_AVAIL})")
    assert lay["height"] <= SETTINGS_AVAIL
    assert lay["footerH"] > 0  # Done has its own slot outside the list
    s = run("S.SETUP")
    assert lay["listH"] + s["pad"] + s["intro"] + lay["footerH"] + s["gap"] == lay["height"]
    assert lay["contentH"] == 6 * s["row"]


def test_short_room_scrolls_the_list_and_still_reserves_done():
    lay = run("S.setupLayout(6,true,150)")
    assert lay["height"] == 150 and lay["scroll"] is True
    assert lay["footerH"] > 0 and lay["listH"] >= 0
    s = run("S.SETUP")
    assert lay["listH"] == 150 - (s["pad"] + s["intro"] + s["footer"] + s["gap"])


def test_layout_holds_at_any_offer_count():
    for n in range(1, 25):
        lay = run(f"S.setupLayout({n},true,{SETTINGS_AVAIL})")
        assert lay["height"] <= SETTINGS_AVAIL and lay["footerH"] > 0


def test_after_first_run_the_strip_leaves_room_for_the_settings_below():
    lay = run(f"S.setupLayout(6,false,{SETTINGS_AVAIL})")
    assert lay["footerH"] == 0
    assert SETTINGS_AVAIL - lay["height"] >= run("S.SETUP.minBelow")


def test_zero_offers_shows_one_note_row_and_no_strip_without_setup():
    lay = run("S.setupLayout(0,true,300)")
    assert lay["contentH"] == run("S.SETUP.row")
    probe = "C.emptyProbe()"
    assert run(f"C.offers({probe},S.resolve({{setupDone:true}}))") == []
    assert run(f"C.needsSetup(S.resolve({{setupDone:true}}))") is False
