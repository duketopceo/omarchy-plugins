#!/usr/bin/env python3
"""Apply or roll back the sanitized bar/plugin surface migration safely."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CURRENT = Path.home() / ".config/omarchy/shell.json"
DEFAULT_DESIRED = ROOT / "machine/bar-layout.json"
DEFAULT_BACKUP_ROOT = Path(
    os.environ.get(
        "OMARCHY_MIGRATION_BACKUP_ROOT",
        Path(os.environ.get("XDG_STATE_HOME", Path.home() / ".local/state"))
        / "omarchy-plugins"
        / "migrations",
    )
)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"unable to read {path.name}: {exc}") from exc
    if not isinstance(value, dict):
        raise RuntimeError(f"{path.name} must contain a JSON object")
    return value


def _direct_ids(config: Mapping[str, Any]) -> set[str]:
    bar = config.get("bar")
    layout = bar.get("layout", {}) if isinstance(bar, Mapping) else {}
    ids: set[str] = set()
    if isinstance(layout, Mapping):
        for entries in layout.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, Mapping) and isinstance(entry.get("id"), str):
                    ids.add(entry["id"])
    return ids


def _retiring_ids() -> set[str]:
    """Retiring list from docs/SCORECARD.md, via the planner's reader."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "plan_surface_migration", ROOT / "scripts" / "plan-surface-migration.py")
    if spec is None or spec.loader is None:
        return set()
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.retiring_ids()


def _merged_entries(desired_entries: list[Any], current_by_id: Mapping[str, Mapping[str, Any]]) -> list[Any]:
    """Desired entries in desired order, each keeping the live entry's inline
    settings (watermarks, mute lists, tray order) when the id is retained."""
    out = []
    for entry in desired_entries:
        if isinstance(entry, Mapping) and isinstance(entry.get("id"), str) and entry["id"] in current_by_id:
            merged = dict(current_by_id[entry["id"]])
            merged.update(entry)
            out.append(merged)
        else:
            out.append(copy.deepcopy(entry))
    return out


def _merge_bar(current: Mapping[str, Any], desired_bar: Mapping[str, Any]) -> dict[str, Any]:
    bar = copy.deepcopy(dict(desired_bar))
    live = current.get("bar", {}).get("layout", {}) if isinstance(current.get("bar"), Mapping) else {}
    by_id = {e["id"]: e for entries in (live.values() if isinstance(live, Mapping) else [])
             if isinstance(entries, list) for e in entries
             if isinstance(e, Mapping) and isinstance(e.get("id"), str)}
    layout = bar.get("layout")
    if isinstance(layout, Mapping):
        bar["layout"] = {section: _merged_entries(entries, by_id) if isinstance(entries, list) else entries
                         for section, entries in layout.items()}
    return bar


def _merge_plugins(current: Mapping[str, Any], desired_plugins: Any) -> Any:
    if not isinstance(desired_plugins, list):
        return copy.deepcopy(desired_plugins)
    live = current.get("plugins")
    by_id = {e["id"]: e for e in (live if isinstance(live, list) else [])
             if isinstance(e, Mapping) and isinstance(e.get("id"), str)}
    return _merged_entries(desired_plugins, by_id)


def _plan(current: Mapping[str, Any], desired: Mapping[str, Any]) -> dict[str, Any]:
    current_ids = _direct_ids(current)
    desired_ids = _direct_ids(desired)
    placed_retired = sorted(desired_ids & _retiring_ids())
    if placed_retired:
        raise RuntimeError("desired layout places retired plugin(s): " + ", ".join(placed_retired))
    return {
        "remove_bar_ids": sorted(current_ids - desired_ids),
        "add_bar_ids": sorted(desired_ids - current_ids),
        "retained_bar_ids": sorted(current_ids & desired_ids),
        "requires_shell_backup": bool(current_ids != desired_ids),
        "destructive_actions": [],
    }


def _safe_environment() -> dict[str, str]:
    allowed = {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "DBUS_SESSION_BUS_ADDRESS",
        "WAYLAND_DISPLAY",
        "HYPRLAND_INSTANCE_SIGNATURE",
        "OMARCHY_PATH",
    }
    return {key: value for key, value in os.environ.items() if key in allowed and value}


def _default_rescan() -> None:
    configured_root = os.environ.get("OMARCHY_PATH")
    candidates = []
    if configured_root:
        candidates.append(Path(configured_root) / "bin" / "omarchy-shell")
    candidates.append(Path("/usr/share/omarchy/bin/omarchy-shell"))
    executable = next((str(path) for path in candidates if path.is_file() and os.access(path, os.X_OK)), None)
    if executable is None:
        executable = shutil.which("omarchy-shell")
    if executable is None:
        raise RuntimeError("omarchy-shell is unavailable for plugin rescan")
    result = subprocess.run(
        [executable, "shell", "rescanPlugins"],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
        env=_safe_environment(),
    )
    if result.returncode != 0:
        raise RuntimeError("host plugin rescan failed")


def _atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        if mode is not None:
            os.fchmod(fd, mode)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _backup_current(current_path: Path, backup_root: Path, plan: Mapping[str, Any]) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    backup_dir = backup_root / f"surface-migration-{timestamp}-{os.getpid()}"
    backup_dir.mkdir(parents=True, mode=0o700)
    original = current_path.read_bytes()
    (backup_dir / "shell.json").write_bytes(original)
    os.chmod(backup_dir / "shell.json", stat.S_IMODE(current_path.stat().st_mode))
    metadata = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "shell.json",
        "sha256": hashlib.sha256(original).hexdigest(),
        "plan": plan,
    }
    metadata_path = backup_dir / "metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    os.chmod(metadata_path, 0o600)
    return backup_dir


def apply_migration(
    *,
    current_path: Path,
    desired_path: Path,
    backup_root: Path,
    rescan: Callable[[], None] | None = None,
) -> dict[str, Any]:
    current = _read_json(current_path)
    desired = _read_json(desired_path)
    plan = _plan(current, desired)
    original_bytes = current_path.read_bytes()
    backup_path = _backup_current(current_path, backup_root, plan)
    updated = copy.deepcopy(current)
    if "bar" in desired:
        updated["bar"] = _merge_bar(current, desired["bar"])
    if "disabledPlugins" in desired:
        updated["disabledPlugins"] = desired["disabledPlugins"]
    if "plugins" in desired:
        updated["plugins"] = _merge_plugins(current, desired["plugins"])
    mode = stat.S_IMODE(current_path.stat().st_mode)
    encoded = (json.dumps(updated, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    _atomic_write(current_path, encoded, mode)
    try:
        (rescan or _default_rescan)()
    except Exception:
        _atomic_write(current_path, original_bytes, mode)
        raise
    return {"backup_path": backup_path, "plan": plan}


def rollback_migration(
    *,
    current_path: Path,
    backup_path: Path,
    rescan: Callable[[], None] | None = None,
) -> None:
    backup_file = backup_path / "shell.json"
    if not backup_file.is_file():
        raise RuntimeError("migration backup does not contain shell.json")
    mode = stat.S_IMODE(current_path.stat().st_mode) if current_path.exists() else 0o600
    _atomic_write(current_path, backup_file.read_bytes(), mode)
    (rescan or _default_rescan)()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--current", type=Path, default=DEFAULT_CURRENT)
    parser.add_argument("--desired", type=Path, default=DEFAULT_DESIRED)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--apply", action="store_true", help="write the migration; default is dry-run")
    parser.add_argument("--rollback", type=Path, help="restore a prior migration backup")
    parser.add_argument("--no-rescan", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.rollback:
            rollback_migration(
                current_path=args.current,
                backup_path=args.rollback,
                rescan=(lambda: None) if args.no_rescan else None,
            )
            print(json.dumps({"rolled_back": True, "backup": str(args.rollback)}, indent=2))
            return 0
        current = _read_json(args.current)
        desired = _read_json(args.desired)
        plan = _plan(current, desired)
        if not args.apply:
            print(json.dumps({"applied": False, "plan": plan}, indent=2, sort_keys=True))
            return 0
        result = apply_migration(
            current_path=args.current,
            desired_path=args.desired,
            backup_root=args.backup_root,
            rescan=(lambda: None) if args.no_rescan else None,
        )
        print(json.dumps({"applied": True, "backup": str(result["backup_path"]), "plan": result["plan"]}, indent=2, sort_keys=True))
        return 0
    except Exception as exc:
        print(f"surface migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
