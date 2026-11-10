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


# ---------------------------------------------------------------- U2 sections and one switch per feature

def rows_by_section():
    secs = run("S.sections(T.TABS,T.PINNED)")
    return {s["id"]: s["rows"] for s in secs}, secs


def test_four_sections_in_order():
    _, secs = rows_by_section()
    assert [s["title"] for s in secs] == ["Look", "Tabs and features", "Data sources", "Advanced"]
    assert all(s["rows"] for s in secs)


def test_every_visible_setting_appears_exactly_once():
    by, _ = rows_by_section()
    keys = [r["key"] for rows in by.values() for r in rows]
    assert len(keys) == len(set(keys)), "a setting is drawn twice"
    visible = [f["key"] for f in run("S.FIELDS") if not f.get("hidden")]
    assert set(visible) <= set(keys)
    # hidden bookkeeping keys never get a row
    assert not {"setupDone", "hiddenTabs", "tabUsage"} & set(keys)


def test_every_setup_module_keeps_an_off_switch_after_setup():
    by, _ = rows_by_section()
    switch = {r["key"]: r for rows in by.values() for r in rows if r["type"] == "bool"}
    for m in run("C.MODULES"):
        assert m["setting"] in switch, f"{m['id']} cannot be turned off after setup"
    settings = "S.resolve({setupDone:true,snapdex:true})"
    assert run(f"S.rowValue({settings},{json.dumps(switch['snapdex'])})") is True
    assert run(f"S.rowPatch({settings},{json.dumps(switch['snapdex'])},false)") == {"snapdex": False}


def test_feature_switches_live_in_tabs_and_features_only():
    by, _ = rows_by_section()
    feat = {r["key"] for r in by["features"]}
    for f in run("S.featureFields()"):
        assert f["key"] in feat
    for sec in ("look", "data", "advanced"):
        assert not {f["key"] for f in run("S.featureFields()")} & {r["key"] for r in by[sec]}


def test_built_in_tabs_get_a_switch_but_optional_and_pinned_do_not():
    by, _ = rows_by_section()
    tab_rows = {r["tabId"] for r in by["features"] if r["kind"] == "tab"}
    tabs = run("T.TABS")
    expect = {t["id"] for t in tabs if "optional" not in t and t["id"] not in ("home", "settings")}
    assert tab_rows == expect and {"media", "network", "power", "system", "stocks", "plugins"} <= tab_rows
    assert "settings" not in tab_rows and "home" not in tab_rows
    # a tab with its own optional switch is not switchable twice
    assert not tab_rows & {t["id"] for t in tabs if "optional" in t}


def test_tab_row_value_and_patch_round_trip_through_hidden_tabs():
    row = json.dumps({"key": "tab:media", "kind": "tab", "tabId": "media", "type": "bool"})
    assert run(f"S.rowValue(S.resolve(null),{row})") is True
    assert run(f"S.rowValue(S.resolve({{hiddenTabs:['media']}}),{row})") is False
    assert run(f"S.rowPatch(S.resolve(null),{row},false)") == {"hiddenTabs": ["media"]}
    assert run(f"S.rowPatch(S.resolve({{hiddenTabs:['media','power']}}),{row},true)") == {"hiddenTabs": ["power"]}
    assert run(f"S.rowPatch(S.resolve({{hiddenTabs:['media']}}),{row},false)") == {"hiddenTabs": ["media"]}


def test_hints_exist_for_the_jargon_labels():
    by, _ = rows_by_section()
    hints = {r["key"]: r["hint"] for rows in by.values() for r in rows}
    for key in ("snapdex", "optAgents", "optMessages", "cameraWidth", "slideSeconds", "dayflow", "hoverDelay", "clockSeconds"):
        assert hints[key].strip(), f"{key} has no hint"
    assert "herdr" in hints["optAgents"] and "Blip" in hints["optMessages"] and "Snapdex" in hints["snapdex"]
    assert all(len(h) <= 70 for h in hints.values()), "hints are one line"


def test_small_range_ints_are_segmented_and_big_ones_are_not():
    f = {x["key"]: x for x in run("S.FIELDS")}
    for key in ("slideSeconds", "clockSeconds", "hoverDelay"):
        assert f[key]["choices"] and all(f[key]["min"] <= c <= f[key]["max"] for c in f[key]["choices"])
    assert "choices" not in f["cameraWidth"]


def test_choices_keep_a_saved_off_list_value_and_step_through_them():
    f = "S.field('slideSeconds')"
    assert run(f"S.choicesFor({f},7)") == [4, 7, 10, 15]
    assert run(f"S.choicesFor({f},9)") == [4, 7, 9, 10, 15]
    assert run("S.next(S.resolve(null),'slideSeconds',1)") == 10
    assert run("S.next(S.resolve({slideSeconds:15}),'slideSeconds',1)") == 15
    assert run("S.resolve({slideSeconds:9}).slideSeconds") == 9


def test_list_and_map_settings_are_sanitised():
    assert run("S.resolve({hiddenTabs:['media','media',3,'']}).hiddenTabs") == ["media"]
    assert run("S.resolve({hiddenTabs:'media'}).hiddenTabs") == []
    assert run("S.resolve({tabUsage:{power:3,x:-1,y:'z'}}).tabUsage") == {"power": 3}
    # defaults are copied, never shared between resolves
    assert run("(()=>{const a=S.resolve(null);a.hiddenTabs.push('x');return S.resolve(null).hiddenTabs})()") == []


def test_charging_alert_is_a_feature_switch_on_by_default():
    assert run("S.DEFAULTS.chargingAlert") is True
    by, _ = rows_by_section()
    assert any(r["key"] == "chargingAlert" for r in by["features"])
