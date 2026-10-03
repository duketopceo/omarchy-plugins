from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apply-surface-migration.py"


def load_module():
    assert SCRIPT.exists(), f"surface migration applier is missing: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("apply_surface_migration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write_shell(path: Path, active_id: str = "lukekimball.active-window") -> None:
    path.write_text(
        json.dumps(
            {
                "version": 1,
                "bar": {"layout": {"left": [{"id": active_id}], "right": []}},
                "idle": {"lock": 600},
                "custom_runtime_state": "preserve-me",
            }
        )
    )


def write_desired(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "bar": {
                    "layout": {
                        "left": [{"id": "omarchy.active-window"}],
                        "right": [{"id": "hancore.voxtype-enhance"}],
                    }
                },
                "disabledPlugins": ["io.github.duketopceo.dim"],
            }
        )
    )


def test_apply_migration_backs_up_and_preserves_unrelated_state(tmp_path: Path) -> None:
    module = load_module()
    current = tmp_path / "shell.json"
    desired = tmp_path / "desired.json"
    backup_root = tmp_path / "backups"
    write_shell(current)
    write_desired(desired)
    rescans: list[str] = []

    result = module.apply_migration(
        current_path=current,
        desired_path=desired,
        backup_root=backup_root,
        rescan=lambda: rescans.append("rescan"),
    )

    updated = json.loads(current.read_text())
    assert updated["custom_runtime_state"] == "preserve-me"
    assert updated["bar"]["layout"]["left"] == [{"id": "omarchy.active-window"}]
    assert result["backup_path"].is_dir()
    assert rescans == ["rescan"]


def test_apply_migration_restores_backup_when_rescan_fails(tmp_path: Path) -> None:
    module = load_module()
    current = tmp_path / "shell.json"
    desired = tmp_path / "desired.json"
    backup_root = tmp_path / "backups"
    write_shell(current)
    write_desired(desired)
    original = current.read_bytes()

    def fail_rescan() -> None:
        raise RuntimeError("rescan failed")

    try:
        module.apply_migration(
            current_path=current,
            desired_path=desired,
            backup_root=backup_root,
            rescan=fail_rescan,
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected rescan failure")

    assert current.read_bytes() == original


def test_rollback_restores_the_saved_shell_snapshot(tmp_path: Path) -> None:
    module = load_module()
    current = tmp_path / "shell.json"
    desired = tmp_path / "desired.json"
    backup_root = tmp_path / "backups"
    write_shell(current)
    write_desired(desired)
    result = module.apply_migration(
        current_path=current,
        desired_path=desired,
        backup_root=backup_root,
        rescan=lambda: None,
    )

    module.rollback_migration(
        current_path=current,
        backup_path=result["backup_path"],
        rescan=lambda: None,
    )

    assert json.loads(current.read_text())["bar"]["layout"]["left"] == [
        {"id": "lukekimball.active-window"}
    ]


def test_apply_keeps_inline_settings_of_retained_entries(tmp_path: Path) -> None:
    module = load_module()
    current = tmp_path / "shell.json"
    desired = tmp_path / "desired.json"
    current.write_text(json.dumps({
        "bar": {"layout": {"right": [
            {"id": "io.github.tyrichards.tray", "order": ["a", "b"], "widgets": {"x": 1}},
            {"id": "lukedaduke.connections"},
            {"id": "io.github.duketopceo.bumblebee", "lastSeenExposures": ["e1"]},
        ]}},
        "plugins": [{"id": "lukedaduke.standby", "enabled": True, "location": "Austin"}],
    }))
    desired.write_text(json.dumps({
        "bar": {"layout": {"right": [
            {"id": "io.github.tyrichards.tray"},
            {"id": "omarchy.bluetooth"}, {"id": "omarchy.network"},
            {"id": "io.github.duketopceo.bumblebee"},
        ]}},
        "plugins": [{"id": "lukedaduke.standby", "enabled": True}],
    }))
    module.apply_migration(current_path=current, desired_path=desired,
                           backup_root=tmp_path / "backups", rescan=lambda: None)
    out = json.loads(current.read_text())
    right = out["bar"]["layout"]["right"]
    assert [e["id"] for e in right] == ["io.github.tyrichards.tray", "omarchy.bluetooth",
                                        "omarchy.network", "io.github.duketopceo.bumblebee"]
    assert right[0]["order"] == ["a", "b"] and right[0]["widgets"] == {"x": 1}
    assert right[3]["lastSeenExposures"] == ["e1"]
    assert out["plugins"][0]["location"] == "Austin"


def test_apply_refuses_to_place_a_retired_plugin(tmp_path: Path) -> None:
    module = load_module()
    current = tmp_path / "shell.json"
    desired = tmp_path / "desired.json"
    current.write_text(json.dumps({"bar": {"layout": {"right": []}}}))
    desired.write_text(json.dumps({"bar": {"layout": {"right": [{"id": "lukedaduke.ticker"}]}}}))
    before = current.read_bytes()
    try:
        module.apply_migration(current_path=current, desired_path=desired,
                               backup_root=tmp_path / "backups", rescan=lambda: None)
    except RuntimeError as exc:
        assert "lukedaduke.ticker" in str(exc)
    else:
        raise AssertionError("apply placed a retired plugin")
    assert current.read_bytes() == before


def _apply(module, tmp_path: Path, current: dict, desired: dict) -> dict:
    cur = tmp_path / "shell.json"
    des = tmp_path / "desired.json"
    cur.write_text(json.dumps(current))
    des.write_text(json.dumps(desired))
    module.apply_migration(current_path=cur, desired_path=des,
                           backup_root=tmp_path / "backups", rescan=lambda: None)
    return json.loads(cur.read_text())


def test_live_inline_settings_win_over_the_snapshot(tmp_path: Path) -> None:
    module = load_module()
    out = _apply(module, tmp_path,
                 {"bar": {"layout": {"right": [{"id": "io.github.tyrichards.tray", "order": ["new"]}]}}},
                 {"bar": {"layout": {"right": [{"id": "io.github.tyrichards.tray", "order": ["old"],
                                                "widgets": ["w"]}]}}})
    entry = out["bar"]["layout"]["right"][0]
    assert entry["order"] == ["new"]          # live wins
    assert entry["widgets"] == ["w"]          # snapshot fills a missing key


def test_apply_keeps_the_live_disabled_plugins_list(tmp_path: Path) -> None:
    module = load_module()
    out = _apply(module, tmp_path,
                 {"bar": {"layout": {"right": []}}, "disabledPlugins": ["omarchy.clock"]},
                 {"bar": {"layout": {"right": []}}, "disabledPlugins": ["omarchy.lock", "omarchy.clock"]})
    assert out["disabledPlugins"] == ["omarchy.clock"]


def test_apply_never_drops_a_live_plugins_entry(tmp_path: Path) -> None:
    module = load_module()
    out = _apply(module, tmp_path,
                 {"bar": {"layout": {"right": []}}, "plugins": [{"id": "a"}, {"id": "wisp", "x": 1}]},
                 {"bar": {"layout": {"right": []}}, "plugins": [{"id": "a"}]})
    assert [p["id"] for p in out["plugins"]] == ["a", "wisp"]
    assert out["plugins"][1]["x"] == 1


def test_apply_fails_closed_without_a_readable_retiring_list(tmp_path: Path, monkeypatch) -> None:
    module = load_module()
    def broken():
        raise RuntimeError("docs/SCORECARD.md has no readable retiring list")
    monkeypatch.setattr(module, "_retiring_ids", broken)
    cur = tmp_path / "shell.json"
    cur.write_text(json.dumps({"bar": {"layout": {"right": []}}}))
    des = tmp_path / "desired.json"
    des.write_text(json.dumps({"bar": {"layout": {"right": [{"id": "x"}]}}}))
    before = cur.read_bytes()
    try:
        module.apply_migration(current_path=cur, desired_path=des,
                               backup_root=tmp_path / "backups", rescan=lambda: None)
    except RuntimeError:
        pass
    else:
        raise AssertionError("apply ran without a retiring list")
    assert cur.read_bytes() == before
    assert not (tmp_path / "backups").exists()
