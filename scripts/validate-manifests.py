#!/usr/bin/env python3
"""Validate Omarchy plugin manifests in plugins/."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REQUIRED = ("schemaVersion", "id", "name", "version", "author", "kinds", "entryPoints")
ROOT = Path(__file__).resolve().parents[1]
PLUGINS = ROOT / "plugins"


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


def main() -> int:
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
