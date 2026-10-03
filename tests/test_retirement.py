"""U9: connections, ticker and agents are retired in favour of tools already on the bar."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
RETIRED = {
    "lukedaduke.connections": ["omarchy.bluetooth", "omarchy.network"],
    "lukedaduke.ticker": ["mohamedmansour.finance"],
    "lukedaduke.agents": ["akitaonrails.ai-usagebar"],
}
STUB_FILES = {"manifest.json", "Stub.qml", "README.md", "LICENSE"}


def _bar_ids(config: dict) -> list[str]:
    layout = config.get("bar", {}).get("layout", {})
    return [e["id"] for entries in layout.values() for e in entries if isinstance(e, dict)]


def _load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("plugin", sorted(RETIRED))
def test_retired_plugin_is_a_notice_only_stub(plugin: str) -> None:
    root = ROOT / "plugins" / plugin
    assert {p.name for p in root.iterdir()} == STUB_FILES
    manifest = json.loads((root / "manifest.json").read_text())
    assert manifest["id"] == plugin
    assert manifest["entryPoints"] == {"barWidget": "Stub.qml"}
    assert manifest["kinds"] == ["bar-widget"]
    assert int(manifest["version"].split(".")[0]) >= 3
    stub = (root / "Stub.qml").read_text()
    for replacement in RETIRED[plugin]:
        assert replacement in stub
    for block in re.findall(r"Text \{[^}]*\}", stub):
        assert "Text.PlainText" in block
    assert "Process" not in stub and "execDetached" not in stub
    readme = (root / "README.md").read_text()
    assert "retired" in readme.lower()
    assert all(r in readme for r in RETIRED[plugin])


def test_catalog_and_machine_inventory_drop_retired_ids() -> None:
    catalog = json.loads((ROOT / "catalog.json").read_text())
    assert not {p["id"] for p in catalog["plugins"]} & set(RETIRED)
    inventory = json.loads((ROOT / "machine" / "plugins.json").read_text())
    assert not set(inventory["first_party_from_this_repo"]) & set(RETIRED)


def test_desired_layout_swaps_connections_for_first_party_radios() -> None:
    desired = json.loads((ROOT / "machine" / "bar-layout.json").read_text())
    ids = _bar_ids(desired)
    assert not set(ids) & set(RETIRED)
    right = [e["id"] for e in desired["bar"]["layout"]["right"]]
    i = right.index("omarchy.bluetooth")
    assert right[i + 1] == "omarchy.network"
    assert right[i - 1] == "omarchy.tailscale"  # same slot connections held
    # wisp is on the live bar; the desired layout must not silently remove it.
    assert "io.github.duketopceo.wisp" in ids


def test_planner_refuses_a_desired_layout_that_places_a_retired_plugin(tmp_path: Path) -> None:
    planner = _load("plan-surface-migration")
    current = {"bar": {"layout": {"right": [{"id": "lukedaduke.fan"}]}}}
    desired = {"bar": {"layout": {"right": [{"id": "lukedaduke.fan"}, {"id": "lukedaduke.ticker"}]}}}
    with pytest.raises(ValueError, match="lukedaduke.ticker"):
        planner.plan_migration(current, desired, retiring=set(RETIRED))


def test_planner_reports_retired_ids_it_removes() -> None:
    planner = _load("plan-surface-migration")
    current = {"bar": {"layout": {"right": [{"id": "omarchy.tailscale"}, {"id": "lukedaduke.connections"}]}}}
    desired = {"bar": {"layout": {"right": [{"id": "omarchy.tailscale"}, {"id": "omarchy.bluetooth"},
                                            {"id": "omarchy.network"}]}}}
    plan = planner.plan_migration(current, desired, retiring=set(RETIRED))
    assert plan["retired_bar_ids"] == ["lukedaduke.connections"]
    assert plan["add_bar_ids"] == ["omarchy.bluetooth", "omarchy.network"]


def test_planner_reads_the_retiring_list_from_the_scorecard() -> None:
    planner = _load("plan-surface-migration")
    assert planner.retiring_ids() == set(RETIRED)


@pytest.mark.parametrize("plugin", sorted(RETIRED))
def test_stub_module_name_matches_its_plugin_id(plugin: str) -> None:
    stub = (ROOT / "plugins" / plugin / "Stub.qml").read_text()
    assert f'moduleName: "{plugin}"' in stub
    assert "dimmed: true" in stub


def test_retiring_ids_raise_when_the_scorecard_is_unreadable(tmp_path: Path) -> None:
    planner = _load("plan-surface-migration")
    with pytest.raises(ValueError):
        planner.retiring_ids(tmp_path / "missing.md")
    bad = tmp_path / "SCORECARD.md"
    bad.write_text("# s\n\n```scorecard-config\n{not json\n```\n")
    with pytest.raises(ValueError):
        planner.retiring_ids(bad)


def test_desired_file_mirrors_live_plugin_lists() -> None:
    desired = json.loads((ROOT / "machine" / "bar-layout.json").read_text())
    assert "omarchy.lock" not in desired.get("disabledPlugins", [])
    assert "io.github.duketopceo.wisp" in [p["id"] for p in desired.get("plugins", [])]


def test_planner_cli_exits_2_on_retired_placement(tmp_path: Path) -> None:
    planner = _load("plan-surface-migration")
    cur = tmp_path / "c.json"
    des = tmp_path / "d.json"
    cur.write_text(json.dumps({"bar": {"layout": {"right": []}}}))
    des.write_text(json.dumps({"bar": {"layout": {"right": [{"id": "lukedaduke.agents"}]}}}))
    assert planner.main(["--current", str(cur), "--desired", str(des)]) == 2
