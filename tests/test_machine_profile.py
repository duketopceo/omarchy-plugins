from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MACHINE = ROOT / "machine"


def test_machine_index_describes_the_arm_asahi_host() -> None:
    index = (MACHINE / "INDEX.md").read_text()
    assert "Arch Linux ARM" in index
    assert "aarch64" in index
    assert "Asahi" in index
    assert "Dell Precision 5560" not in index
    assert "NVIDIA" not in index


def test_restore_playbook_has_no_stale_x86_assumptions() -> None:
    restore = (MACHINE / "RESTORE.md").read_text()
    for stale in ("Dell Precision", "NVIDIA vs Intel", "nvidia-open-dkms", "intel-media-driver"):
        assert stale not in restore


def test_bar_layout_is_sanitized_and_keeps_hosted_widgets() -> None:
    layout = json.loads((MACHINE / "bar-layout.json").read_text())
    serialized = json.dumps(layout)
    assert "lastSeen" not in serialized
    right = layout["bar"]["layout"]["right"]
    tray = next(item for item in right if item.get("id") == "io.github.tyrichards.tray")
    widget_ids = {widget["entry"]["id"] for widget in tray["widgets"]}
    assert widget_ids == {"jankeesvw.herdr", "lukedaduke.nexus"}
    assert "hancore.voxtype-enhance" in serialized
    assert "omarchy.active-window" in serialized
    assert "lukekimball.active-window" not in serialized
    assert "io.github.duketopceo.dim" not in serialized


def test_plugin_map_has_no_user_checkout_paths() -> None:
    plugin_map = json.loads((MACHINE / "plugins.json").read_text())
    serialized = json.dumps(plugin_map)
    assert "source_dir" not in serialized
    assert "Documents/github" not in serialized
    assert "io.github.duketopceo.dim" in serialized
    assert "io.github.duketopceo.dayflow" in serialized
