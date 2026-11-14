"""Island.qml is the only panel entry: compact ears + hover-morph dashboard.

These tests read the QML source for wiring that node cannot see — hover leave,
ExpandedPanel host, and that Notch.qml is gone so a second surface cannot load.
"""
import json
import re
from pathlib import Path

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
ISLAND = NOTCH / "Island.qml"
MANIFEST = NOTCH / "manifest.json"


def source():
    return ISLAND.read_text()


def test_manifest_keeps_the_installed_id_and_points_at_the_island():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["id"] == "io.github.duketopceo.notch"
    assert manifest["entryPoints"]["panel"] == "Island.qml"
    assert (NOTCH / manifest["entryPoints"]["panel"]).is_file()


def test_notch_qml_is_removed_island_is_the_only_surface():
    assert not (NOTCH / "Notch.qml").exists()
    assert ISLAND.is_file()
    assert (NOTCH / "ExpandedPanel.qml").is_file()
    for tab in ("HomeTab.qml", "MediaTab.qml", "NetworkTab.qml", "SettingsTab.qml"):
        assert (NOTCH / tab).is_file(), tab


def test_hover_opens_and_leave_collapses_unless_pinned():
    text = source()
    assert "HoverHandler" in text
    assert 'win.xevent(hovered ? "enter" : "leave")' in text
    assert "pinned" in text
    assert "collapseNow" in text
    assert re.search(r'sequence:\s*"Escape"', text)


def test_expanded_hosts_the_tabbed_dashboard():
    text = source()
    assert "ExpandedPanel" in text
    assert "currentTab" in text
    assert "Tabs.sizeFor" in text or "Tabs.maxHeight" in text


def test_compact_is_island_pill_not_square_top_notch():
    text = source()
    assert 'WlrLayershell.namespace: "omarchy-notch-island"' in text
    assert "cornerR" in text
    assert "pillR" in text
    # Retired: flush square-top notch silhouette.
    assert "topLeftRadius: 0" not in text


def test_externally_sourced_idle_text_stays_plain():
    text = source()
    assert "textFormat: Text.PlainText" in text


def test_keyboard_focus_only_when_pinned_open():
    text = source()
    assert "WlrKeyboardFocus.OnDemand" in text
    assert "WlrKeyboardFocus.None" in text
