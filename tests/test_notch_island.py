"""Island.qml: Dynamic Island pill + ExpandedPanel tab dashboard morph."""
import json
import re
from pathlib import Path

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
ISLAND = NOTCH / "Island.qml"
MANIFEST = NOTCH / "manifest.json"
GEOM = NOTCH / "IslandGeom.js"


def source():
    return ISLAND.read_text()


def test_manifest_points_at_island_only():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["id"] == "io.github.duketopceo.notch"
    assert manifest["entryPoints"]["panel"] == "Island.qml"
    assert not (NOTCH / "Notch.qml").exists()
    assert 'source: "Notch.qml"' not in source()


def test_compact_uses_island_geom_not_cutout_fill():
    text = source()
    assert 'import "IslandGeom.js" as Geom' in text
    assert "Geom.COMPACT_H" in text
    assert "Geom.compactWidth(" in text
    assert "Math.max(cut, barHeight)" not in text
    assert GEOM.is_file()


def test_expand_hosts_expanded_panel_tabs():
    text = source()
    assert "ExpandedPanel" in text
    assert "currentTab" in text
    assert "Tabs.sizeFor" in text or "Tabs.maxHeight" in text
    assert "noteTabUse" in text
    assert (NOTCH / "ExpandedPanel.qml").is_file()


def test_hover_pin_escape_wiring():
    text = source()
    assert "HoverHandler" in text
    assert "pinned" in text
    assert "collapseNow" in text
    assert re.search(r'sequence:\s*"Escape"', text)
    assert 'WlrLayershell.namespace: "omarchy-notch-island"' in text


def test_keyboard_focus_only_when_pinned_open():
    text = source()
    assert "WlrKeyboardFocus.OnDemand" in text
    assert "WlrKeyboardFocus.None" in text


def test_fullscreen_step_aside_is_wired():
    text = source()
    assert 'import "Fullscreen.js" as FS' in text
    assert "shouldStepAside" in text
    assert "visible: !stepAside" in text
    assert (NOTCH / "Fullscreen.js").is_file()


def test_notifications_policy_is_opt_in():
    text = source()
    assert 'import "NotificationsPolicy.js" as NotifPol' in text
    assert "notificationsStatus" in text
    assert (NOTCH / "NotificationsPolicy.js").is_file()

