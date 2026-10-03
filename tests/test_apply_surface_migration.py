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
