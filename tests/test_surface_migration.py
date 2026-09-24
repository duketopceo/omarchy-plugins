from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan-surface-migration.py"


def load_module():
    assert SCRIPT.exists(), f"surface migration planner is missing: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("plan_surface_migration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shell_config() -> dict:
    return {
        "bar": {
            "layout": {
                "left": [{"id": "lukekimball.active-window"}],
                "right": [
                    {"id": "io.github.duketopceo.dim"},
                    {"id": "io.github.tyrichards.tray", "widgets": []},
                ],
            }
        },
        "plugins": [{"id": "localdev.secrets"}],
    }


def desired_config() -> dict:
    return {
        "bar": {
            "layout": {
                "left": [{"id": "omarchy.active-window"}],
                "right": [
                    {"id": "hancore.voxtype-enhance"},
                    {"id": "io.github.tyrichards.tray", "widgets": []},
                ],
            }
        },
        "plugins": [{"id": "localdev.secrets"}],
    }


def test_planner_replaces_voice_and_active_window_without_deleting_data() -> None:
    module = load_module()
    plan = module.plan_migration(shell_config(), desired_config())

    assert plan["remove_bar_ids"] == ["io.github.duketopceo.dim", "lukekimball.active-window"]
    assert plan["add_bar_ids"] == ["hancore.voxtype-enhance", "omarchy.active-window"]
    assert plan["retained_bar_ids"] == ["io.github.tyrichards.tray"]
    assert plan["destructive_actions"] == []
    assert plan["requires_shell_backup"] is True


def test_planner_output_is_serializable_and_has_rollback_metadata() -> None:
    module = load_module()
    plan = module.plan_migration(shell_config(), desired_config())
    serialized = json.dumps(plan)

    assert "rollback" in plan
    assert "bar" in plan["rollback"].lower()
    assert str(ROOT) not in serialized
