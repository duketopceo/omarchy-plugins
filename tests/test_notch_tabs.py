"""Tabs.js, Settings.js, Activity.js and Plugins.js for the notch island, run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
FIXTURE = Path(__file__).resolve().parent / "fixtures/notch_shell.json"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = (
        f"const T=require({json.dumps(str(NOTCH / 'Tabs.js'))});"
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"const A=require({json.dumps(str(NOTCH / 'Activity.js'))});"
        f"const P=require({json.dumps(str(NOTCH / 'Plugins.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


# ---------------------------------------------------------------- tabs

def test_tab_list_shape_and_sources():
    tabs = run("T.TABS")
    assert [t["id"] for t in tabs] == ["home", "media", "agents", "ai", "messages", "network", "power", "system", "stocks", "screenshots", "dayflow", "timer", "plugins", "settings"]
    for t in tabs:
        assert {"id", "title", "short", "glyph", "source"} <= set(t) <= {"id", "title", "short", "glyph", "source", "optional", "size"} and len(t["short"]) <= 7 and t["glyph"] and t["title"]
    assert {t["id"]: t["source"] for t in tabs} == {
        "home": "HomeTab.qml", "media": "MediaTab.qml", "agents": "AgentsTab.qml",
        "ai": "AiUsageTab.qml",
        "messages": "MessagesTab.qml", "network": "NetworkTab.qml", "power": "PowerTab.qml", "system": "SystemTab.qml", "stocks": "StocksTab.qml", "screenshots": "ScreenshotsTab.qml", "dayflow": "DayflowTab.qml", "timer": "TimerTab.qml",
        "plugins": "PluginsTab.qml", "settings": "SettingsTab.qml"}


def test_optional_tabs_off_by_default_and_setup_keys_exist():
    off = [t["id"] for t in run("T.visibleTabs(S.resolve(null))")]
    assert "screenshots" not in off
    # local branch keeps Agents/Messages on by default (owner uses both); upstream default is off
    assert "agents" in off and "messages" in off
    assert "network" in off and "stocks" in off and "plugins" in off
    on = [t["id"] for t in run("T.visibleTabs(S.resolve({snapdex:true,optAgents:true,optMessages:true}))")]
    assert set(["screenshots", "agents", "messages"]).issubset(on)
    assert run("S.DEFAULTS.snapdex") is False
    assert run("S.DEFAULTS.optAgents") is True
    assert run("S.DEFAULTS.setupDone") is False
    assert run("S.field('snapdex').type") == "bool"
    prefs = [f["key"] for f in run("S.prefFields()")]
    assert "setupDone" not in prefs and "snapdex" not in prefs and "clockSeconds" in prefs


def test_shipped_tab_files_exist():
    for t in run("T.TABS"):
        assert (NOTCH / t["source"]).is_file(), t["source"]
    assert (NOTCH / "Notch.qml").is_file()
    assert (NOTCH / "bin" / "notch-data").is_file()


def test_notch_has_no_required_sibling_plugin_imports():
    """OOB: QML/JS must not import other plugins; optional paths are detect-only."""
    forbidden = (
        "import \"../lukedaduke",
        "import \"../io.github.duketopceo.",
        "qs.Plugins.",
    )
    for path in list(NOTCH.glob("*.qml")) + list(NOTCH.glob("*.js")):
        text = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{path.name} contains {needle!r}"


def test_select_falls_back_to_home():
    assert run("T.select('plugins').id") == "plugins"
    assert run("T.select('nope').id") == "home"
    assert run("T.select(undefined).id") == "home"


def test_resolve_states():
    assert run("T.resolve(T.byId('home'), {home:true})") == {"state": "ready", "source": "HomeTab.qml", "message": ""}
    assert run("T.resolve(T.byId('home'), {})")["state"] == "loading"
    assert run("T.resolve(T.byId('home'), null)")["state"] == "loading"


def test_missing_source_is_quiet_coming_soon():
    r = run("T.resolve(T.byId('media'), {media:false})")
    assert r == {"state": "missing", "source": "", "message": "Media is coming soon"}
    assert "rror" not in r["message"]
    assert run("T.resolve(null, {}).state") == "missing"
    assert run("T.failed(T.byId('agents')).message") == "Agents is coming soon"


# ---------------------------------------------------------------- activities

def test_highest_priority_active_wins():
    out = run("A.pick([{id:'media',active:true,priority:50,text:'song'},{id:'dict',active:true,priority:90,text:'Listening'}]).id")
    assert out == "dict"


def test_inactive_and_empty_text_are_skipped():
    assert run("A.pick([{id:'a',active:false,priority:99,text:'x'},{id:'b',active:true,priority:1,text:''}])") is None
    assert run("A.pick([{id:'a',active:false,priority:99,text:'x'},{id:'b',active:true,priority:1,text:'y'}]).id") == "b"


def test_ties_go_to_first_listed_and_junk_is_ignored():
    assert run("A.pick([{id:'a',active:true,priority:5,text:'x'},{id:'b',active:true,priority:5,text:'y'}]).id") == "a"
    assert run("A.pick([null, 3, {active:'yes',priority:1,text:'x'}])") is None
    assert run("A.pick(undefined)") is None
    assert run("A.pick([])") is None


def test_label_prefixes_glyph():
    assert run("A.label({text:'song',glyph:'G'})") == "G song"
    assert run("A.label({text:'song'})") == "song"
    assert run("A.label(null)") == ""


# ---------------------------------------------------------------- settings

def test_defaults_when_entry_absent_or_junk():
    d = run("S.resolve(null)")
    assert (d["clockSeconds"], d["slideSeconds"], d["showWeather"], d["showStocks"]) == (24, 7, True, True)
    assert (d["unit"], d["unitName"], d["clockHours"], d["timeFormat"]) == ("F", "fahrenheit", 12, "h:mm AP")
    assert (d["cameraWidth"], d["hoverDelay"]) == (0, 150)
    assert run("S.resolve({clockSeconds:'abc',showWeather:'no',unit:'K',clockHours:13,cameraWidth:-5,hoverDelay:null})") == d


def test_resolve_reads_valid_values_and_clamps():
    r = run("S.resolve({clockSeconds:40,unit:'C',clockHours:24,showStocks:false,cameraWidth:188,hoverDelay:99999,slideSeconds:0})")
    assert (r["clockSeconds"], r["unit"], r["unitName"], r["timeFormat"]) == (40, "C", "celsius", "HH:mm")
    assert (r["showStocks"], r["cameraWidth"], r["hoverDelay"], r["slideSeconds"]) == (False, 188, 1000, 2)


def test_overrides_win_over_entry():
    assert run("S.resolve({unit:'C'},{unit:'F'}).unit") == "F"


def test_next_steps_and_wraps():
    assert run("S.next(S.resolve(null),'showWeather',1)") is False
    assert run("S.next(S.resolve(null),'unit',1)") == "C"
    assert run("S.next(S.resolve({unit:'C'}),'unit',1)") == "F"
    assert run("S.next(S.resolve(null),'clockHours',-1)") == 24
    assert run("S.next(S.resolve(null),'clockSeconds',1)") == 40   # segmented: 12 / 24 / 40 / 60
    assert run("S.next(S.resolve({clockSeconds:5}),'clockSeconds',-1)") == 5
    assert run("S.next(S.resolve(null),'cameraWidth',1)") == 10
    assert run("S.next(S.resolve(null),'bogus',1)") is None


def test_format():
    assert run("S.format(S.field('cameraWidth'),0)") == "auto"
    assert run("S.format(S.field('cameraWidth'),188)") == "188 px"
    assert run("S.format(S.field('showStocks'),false)") == "off"
    assert run("S.format(S.field('unit'),'C')") == "°C"


def test_mutator_creates_and_merges_entry():
    out = run("(()=>{const c={};S.settingsMutator('id.x',{unit:'C'})(c);S.settingsMutator('id.x',{clockSeconds:30})(c);return c})()")
    assert out == {"plugins": [{"id": "id.x", "unit": "C", "clockSeconds": 30}]}
    out = run("(()=>{const c={plugins:[{id:'a',k:1},{id:'id.x',keep:true}]};S.settingsMutator('id.x',{unit:'F'})(c);return c})()")
    assert out["plugins"] == [{"id": "a", "k": 1}, {"id": "id.x", "keep": True, "unit": "F"}]


def test_fixture_entry_round_trip():
    cfg = json.loads(FIXTURE.read_text())
    r = run(f"S.resolve(S.pluginEntry({json.dumps(cfg)},'io.github.duketopceo.notch'))")
    assert (r["clockSeconds"], r["unitName"], r["showStocks"], r["cameraWidth"]) == (40, "celsius", False, 188)
    assert run(f"S.pluginEntry({json.dumps(cfg)},'missing')") is None


def test_unit_reaches_notch_data_args():
    assert run("S.dataArgs(S.resolve({unit:'C'}))") == ["--max-age", "900", "--unit", "celsius"]
    assert run("S.dataArgs(S.resolve(null))") == ["--max-age", "900", "--unit", "fahrenheit"]


# ---------------------------------------------------------------- plugins tab

def test_tray_ids_from_fixture():
    cfg = json.loads(FIXTURE.read_text())
    assert run(f"P.trayIds({json.dumps(cfg)})") == ["example.alpha", "example.beta", "example.gamma"]


def test_tray_ids_absent_config():
    for cfg in ("null", "{}", "{bar:{}}", "{bar:{layout:{tray:'x'}}}"):
        assert run(f"P.trayIds({cfg})") == []


def test_slot_info_name_and_icon():
    m = json.dumps({"id": "a.b", "name": "Plain", "barWidget": {"displayName": "Nice"}, "preview": "art/p.png"})
    i = run(f"P.slotInfo('a.b',{json.dumps(m)},'/h')")
    assert i["name"] == "Nice" and i["image"] == "/h/.config/omarchy/plugins/a.b/art/p.png"
    m = json.dumps({"name": "Plain", "preview": "\U000f0431"})
    i = run(f"P.slotInfo('a.b',{json.dumps(m)},'/h')")
    assert i["name"] == "Plain" and i["image"].endswith("/a.b/icon.png") and i["glyph"] == "\U000f0431"
    m = json.dumps({"name": "Plain", "preview": "/abs/p.svg"})
    assert run(f"P.slotInfo('a.b',{json.dumps(m)},'/h')")["image"] == "/abs/p.svg"


def test_slot_info_generic_when_manifest_missing():
    i = run("P.slotInfo('lukedaduke.fan','','/h')")
    assert i["name"] == "fan" and i["image"].endswith("/lukedaduke.fan/icon.png")
    assert i["glyph"] == run("P.GLYPHS['lukedaduke.fan']") != run("P.GENERIC_GLYPH")


def test_preview_png_is_never_the_icon():
    # preview.png is a screenshot of the panel, not an icon.
    m = json.dumps({"name": "X", "preview": "preview.png"})
    assert run(f"P.slotInfo('a.b',{json.dumps(m)},'/h')")["image"].endswith("/a.b/icon.png")


def test_open_chain_and_step_results():
    chain = run("P.openChain('robzolkos.github')")
    assert [s["kind"] for s in chain] == ["summon", "ipc", "run"]
    assert chain[0]["cmd"][-3:] == ["summon", "robzolkos.github", "{}"]
    assert chain[1]["cmd"][-2:] == ["robzolkos.github", "toggle"]
    assert [s["kind"] for s in run("P.openChain('lukedaduke.fan')")] == ["summon", "ipc"]
    assert [s["kind"] for s in run("P.openChain('x.y',['/bin/true'])")] == ["summon", "ipc", "run"]
    assert all(s["cmd"][0].startswith("/") for s in chain)
    summon, ipc, fallback = chain
    assert run("P.stepOk(%s,0,'ok\\n')" % json.dumps(summon)) is True
    assert run("P.stepOk(%s,0,'unknown')" % json.dumps(summon)) is False
    assert run("P.stepOk(%s,0,'')" % json.dumps(ipc)) is True
    assert run("P.stepOk(%s,0,'Target not found.')" % json.dumps(ipc)) is False  # qs exits 0 here
    assert run("P.stepOk(%s,1,'')" % json.dumps(fallback)) is False


def test_open_commands():
    assert run("P.ipcCommand('a.b')") == ["qs", "-p", "/usr/share/omarchy/shell", "ipc", "call", "shell", "toggle", "a.b", "{}"]
    assert run("P.manifestPath('/h','a.b')") == "/h/.config/omarchy/plugins/a.b/manifest.json"


def test_expand_hover_delay_setting():
    js = f"const E=require({json.dumps(str(NOTCH / 'Expand.js'))});console.log(JSON.stringify([E.step('collapsed','enter',400),E.step('collapsed','enter',0),E.step('collapsed','enter')]))"
    out = json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)
    assert [o["timer"] for o in out] == [400, 1, 150]


def test_per_tab_size_hook():
    assert run("T.sizeFor('home')") == {"w": 720, "h": 380}
    # Every tab opens at Home's size so the panel never jumps between tabs.
    for tab in ("stocks", "media", "system", "settings", "plugins"):
        assert run("T.sizeFor('%s')" % tab) == {"w": 720, "h": 380}
    assert run("T.sizeFor('nope')") is None
    assert run("T.maxHeight(240)") == 380
