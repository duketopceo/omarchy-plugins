"""Island.qml: Dynamic Island look (prototype geometry) + activity expand.

Notch.qml is gone. Tabbed dashboard ports next; these tests lock the pill look
and hover/pin expand wiring.
"""
import json
import re
from pathlib import Path

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
ISLAND = NOTCH / "Island.qml"
MANIFEST = NOTCH / "manifest.json"
MOTION = NOTCH / "Motion.js"


def source():
    return ISLAND.read_text()


def test_manifest_keeps_the_installed_id_and_points_at_the_island():
    manifest = json.loads(MANIFEST.read_text())
    assert manifest["id"] == "io.github.duketopceo.notch"
    assert manifest["entryPoints"]["panel"] == "Island.qml"
    assert (NOTCH / manifest["entryPoints"]["panel"]).is_file()


def test_notch_qml_is_removed():
    assert not (NOTCH / "Notch.qml").exists()
    assert 'source: "Notch.qml"' not in source()


def test_dynamic_island_prototype_geometry():
    text = source()
    assert "compactHeight: 37" in text
    assert "expandedWidth: 374" in text
    assert "expandedHeight: 180" in text
    assert 'WlrLayershell.namespace: "omarchy-notch-island"' in text
    # Must not hug the cutout (that is the notch look).
    assert "Math.max(cut, barHeight)" not in text


def test_island_motion_tokens_match_prototype():
    m = MOTION.read_text()
    assert "ISLAND_RADIUS = 46" in m
    assert "ISLAND_OPEN_MS = 390" in m


def test_hover_opens_and_leave_collapses_unless_pinned():
    text = source()
    assert "HoverHandler" in text
    assert "pinned" in text
    assert "closeIsland" in text
    assert re.search(r'sequence:\s*"Escape"', text)


def test_keyboard_focus_only_when_expanded():
    text = source()
    assert "WlrKeyboardFocus.OnDemand" in text
    assert "WlrKeyboardFocus.None" in text
