#!/usr/bin/env python3
"""Check owned plugin release artifacts before publication."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HOST_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users|tmp|private/tmp)/")
GENERATED_NAMES = {"__pycache__", "node_modules", "target", "build", "dist"}
TEXT_SUFFIXES = {".qml", ".py", ".sh", ".bash", ".js", ".mjs", ".json", ".md", ".yml", ".yaml", ".toml"}


def _load_sync_shared() -> Any:
    script = Path(__file__).resolve().with_name("sync-shared.py")
    spec = importlib.util.spec_from_file_location("sync_shared", script)
    if spec is None or spec.loader is None:
        raise ImportError(f"unable to load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_shared(plugin_root: Path, shared_root: Path, plugin_id: str | None) -> list[str]:
    """Every shared/consumers.txt plugin carries an exact copy of shared/."""
    sync = _load_sync_shared()
    repo = shared_root.parent
    errors: list[str] = []
    for consumer in sync.read_consumers(repo):
        if plugin_id and consumer != plugin_id:
            continue
        vendored = plugin_root / consumer / sync.VENDOR_DEST
        if not (plugin_root / consumer).is_dir():
            errors.append(f"{consumer}: shared consumer has no plugin directory")
            continue
        for problem in sync.compare_dir(repo, vendored):
            errors.append(f"{consumer}: shared library drift: {problem}")
    return errors


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"unable to read {path.name}: {exc}") from exc


def _tracked_files(root: Path) -> set[str] | None:
    git = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True,
        check=False,
    )
    if git.returncode != 0:
        return None
    return {item.decode("utf-8", errors="replace") for item in git.stdout.split(b"\0") if item}


def _scan_artifacts(plugin: Path, tracked_files: set[str] | None = None) -> list[str]:
    errors: list[str] = []
    generated = False
    host_path = False
    for path in plugin.rglob("*"):
        relative = str(path.relative_to(plugin))
        if tracked_files is not None and relative not in tracked_files and path.name != "manifest.json":
            continue
        if any(part in GENERATED_NAMES or part.endswith(".pyc") for part in path.parts):
            generated = True
        if path.is_symlink():
            errors.append(f"{plugin.name}: symlink is not allowed in a release")
            continue
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text()
        except (OSError, UnicodeDecodeError):
            continue
        if HOST_PATH_RE.search(text):
            host_path = True
    if generated:
        errors.append(f"{plugin.name}: generated artifact found")
    if host_path:
        errors.append(f"{plugin.name}: host-specific absolute path found")
    return errors


def _check_plugin(
    plugin: Path,
    catalog_entry: dict[str, Any] | None,
    ci_text: str,
    tracked_files: set[str] | None,
) -> list[str]:
    errors: list[str] = []
    manifest_path = plugin / "manifest.json"
    if not manifest_path.is_file():
        return [f"{plugin.name}: missing manifest.json"]
    try:
        manifest = _read_json(manifest_path)
    except ValueError as exc:
        return [f"{plugin.name}: {exc}"]
    if not isinstance(manifest, dict):
        return [f"{plugin.name}: manifest must be an object"]
    plugin_id = manifest.get("id")
    if plugin_id != plugin.name:
        errors.append(f"{plugin.name}: manifest id does not match directory")
    for key in ("schemaVersion", "id", "name", "version", "author", "kinds", "entryPoints"):
        if key not in manifest:
            errors.append(f"{plugin.name}: manifest missing {key}")
    if not (plugin / "LICENSE").is_file():
        errors.append(f"{plugin.name}: missing LICENSE")
    if not (plugin / "README.md").is_file():
        errors.append(f"{plugin.name}: missing README.md")
    entry_points = manifest.get("entryPoints")
    if isinstance(entry_points, dict):
        for kind, relative in entry_points.items():
            if not (plugin / str(relative)).is_file():
                errors.append(f"{plugin.name}: missing entry point {kind}")
    if catalog_entry is None:
        errors.append(f"{plugin.name}: missing catalog entry")
    else:
        if str(catalog_entry.get("version")) != str(manifest.get("version")):
            errors.append(f"{plugin.name}: catalog version mismatch")
        if not catalog_entry.get("repo"):
            errors.append(f"{plugin.name}: catalog repository is missing")
    architectures = manifest.get("architectures", manifest.get("architectureSupport"))
    if not architectures:
        if "ubuntu-latest" not in ci_text or "ubuntu-24.04-arm" not in ci_text:
            errors.append(f"{plugin.name}: no architecture evidence")
    elif not isinstance(architectures, list) or not architectures:
        errors.append(f"{plugin.name}: architecture evidence is empty")
    errors.extend(_scan_artifacts(plugin, tracked_files))
    return errors


def check_tree(
    plugin_root: Path,
    catalog_path: Path,
    ci_path: Path | None = None,
    plugin_id: str | None = None,
    tracked_files: set[str] | None = None,
    shared_root: Path | None = None,
) -> list[str]:
    try:
        catalog = _read_json(catalog_path)
    except ValueError as exc:
        return [str(exc)]
    if not isinstance(catalog, dict) or not isinstance(catalog.get("plugins"), list):
        return ["catalog must contain a plugins list"]
    catalog_by_id = {
        str(entry.get("id")): entry
        for entry in catalog["plugins"]
        if isinstance(entry, dict) and entry.get("id")
    }
    try:
        ci_text = ci_path.read_text() if ci_path and ci_path.is_file() else ""
    except OSError:
        ci_text = ""
    errors: list[str] = []
    for plugin in sorted(plugin_root.iterdir(), key=lambda item: item.name) if plugin_root.is_dir() else []:
        if not plugin.is_dir() or plugin.name.startswith(".") or ".bak." in plugin.name:
            continue
        if not (plugin / "manifest.json").is_file():
            continue
        if plugin_id and plugin.name != plugin_id:
            continue
        errors.extend(_check_plugin(plugin, catalog_by_id.get(plugin.name), ci_text, tracked_files))
    if plugin_id and not any(plugin.name == plugin_id for plugin in plugin_root.iterdir() if plugin.is_dir()):
        errors.append(f"plugin not found: {plugin_id}")
    if shared_root is not None:
        errors.extend(_check_shared(plugin_root, shared_root, plugin_id))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path, default=ROOT / "plugins")
    parser.add_argument("--catalog", type=Path, default=ROOT / "catalog.json")
    parser.add_argument("--ci", type=Path, default=ROOT / ".github/workflows/ci.yml")
    parser.add_argument("--shared", type=Path, default=ROOT / "shared")
    parser.add_argument("--plugin-id")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    errors = check_tree(
        args.plugin_root,
        args.catalog,
        args.ci,
        args.plugin_id,
        tracked_files=_tracked_files(args.plugin_root),
        shared_root=args.shared,
    )
    if args.format == "json":
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    elif errors:
        for error in errors:
            print(error, file=sys.stderr)
    else:
        print("ok: release readiness")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
