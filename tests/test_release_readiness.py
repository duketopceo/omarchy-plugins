from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-release-readiness.py"


def load_module():
    assert SCRIPT.exists(), f"release checker is missing: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("check_release_readiness", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_release_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    plugin_root = tmp_path / "plugins"
    plugin = plugin_root / "lukedaduke.demo"
    plugin.mkdir(parents=True)
    (plugin / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "id": "lukedaduke.demo",
                "name": "Demo",
                "version": "1.0.0",
                "author": "fixture",
                "kinds": ["bar-widget"],
                "entryPoints": {"barWidget": "Panel.qml"},
                "architectures": ["aarch64", "x86_64"],
            }
        )
    )
    (plugin / "Panel.qml").write_text("import QtQuick\n")
    (plugin / "README.md").write_text("# Demo\n")
    (plugin / "LICENSE").write_text("MIT\n")
    catalog = tmp_path / "catalog.json"
    catalog.write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "id": "lukedaduke.demo",
                        "version": "1.0.0",
                        "repo": "https://example.invalid/demo",
                    }
                ]
            }
        )
    )
    ci = tmp_path / "ci.yml"
    ci.write_text("matrix:\n  os: [ubuntu-latest, ubuntu-24.04-arm]\n")
    return plugin_root, catalog, ci


def test_valid_fixture_passes_release_gate(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    errors = module.check_tree(plugin_root, catalog, ci)
    assert errors == []


def test_missing_license_fails_release_gate(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    (plugin_root / "lukedaduke.demo" / "LICENSE").unlink()
    errors = module.check_tree(plugin_root, catalog, ci)
    assert any("LICENSE" in error for error in errors)


def test_catalog_version_mismatch_fails_release_gate(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    data = json.loads(catalog.read_text())
    data["plugins"][0]["version"] = "0.9.0"
    catalog.write_text(json.dumps(data))
    errors = module.check_tree(plugin_root, catalog, ci)
    assert any("version" in error.lower() for error in errors)


def test_generated_and_host_specific_artifacts_fail_release_gate(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    plugin = plugin_root / "lukedaduke.demo"
    (plugin / "__pycache__").mkdir()
    (plugin / "README.md").write_text("source at /home/example/private\n")
    errors = module.check_tree(plugin_root, catalog, ci)
    assert any("generated" in error.lower() for error in errors)
    assert any("host" in error.lower() for error in errors)


def test_publish_script_runs_release_gate_before_subtree_push() -> None:
    publish = (ROOT / "scripts" / "publish.sh").read_text()
    assert "check-release-readiness.py" in publish
    assert "git subtree split" in publish
