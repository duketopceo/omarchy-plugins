#!/usr/bin/env python3
"""Validate Omarchy plugin manifests and release/install layouts."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REQUIRED = ("schemaVersion", "id", "name", "version", "author", "kinds", "entryPoints")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"
HOST_PATH_RE = re.compile(r"(?<![A-Za-z0-9_])/(?:home|Users|tmp|private/tmp)/")


def validate_one(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"{path}: invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return [f"{path}: manifest must be an object"]
    for key in REQUIRED:
        if key not in data:
            errors.append(f"{path}: missing {key}")
    folder_id = path.parent.name
    plugin_id = data.get("id")
    if plugin_id != folder_id:
        errors.append(f"{path}: id {plugin_id!r} does not match folder {folder_id!r}")
    entry = data.get("entryPoints")
    if isinstance(entry, dict):
        for kind, rel in entry.items():
            target = path.parent / str(rel)
            if not target.is_file():
                errors.append(f"{path}: entryPoints.{kind} missing file {rel}")
    elif "entryPoints" in data:
        errors.append(f"{path}: entryPoints must be an object")
    kinds = data.get("kinds")
    if kinds is not None and not isinstance(kinds, list):
        errors.append(f"{path}: kinds must be a list")
    return errors


def all_manifests() -> list[Path]:
    if not PLUGINS.is_dir():
        return []
    return sorted(PLUGINS.glob("*/manifest.json"))


def _read_manifest(path: Path) -> tuple[dict | None, str | None]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "manifest must be an object"
    return value, None


def _contains_generated_artifact(path: Path) -> bool:
    generated_names = {"__pycache__", "node_modules", "target", "build", "dist"}
    return any(part in generated_names or part.endswith(".pyc") for part in path.parts)


def _release_files(path: Path):
    for item in path.rglob("*"):
        if item.is_file() and not item.is_symlink():
            try:
                if item.stat().st_size <= 1024 * 1024:
                    yield item
            except OSError:
                continue


def validate_install_layout(
    root: Path,
    *,
    release: bool = False,
    allow_symlink: bool = False,
    ignore_legacy_backups: bool = False,
    only: set[str] | None = None,
) -> list[str]:
    """Validate direct plugin directories under an install root.

    ``only`` limits release-copy checks to the named directories, so a copy
    install is not failed by third-party plugins sharing the discovery root.
    Manifest and duplicate-id checks still cover every directory.
    """
    if not root.is_dir():
        return [f"install root is unavailable: {root.name or 'root'}"]
    errors: list[str] = []
    ids: dict[str, list[str]] = {}
    for directory in sorted(root.iterdir(), key=lambda item: item.name):
        if not directory.is_dir() or directory.name.startswith("."):
            continue
        if ignore_legacy_backups and ".bak." in directory.name:
            continue
        manifest_path = directory / "manifest.json"
        if not manifest_path.is_file():
            looks_like_plugin = any(
                item.is_file() and item.suffix in {".qml", ".py", ".sh"}
                for item in directory.iterdir()
            )
            if looks_like_plugin:
                errors.append(f"{directory.name}: missing manifest.json")
            continue
        manifest, read_error = _read_manifest(manifest_path)
        if read_error is not None or manifest is None:
            errors.append(f"{directory.name}: invalid manifest ({read_error})")
            continue
        plugin_id = manifest.get("id")
        if not isinstance(plugin_id, str) or not plugin_id:
            errors.append(f"{directory.name}: manifest has no string id")
            continue
        ids.setdefault(plugin_id, []).append(directory.name)
        if not allow_symlink and directory.is_symlink():
            errors.append(f"{directory.name}: symlinked plugin directory is not allowed")
        if release and (only is None or directory.name in only):
            if any(item.is_symlink() for item in directory.rglob("*")):
                errors.append(f"{directory.name}: release copy contains a symlink")
            if any(_contains_generated_artifact(item) for item in directory.rglob("*")):
                errors.append(f"{directory.name}: release copy contains generated artifacts")
            for file_path in _release_files(directory):
                try:
                    text = file_path.read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                if HOST_PATH_RE.search(text):
                    errors.append(f"{directory.name}: release copy contains a host-absolute path")
                    break
    for plugin_id, names in sorted(ids.items()):
        if len(names) > 1:
            errors.append(f"duplicate manifest id {plugin_id!r}: {', '.join(names)}")
    return errors


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--install-root", type=Path, help="validate an install root instead of source plugins")
    parser.add_argument("--release", action="store_true", help="apply release-copy checks")
    parser.add_argument("--allow-symlink", action="store_true", help="allow linked development directories")
    parser.add_argument("--ignore-legacy-backups", action="store_true", help="ignore *.bak.* directories during preflight")
    parser.add_argument("--only", action="append", metavar="DIR", help="limit release checks to this plugin directory (repeatable)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.install_root is not None:
        errors = validate_install_layout(
            args.install_root,
            release=args.release,
            allow_symlink=args.allow_symlink or not args.release,
            ignore_legacy_backups=args.ignore_legacy_backups,
            only=set(args.only) if args.only else None,
        )
        if errors:
            for line in errors:
                print(line, file=sys.stderr)
            return 1
        print(f"ok: install layout {args.install_root.name or 'root'}")
        return 0
    manifests = all_manifests()
    if not manifests:
        print("no manifests found", file=sys.stderr)
        return 1
    errors: list[str] = []
    for path in manifests:
        errors.extend(validate_one(path))
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        return 1
    print(f"ok: {len(manifests)} manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
