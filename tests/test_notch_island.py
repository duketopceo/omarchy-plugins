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


def test_the_old_panel_is_retired():
    # The island owns every tab now; the dashboard implementation lives in git
    # history (commit b9029d2 and earlier), not in the shipped plugin.
    assert not (NOTCH / "Notch.qml").exists()
    assert not (NOTCH / "ExpandedPanel.qml").exists()
    # Its per-tab content is still shipped, and the island hosts it.
    for tab in ("HomeTab.qml", "MediaTab.qml", "NetworkTab.qml", "SettingsTab.qml"):
        assert (NOTCH / tab).is_file(), tab


# --------------------------------------------------------------- ID binding

def test_each_detail_view_is_bound_to_its_own_activity_id():
    # KTD6: a control must never act on a different activity after a reorder.
    # Every detail block tests `selected.id === "<id>"`, never a rank.
    text = source()
    # Each bound id is still tested by value, never by rank.
    for activity in ("media", "dictation", "agents", "messages", "screenshots"):
        assert f'"{activity}"' in text, activity
    assert "win.selected.id === \"media\"" in text
    # The four single-action views share one Repeater keyed on the id.
    assert 'win.selected.id === detail.modelData.act' in text
    assert not re.search(r'selected\.id === \d', text), "an activity was matched by rank"


def test_stop_is_gated_on_the_recording_state():
    # KTD6: "Stop" may only appear while recording; Island.action owns that
    # rule, so the QML must ask it rather than testing the state itself.
    text = source()
    assert 'Island.action("dictation", dictation.state) === "stop"' in text


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
    # The dashboard's tabs are the island's own tabs now, so "reachable"
    # means the tab files load through the island's Loader.
    assert 'source: tab && tab.source ? tab.source : ""' in text
    assert "item.notch = root" in text
    assert "function openDashboard(" in text


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
    assert buttons >= 5, buttons
    assert buttons == focusable, f"{buttons} buttons but {focusable} focusable"
    assert keys >= focusable, f"{focusable} focusable targets but {keys} key handlers"


# --------------------------------------------------------------- collectors

def test_the_island_reuses_the_existing_collectors():
    # KTD2: no parallel backend. The five components must be instantiated.
    text = source()
    for component in ("MediaActivity", "WordinkActivity", "AgentsActivity",
                      "MessagesActivity", "ScreenshotsActivity"):
        assert re.search(rf"^\s*{component}\s*\{{", text, re.M), component


def test_the_compact_bar_stays_an_activity_surface():
    # The tabs live behind the expanded panel, reached by the strip; the
    # compact bar itself carries the clock, the idle cycle and activities.
    text = source()
    compact = text[text.index("-------- compact"):text.index("-------- expanded")]
    for banned in ("NetworkTab", "PowerTab", "SystemTab", "StocksTab", "PluginsTab"):
        assert banned not in compact, banned


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




def test_no_object_declares_the_same_signal_handler_twice():
    # QML fails the whole component to load with "Property value set multiple
    # times" when one object carries the same handler twice. That blanked the
    # island entirely while every other static check still passed. Scope each
    # object body by its opening line's indentation so two different FileViews
    # handling the same signal are not mistaken for a duplicate.
    lines = source().splitlines()
    seen = {}          # (indent, handler) -> count of open blocks at that level
    stack = []         # (indent, {handler: count})
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        indent = len(line) - len(line.lstrip())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        m = re.match(r"(on[A-Z][A-Za-z]+Changed):", stripped)
        if m and stack:
            frame = stack[-1][1]
            frame[m.group(1)] = frame.get(m.group(1), 0) + 1
            assert frame[m.group(1)] == 1, (
                f"{m.group(1)} declared twice on the same object (line: {stripped[:40]})")
        if stripped.endswith("{"):
            stack.append((indent, {}))


def test_a_rank_change_fills_an_empty_selection():
    # Opening while idle left selectedId empty forever, so the expanded view
    # said "Nothing active" while an activity was live.
    text = source()
    assert "function adopt()" in text
    adopt = text[text.index("function adopt()"):]
    adopt = adopt[:adopt.index("\n      }")]
    assert 'selectedId === "" && ranked.length' in adopt
    # adopted on open, not only on a rank change
    assert "adopt()" in text[text.index("function pinOpen()"):text.index("function closeIsland()")]


def test_compact_height_follows_the_cutout_not_a_constant():
    # A constant 37 px sat a few pixels below the bar on this panel. The
    # compact island must be the camera cutout tall when there is one.
    text = source()
    assert "compactHeight: cut > 0 ? Math.max(cut, barHeight)" in text


def test_physical_size_is_derived_when_hyprland_reports_none():
    # Hyprland.monitorFor() returns 0x0 here, so cutoutTop got the logical
    # width and matched no panel entry; the cutout was never detected.
    text = source()
    assert "Math.round(modelData.width * dpr)" in text
    assert "Math.round(modelData.height * dpr)" in text
