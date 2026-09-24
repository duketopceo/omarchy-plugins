from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "scripts" / "install.sh"
VALIDATE = ROOT / "scripts" / "validate-manifests.py"


def manifest(path: Path, plugin_id: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "manifest.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "id": plugin_id,
                "name": plugin_id,
                "version": "1.0.0",
                "author": "fixture",
                "kinds": ["bar-widget"],
                "entryPoints": {"barWidget": "Panel.qml"},
            }
        )
    )
    (path / "Panel.qml").write_text("// fixture\n")


def run_installer(destination: Path, backup_root: Path, mode: str = "--link") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            str(INSTALL),
            mode,
            "--dest",
            str(destination),
            "--backup-root",
            str(backup_root),
            "--no-rescan",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_legacy_backups_move_out_of_discovery_root(tmp_path: Path) -> None:
    destination = tmp_path / "plugins"
    backup_root = tmp_path / "state" / "backups"
    manifest(destination / "lukedaduke.fan.bak.123", "lukedaduke.fan")

    result = run_installer(destination, backup_root)

    assert result.returncode == 0, result.stderr
    assert not (destination / "lukedaduke.fan.bak.123").exists()
    assert (backup_root / "lukedaduke.fan.bak.123" / "manifest.json").is_file()
    assert (destination / "lukedaduke.fan" / "manifest.json").is_file()


def test_duplicate_non_backup_manifests_fail_without_moving_state(tmp_path: Path) -> None:
    destination = tmp_path / "plugins"
    backup_root = tmp_path / "state" / "backups"
    manifest(destination / "one", "lukedaduke.fan")
    manifest(destination / "two", "lukedaduke.fan")
    before = sorted(path.name for path in destination.iterdir())

    result = run_installer(destination, backup_root)

    assert result.returncode != 0
    assert "duplicate" in (result.stdout + result.stderr).lower()
    assert sorted(path.name for path in destination.iterdir()) == before
    assert not backup_root.exists()


def test_repeated_link_install_is_idempotent(tmp_path: Path) -> None:
    destination = tmp_path / "plugins"
    backup_root = tmp_path / "state" / "backups"

    first = run_installer(destination, backup_root)
    second = run_installer(destination, backup_root)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr
    assert "unchanged lukedaduke.fan" in second.stdout
    assert (destination / "lukedaduke.fan").is_symlink()


def test_copy_install_is_validated_and_excludes_generated_artifacts(tmp_path: Path) -> None:
    destination = tmp_path / "plugins"
    backup_root = tmp_path / "state" / "backups"

    result = run_installer(destination, backup_root, "--copy")

    assert result.returncode == 0, result.stderr
    assert not list(destination.rglob("__pycache__"))
    assert not list(destination.rglob("*.pyc"))
    assert (destination / "lukedaduke.fan" / "manifest.json").is_file()


def test_release_validation_rejects_symlinked_plugin_copy(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("validate_manifests", VALIDATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    release_root = tmp_path / "release"
    manifest(release_root / "demo", "demo")
    (release_root / "demo" / "asset").symlink_to(tmp_path / "asset")

    errors = module.validate_install_layout(release_root, release=True)

    assert any("symlink" in error.lower() for error in errors)


def test_release_validation_reports_a_plugin_directory_without_manifest(tmp_path: Path) -> None:
    spec = importlib.util.spec_from_file_location("validate_manifests", VALIDATE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    release_root = tmp_path / "release"
    (release_root / "missing").mkdir(parents=True)
    (release_root / "missing" / "Panel.qml").write_text("// fixture\n")

    errors = module.validate_install_layout(release_root, release=True)

    assert any("missing manifest" in error.lower() for error in errors)
