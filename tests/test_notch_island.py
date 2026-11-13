"""Island.qml wiring: manifest entry, ID-bound controls, and honest empty states.

The activity selection itself is covered by test_island_activity.py; these
tests read the QML source to assert the wiring that file cannot see — that a
control is bound to its own activity id, that externally sourced text stays
plain, and that the dashboard route survives. Source assertions are weak
evidence on their own, so each one names the failure it would catch.
"""
import json
import re
from pathlib import Path

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
ISLAND = NOTCH / "Island.qml"
MANIFEST = NOTCH / "manifest.json"


def source():
    return ISLAND.read_text()


# --------------------------------------------------------------- manifest

def test_manifest_keeps_the_installed_id_and_points_at_the_island():
    # KTD1: the id is the configuration contract; changing it would strand
    # every saved opt-in setting.
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["id"] == "io.github.duketopceo.notch"
    assert manifest["entryPoints"]["panel"] == "Island.qml"
    assert (NOTCH / manifest["entryPoints"]["panel"]).is_file()


def test_the_old_panel_stays_in_source_for_rollback():
    # KTD1/R3: the dashboard implementation must remain recoverable.
    assert (NOTCH / "Notch.qml").is_file()
    assert (NOTCH / "ExpandedPanel.qml").is_file()


# --------------------------------------------------------------- ID binding

def test_each_detail_view_is_bound_to_its_own_activity_id():
    # KTD6: a control must never act on a different activity after a reorder.
    # Every detail block tests `selected.id === "<id>"`, never a rank.
    text = source()
    for activity in ("media", "dictation", "agents", "messages", "screenshots"):
        assert f'win.selected.id === "{activity}"' in text, activity
    assert not re.search(r'selected\.id === \d', text), "an activity was matched by rank"


def test_stop_is_gated_on_the_recording_state():
    # KTD6: "Stop" may only appear while recording; Island.action owns that
    # rule, so the QML must ask it rather than testing the state itself.
    text = source()
    assert 'Island.action("dictation", dictation.state)' in text
    assert 'visible: act === "stop"' in text


def test_a_finished_activity_leaves_a_neutral_state():
    # KTD6: the expanded view must not fall through to another activity.
    text = source()
    assert "Island.selected(ranked, selectedId) === null" in text
    assert 'qsTr("Nothing active")' in text


# --------------------------------------------------------------- safety

def test_externally_sourced_text_is_plain():
    # KTD7: message and screenshot text comes from outside the app.
    text = source()
    plain = text.count("textFormat: Text.PlainText")
    total = len(re.findall(r"Text\s*\{", text))
    # every Text block in this file sets PlainText; a single missing one is
    # the markup-injection hole this test exists to catch
    assert plain >= total, f"{total} Text blocks but only {plain} set PlainText"


def test_keyboard_dismissal_and_focus_are_wired():
    # R5: Escape dismisses; focus is only granted once open, so hovering to
    # expand never steals the keyboard.
    text = source()
    assert re.search(r'sequence:\s*"Escape"', text)
    assert re.search(r"keyboardFocus:\s*win\.expanded\s*\?\s*WlrKeyboardFocus\.OnDemand"
                     r"\s*:\s*WlrKeyboardFocus\.None", text)
    # Hover expands the island (owner-directed), so a HoverHandler is expected;
    # what must not happen is the hover path granting keyboard focus.
    assert "HoverHandler" in text
    focus_line = re.search(r"keyboardFocus:.*", text).group(0)
    assert "hover" not in focus_line.lower()


def test_reduced_motion_snaps_the_shape():
    # R4: animations are gated on the reduce-motion setting.
    text = source()
    assert text.count("enabled: !root.reduceMotion") >= 3


def test_the_dashboard_route_loads_the_old_panel():
    # R6/KTD8: the old surface must actually open. The plugin has one entry
    # point, so there is no separate panel to summon; Notch.qml is loaded here.
    text = source()
    assert "function openDashboard(" in text
    assert 'source: "Notch.qml"' in text
    assert "active: root.dashboardOpen" in text
    assert 'qsTr("Open the dashboard")' in text


def test_the_dashboard_can_hand_control_back():
    # The island hides while the dashboard is open, so if nothing clears that
    # flag the primary surface stays gone for the session. Notch.qml's own
    # Escape/outside-click ends in collapseRequested.
    text = source()
    assert "function onCollapseRequested() { root.dashboardOpen = false }" in text


def test_activity_targets_are_focusable_and_activate_from_the_keyboard():
    # R5: a focusable target that only answers the pointer is inert for
    # keyboard users, so count key handlers as well as focus flags.
    text = source()
    buttons = text.count("Accessible.role: Accessible.Button")
    focusable = text.count("activeFocusOnTab: true")
    keys = text.count("Keys.onPressed")
    assert buttons >= 6, buttons
    assert buttons == focusable, f"{buttons} buttons but {focusable} focusable"
    assert keys >= focusable, f"{focusable} focusable targets but {keys} key handlers"


# --------------------------------------------------------------- collectors

def test_the_island_reuses_the_existing_collectors():
    # KTD2: no parallel backend. The five components must be instantiated.
    text = source()
    for component in ("MediaActivity", "WordinkActivity", "AgentsActivity",
                      "MessagesActivity", "ScreenshotsActivity"):
        assert re.search(rf"^\s*{component}\s*\{{", text, re.M), component


def test_the_island_instantiates_no_removed_tab_content():
    # R3: no network, power, system, stocks, or plugin-management *tabs*.
    # The ambient idle cycle (weather, watchlist) is deliberately kept: it is
    # what the compact notch showed, and it is not a tab.
    text = source()
    for banned in ("NetworkTab", "PowerTab", "SystemTab", "StocksTab",
                   "PluginsTab", "NetworkState"):
        assert banned not in text, banned


def test_the_ambient_idle_cycle_is_present():
    # The owner asked for weather and the watchlist back beside the clock;
    # without them the compact island looks empty when nothing is happening.
    text = source()
    assert "WatchlistSlide" in text
    assert "root.weather" in text and "root.quotes" in text
    assert "Model.idleSlot" in text


def test_compact_ears_use_the_real_ear_math():
    # A hardcoded ear box gave 46 px on this panel, narrower than the time
    # string, so the compact island rendered as an empty pill.
    text = source()
    assert "Model.earWidthFor(" in text
    assert "Model.earWidthFit(" in text
    assert "Model.maxEarWidth(" in text


def test_the_root_exposes_the_shell_summon_entry_point():
    # The shell calls open() on a panel's root item when it summons the
    # plugin. Without it, summon prints ok and nothing appears.
    text = source()
    assert re.search(r"^  function open\(\)", text, re.M)
    assert re.search(r"^  function close\(\)", text, re.M)
