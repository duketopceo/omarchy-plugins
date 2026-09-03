from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATE = ROOT / "scripts" / "validate-manifests.py"


def test_shipped_manifests_pass() -> None:
    result = subprocess.run([sys.executable, str(VALIDATE)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "ok:" in result.stdout


def test_id_must_match_folder(tmp_path: Path, monkeypatch) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_manifests", VALIDATE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    plugin = tmp_path / "wrong.id"
    plugin.mkdir()
    manifest = plugin / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "id": "other.id",
                "name": "X",
                "version": "1.0.0",
                "author": "t",
                "kinds": ["bar-widget"],
                "entryPoints": {"barWidget": "Panel.qml"},
            }
        )
    )
    (plugin / "Panel.qml").write_text("// stub\n")
    errors = mod.validate_one(manifest)
    assert any("does not match folder" in e for e in errors)


def test_missing_entry_points_fails(tmp_path: Path) -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location("validate_manifests", VALIDATE)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    plugin = tmp_path / "lukedaduke.demo"
    plugin.mkdir()
    manifest = plugin / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "id": "lukedaduke.demo",
                "name": "Demo",
                "version": "1.0.0",
                "author": "t",
                "kinds": ["bar-widget"],
            }
        )
    )
    errors = mod.validate_one(manifest)
    assert any("missing entryPoints" in e for e in errors)


def test_agents_panel_uses_own_id() -> None:
    panel = (ROOT / "plugins/lukedaduke.agents/Panel.qml").read_text()
    assert 'moduleName: "lukedaduke.agents"' in panel
    assert 'moduleName: "omarchy.agents"' not in panel
