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


# --- shared library drift (U4) ---------------------------------------------

def make_shared(tmp_path: Path, consumers: list[str]) -> Path:
    shared = tmp_path / "shared"
    lib = shared / "py" / "_omplug"
    lib.mkdir(parents=True)
    (lib / "__init__.py").write_text('"""lib."""\n')
    (shared / "VERSION").write_text("0.1.0\n")
    (shared / "consumers.txt").write_text("".join(c + "\n" for c in consumers))
    return shared


def test_consumer_with_matching_copy_passes(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    shared = make_shared(tmp_path, ["lukedaduke.demo"])
    vendored = plugin_root / "lukedaduke.demo" / "bin" / "_omplug"
    vendored.mkdir(parents=True)
    (vendored / "__init__.py").write_text('"""lib."""\n')
    (vendored / "VERSION").write_text("0.1.0\n")
    assert module.check_tree(plugin_root, catalog, ci, shared_root=shared) == []


def test_consumer_with_drifted_copy_fails(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    shared = make_shared(tmp_path, ["lukedaduke.demo"])
    errors = module.check_tree(plugin_root, catalog, ci, shared_root=shared)
    assert any("shared" in error for error in errors)
    vendored = plugin_root / "lukedaduke.demo" / "bin" / "_omplug"
    vendored.mkdir(parents=True)
    (vendored / "__init__.py").write_text('"""lib!"""\n')
    (vendored / "VERSION").write_text("0.1.0\n")
    errors = module.check_tree(plugin_root, catalog, ci, shared_root=shared)
    assert any("__init__.py" in error for error in errors)


def test_non_consumer_is_not_checked_for_shared_copy(tmp_path: Path) -> None:
    module = load_module()
    plugin_root, catalog, ci = make_release_fixture(tmp_path)
    shared = make_shared(tmp_path, [])
    assert module.check_tree(plugin_root, catalog, ci, shared_root=shared) == []


# --- publish.sh deletion guard (R16) ---------------------------------------

import subprocess  # noqa: E402

PUBLISH = ROOT / "scripts" / "publish.sh"


def _git(repo: Path, *args: str) -> str:
    env = {
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.invalid",
        "GIT_CONFIG_NOSYSTEM": "1", "HOME": str(repo), "PATH": "/usr/bin:/bin",
    }
    out = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=env, check=True)
    return out.stdout.strip()


def _commit_tree(repo: Path, files: dict[str, str], msg: str) -> str:
    for path in list(repo.iterdir()):
        if path.name != ".git":
            subprocess.run(["rm", "-rf", str(path)], check=True)
    for rel, body in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", msg)
    return _git(repo, "rev-parse", "HEAD")


def _guard(repo: Path, split: str, remote: str, *flags: str) -> subprocess.CompletedProcess:
    script = f'source "{PUBLISH}"; cd "{repo}"; guard_deletions "$@"'
    return subprocess.run(
        ["bash", "-c", script, "guard", split, remote, *flags],
        capture_output=True, text=True,
    )


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    return repo


def test_publish_refuses_remote_only_files_without_allow_delete(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    remote = _commit_tree(repo, {"manifest.json": "{}", "SECURITY.md": "remote-only"}, "remote")
    split = _commit_tree(repo, {"manifest.json": "{}", "Panel.qml": "x"}, "split")
    res = _guard(repo, split, remote)
    assert res.returncode != 0
    assert "SECURITY.md" in res.stdout + res.stderr
    assert "--allow-delete" in res.stdout + res.stderr


def test_publish_allows_remote_only_files_with_allow_delete(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    remote = _commit_tree(repo, {"manifest.json": "{}", "SECURITY.md": "remote-only"}, "remote")
    split = _commit_tree(repo, {"manifest.json": "{}"}, "split")
    res = _guard(repo, split, remote, "--allow-delete")
    assert res.returncode == 0
    assert "SECURITY.md" in res.stdout + res.stderr


def test_publish_passes_when_split_covers_remote(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    remote = _commit_tree(repo, {"manifest.json": "{}"}, "remote")
    split = _commit_tree(repo, {"manifest.json": "{\"v\":2}", "Panel.qml": "x"}, "split")
    assert _guard(repo, split, remote).returncode == 0
    # Brand-new remote with no main branch: nothing can be deleted.
    assert _guard(repo, split, "").returncode == 0


def test_publish_sourcing_does_not_publish() -> None:
    res = subprocess.run(["bash", "-c", f'source "{PUBLISH}"; echo sourced'], capture_output=True, text=True)
    assert res.returncode == 0 and res.stdout.strip() == "sourced"
    assert "== " not in res.stdout


def test_publish_never_force_pushes() -> None:
    pushes = [line for line in PUBLISH.read_text().splitlines() if "git push" in line]
    assert pushes
    for line in pushes:
        assert "--force" not in line and " -f" not in line
        assert ' "+' not in line and " +" not in line
