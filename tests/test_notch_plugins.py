"""Plugins.js hub and Tabs.visibleIds for the notch Plugins tab, run through node.

Covers plan U1 / R1-R6: every plugin reachable as a large tile, sectioned into
Tray / System / Agent, embedded tiles opening the notch's own tab, everything
else through the launcher chain, and the Configure row opening Settings.
"""
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
        f"const P=require({json.dumps(str(NOTCH / 'Plugins.js'))});"
        f"const T=require({json.dumps(str(NOTCH / 'Tabs.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def fixture_config():
    return json.loads(FIXTURE.read_text())


# ---------------------------------------------------------------- sections

def test_sections_are_tray_system_agent():
    assert run("P.SECTIONS") == [
        {"id": "tray", "title": "Tray"},
        {"id": "system", "title": "System"},
        {"id": "agent", "title": "Agent"},
    ]


@pytest.mark.parametrize("plugin,section", [
    ("nixfred.blip", "system"),
    ("omarchy.network", "system"),
    ("omarchy.auth", "system"),
    ("omarchy.bluetooth", "system"),
    ("omarchy.tray", "system"),
    ("lukedaduke.power", "system"),
    ("lukedaduke.lidguard", "system"),
    ("io.github.ncr.omaphones", "system"),
    ("io.github.duketopceo.wisp", "system"),
    ("ssupt.audio-control", "system"),
    ("lukedaduke.agents", "agent"),
    ("jankeesvw.herdr", "agent"),
    ("io.github.duketopceo.dayflow", "tray"),
    ("lukedaduke.fan", "tray"),
    ("io.github.duketopceo.omaseal", "tray"),
])
def test_section_assignment(plugin, section):
    assert run(f"P.sectionOf({json.dumps(plugin)})") == section


def test_matcher_accepts_short_names_and_full_ids():
    assert run("P.matches('omarchy.network', ['network'])") is True
    assert run("P.matches('lukedaduke.power', ['power'])") is True
    assert run("P.matches('lukedaduke.power', ['network'])") is False
    assert run("P.matches('', ['power'])") is False


# ---------------------------------------------------------------- hub grouping

def test_hub_groups_the_fixture_tray():
    cfg = fixture_config()
    groups = run(f"P.hub({json.dumps(cfg)}, null)")
    assert [g["id"] for g in groups] == ["tray", "system", "agent"]
    assert groups[0]["tiles"] == ["example.alpha", "example.beta", "example.gamma"]
    # The confirmed right-side set is always reachable from the hub (R5), in
    # RIGHT_IDS order, split by section.
    right = run("P.RIGHT_IDS")
    for plugin in ("nixfred.blip", "omarchy.network", "omarchy.auth", "omarchy.bluetooth",
                   "omarchy.tray", "lukedaduke.power", "lukedaduke.lidguard",
                   "io.github.ncr.omaphones", "io.github.duketopceo.wisp", "lukedaduke.agents"):
        assert plugin in right
    system = [i for i in right if run(f"P.sectionOf({json.dumps(i)})") == "system"]
    agent = [i for i in right if run(f"P.sectionOf({json.dumps(i)})") == "agent"]
    assert groups[1]["tiles"] == system
    assert groups[2]["tiles"] == agent
    assert "lukedaduke.agents" in groups[2]["tiles"]


def test_hub_never_loses_a_tray_plugin():
    cfg = fixture_config()
    ids = [t for g in run(f"P.hub({json.dumps(cfg)}, null)") for t in g["tiles"]]
    assert len(ids) == len(set(ids))
    for plugin in ("example.alpha", "example.beta", "example.gamma"):
        assert plugin in ids
    # Bigger than the old tray-only grid (3 slots on this fixture).
    assert len(ids) >= 3


def test_hub_filters_to_installed_plugins_when_known():
    cfg = fixture_config()
    installed = ["example.alpha", "example.beta", "example.gamma", "nixfred.blip", "lukedaduke.power"]
    groups = run(f"P.hub({json.dumps(cfg)}, {json.dumps(installed)})")
    assert [g["id"] for g in groups] == ["tray", "system"]
    assert groups[1]["tiles"] == ["nixfred.blip", "lukedaduke.power"]


def test_hub_without_installed_list_does_not_filter():
    cfg = fixture_config()
    assert run(f"P.hub({json.dumps(cfg)}, null)") == run(f"P.hub({json.dumps(cfg)}, [])")


def test_hub_dedupes_and_orders_tray_first():
    cfg = {"bar": {"layout": {"tray": [{"id": "nixfred.blip"}, {"id": "lukedaduke.fan"}, {"id": "nixfred.blip"}]}}}
    groups = run(f"P.hub({json.dumps(cfg)}, null)")
    assert groups[0] == {"id": "tray", "title": "Tray", "tiles": ["lukedaduke.fan"]}
    assert groups[1]["tiles"][0] == "nixfred.blip"
    assert groups[1]["tiles"].count("nixfred.blip") == 1


def test_empty_config_still_shows_the_confirmed_set():
    groups = run("P.hub(null, null)")
    assert [g["id"] for g in groups] == ["system", "agent"]
    assert sum(len(g["tiles"]) for g in groups) == len(run("P.RIGHT_IDS"))


# ---------------------------------------------------------------- tile actions

def test_embedded_tiles_open_the_matching_tab():
    assert run("P.action('lukedaduke.power', ['power'])") == {"kind": "tab", "id": "power", "requires": ""}
    assert run("P.action('omarchy.network', ['network'])") == {"kind": "tab", "id": "network", "requires": ""}
    assert run("P.action('lukedaduke.agents', ['agents'])") == {"kind": "tab", "id": "agents", "requires": ""}
    assert run("P.action('io.github.duketopceo.dayflow', ['dayflow'])")["id"] == "dayflow"


def test_other_tiles_fall_back_to_the_launcher_chain():
    for plugin in ("lukedaduke.fan", "io.github.duketopceo.omaseal", "omarchy.bluetooth", "nixfred.blip"):
        assert run(f"P.action({json.dumps(plugin)}, ['power', 'network'])") == {
            "kind": "chain", "id": plugin, "requires": ""}
    # No tab list means "assume available", which is still a chain for a
    # plugin that is not embedded anywhere.
    assert run("P.action('lukedaduke.fan', null)")["kind"] == "chain"


def test_embed_degrades_when_its_tab_is_not_visible():
    # An optional tab that is off falls back to the launcher and says why (R10).
    assert run("P.action('io.github.duketopceo.dayflow', ['home', 'plugins'])") == {
        "kind": "chain", "id": "io.github.duketopceo.dayflow", "requires": "Dayflow"}
    assert run("P.action('io.github.duketopceo.snapdex', ['home'])")["requires"] == "Screenshots"
    assert run("P.launchHint('io.github.duketopceo.dayflow', ['home'])") == "Requires Dayflow"
    assert run("P.launchHint('lukedaduke.power', ['power'])") == ""


def test_chain_targets_are_real_launcher_steps():
    # The chain a tile falls back to is the existing summon -> ipc -> fallback.
    assert run("[P.openChain('lukedaduke.fan')[0].kind, P.openChain('lukedaduke.fan')[1].kind]") == ["summon", "ipc"]


def test_configure_opens_settings():
    assert run("P.CONFIGURE.label") == "Configure"
    assert run("P.configure()") == {"kind": "tab", "id": "settings", "requires": ""}


# ---------------------------------------------------------------- tile status

def test_status_is_a_pill_when_embedded():
    ctx = {"tabs": ["power"], "tray": ["lukedaduke.power"]}
    got = run(f"P.status('lukedaduke.power', {json.dumps(ctx)})")
    assert (got["kind"], got["on"], got["text"]) == ("pill", True, "In notch")


def test_status_is_a_dot_on_or_off_the_bar():
    ctx = {"tabs": ["power"], "tray": ["lukedaduke.fan"], "right": ["nixfred.blip"]}
    got = run(f"P.status('lukedaduke.fan', {json.dumps(ctx)})")
    assert (got["kind"], got["on"], got["text"]) == ("dot", True, "On the bar")
    got = run(f"P.status('nixfred.blip', {json.dumps(ctx)})")
    assert got["on"] is True and got["text"] == "On the bar" and got["kind"] == "dot"
    got = run(f"P.status('io.github.duketopceo.omaseal', {json.dumps(ctx)})")
    assert (got["kind"], got["on"], got["text"]) == ("dot", False, "Launcher")


def test_status_reports_a_failed_open():
    ctx = {"tabs": [], "tray": ["lukedaduke.fan"], "failed": "lukedaduke.fan"}
    got = run(f"P.status('lukedaduke.fan', {json.dumps(ctx)})")
    assert (got["kind"], got["on"], got["text"]) == ("pill", False, "No panel")


# ---------------------------------------------------------------- tile size

def test_tiles_are_the_compact_old_cell():
    old = run("P.BASE_CELL")
    assert old == {"w": 224, "h": 94}
    area = run("P.tileArea(688)")
    assert area <= 1.05 * old["w"] * old["h"]  # compact: no bigger than the old cell
    width = run("P.tileWidth(688)")
    assert width == 222
    assert run("P.TILE_H") == 96
    # Three columns plus two gaps fill the 720 px panel's 688 px content width.
    assert 3 * width + 2 * run("P.HUB_GAP") == 686


def test_tile_width_never_collapses():
    assert run("P.tileWidth(0)") == run("P.BASE_CELL.w")
    assert run("P.tileWidth(400)") >= 120  # min tile


# ---------------------------------------------------------------- slot fallback

def test_slot_info_fallback_survives_a_missing_manifest():
    info = run("P.slotInfo('io.github.duketopceo.missing', '', '/h')")
    assert info["name"] == "missing"
    assert info["image"] == "/h/.config/omarchy/plugins/io.github.duketopceo.missing/icon.png"
    assert info["glyph"] == run("P.GENERIC_GLYPH")
    # A broken manifest text takes the same path instead of throwing.
    assert run("P.slotInfo('a.b', '{not json', '/h')")["name"] == "b"


# ---------------------------------------------------------------- tabs glue

def test_visible_ids_tracks_optional_tabs():
    assert run("T.visibleIds({snapdex: false, dayflow: false})").count("screenshots") == 0
    assert run("T.visibleIds({snapdex: true, dayflow: true})")[-4:] == ["screenshots", "dayflow", "plugins", "settings"]
    assert run("T.visibleIds(null)[0]") == "home"


# ---------------------------------------------------------------- QML wiring

def test_plugins_tab_wires_the_hub():
    qml = (NOTCH / "PluginsTab.qml").read_text()
    assert "Plugins.hub(" in qml
    assert "Plugins.action(" in qml
    assert "Plugins.status(" in qml
    assert "Tabs.visibleIds(" in qml
    # R2: embedded tiles open the notch tab in place.
    assert "notch.openTab" in qml
    assert "openTabRequested" in qml
    # Launcher fallback stays the existing chain (notch.openPlugin runs it).
    assert "notch.openPlugin(" in qml
    # R6: Configure opens Settings through Plugins.configure().
    assert "Plugins.CONFIGURE" in qml
    assert "openConfigure" in qml
    # R9: name/icon still come from slotInfo's fallback.
    assert "Plugins.slotInfo(" in qml
