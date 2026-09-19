"""Regression tests for plugins/lukedaduke.connections.

The plugin is pure QML that embeds the stock Omarchy panels, so there is no
runnable helper code to unit-test. These tests pin the source-level contract
that the JEV review findings were about: dimmed bindings must read the real
state sources (not dead `"x" in item` guards), the dead anchorItem/hostWidget
injection must stay gone, the loaders must sit inside their visible buttons
for popup anchoring, and the README must warn about stock-widget IPC dupes.

When the stock panels are installed (this is an Omarchy machine), also check
the upstream symbols the widget calls on the loaded items still exist.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugins" / "lukedaduke.connections"
QML = PLUGIN / "BarWidget.qml"
README = PLUGIN / "README.md"

STOCK = Path("/usr/share/omarchy/shell")
STOCK_BT = STOCK / "plugins/panels/bluetooth/Panel.qml"
STOCK_NET = STOCK / "plugins/panels/network/Panel.qml"
STOCK_PANEL_BASE = STOCK / "Ui/Panel.qml"
STOCK_PRESENT = STOCK_BT.exists() and STOCK_NET.exists() and STOCK_PANEL_BASE.exists()


@pytest.fixture(scope="module")
def qml() -> str:
    return QML.read_text()


def test_barwidget_exists() -> None:
    assert QML.is_file()


def test_bluetooth_dimmed_binds_real_adapter_state(qml: str) -> None:
    # Real source: Bluetooth.defaultAdapter (.enabled), as the stock panel's
    # `adapter` property reads. The old `"bluetoothEnabled" in item` guard was
    # dead code — no stock panel exposes that root property.
    assert "import Quickshell.Bluetooth" in qml
    assert "Bluetooth.defaultAdapter" in qml
    assert "bluetoothEnabled" not in qml


def test_wifi_dimmed_binds_real_networking_state(qml: str) -> None:
    # Real source: Networking.wifiEnabled on the Quickshell.Networking
    # singleton. The old `"wifiEnabled" in item` guard was dead code.
    assert "import Quickshell.Networking" in qml
    assert "Networking.wifiEnabled" in qml
    assert '"wifiEnabled" in' not in qml


def test_no_dead_anchor_injection(qml: str) -> None:
    # Panel declares neither anchorItem nor hostWidget; injecting them no-ops
    # and masked the real anchoring fix (loaders filled to the bar buttons).
    assert "anchorItem" not in qml
    assert "hostWidget" not in qml


def test_loaders_fill_their_bar_buttons(qml: str) -> None:
    # Popup anchoring: each Loader must fill its visible BarIconButton so the
    # embedded panel's internal anchor button lands under the right icon.
    loaders = re.findall(
        r"Loader\s*\{\s*id:\s*(btLoader|wifiLoader)\s*anchors\.fill:\s*parent", qml
    )
    assert sorted(loaders) == ["btLoader", "wifiLoader"]


def test_loaders_warn_on_error(qml: str) -> None:
    assert qml.count("Loader.Error") == 2
    assert "console.warn" in qml


def test_panel_sources_are_stock_paths(qml: str) -> None:
    assert "panels/bluetooth/Panel.qml" in qml
    assert "panels/network/Panel.qml" in qml


def test_readme_warns_about_stock_widget_ipc_dupes() -> None:
    readme = README.read_text()
    assert "omarchy.bluetooth" in readme
    assert "omarchy.network" in readme
    assert "disable" in readme.lower() or "remove" in readme.lower()


@pytest.mark.skipif(not STOCK_PRESENT, reason="stock Omarchy panels not installed")
def test_stock_panels_still_expose_widget_contract() -> None:
    bt = STOCK_BT.read_text()
    net = STOCK_NET.read_text()
    base = STOCK_PANEL_BASE.read_text()
    # Symbols BarWidget.qml dereferences on the loaded items.
    assert "adapter" in bt and "Bluetooth.defaultAdapter" in bt
    assert "function toggleBluetooth" in bt
    assert "function toggleNetwork" in net
    assert "property string icon" in bt and "property string icon" in net
    # toggle() comes from the shared Panel base.
    assert "function toggle()" in base
    # Both panels anchor their popups to an internal button filling the
    # loaded item — the reason the loaders fill the visible bar buttons.
    assert "anchorItem: button" in bt
    assert "anchorItem: button" in net
