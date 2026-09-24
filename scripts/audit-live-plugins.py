#!/usr/bin/env python3
"""Produce a sanitized inventory of Omarchy plugin state.

The default command reads the local plugin registry and shell layout without
modifying either.  Tests and operators can pass a fixture root containing
``plugins/``, ``shell.json``, ``registry.ndjson``, ``services.json``, and
``dispositions.json`` to exercise the same code path without touching the host.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any


MAX_INPUT_BYTES = 2 * 1024 * 1024
MAX_COMMAND_BYTES = 1024 * 1024
COMMAND_TIMEOUT_SECONDS = 3
SECRET_KEY_RE = re.compile(
    r"(?:password|passwd|secret|token|api[_-]?key|authorization|credential|private[_-]?key)",
    re.IGNORECASE,
)
SECRET_VALUE_RES = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{8,}\b"),
    re.compile(r"(?i)\bBearer\s+[^\s]+"),
    re.compile(r"(?i)([a-z][a-z0-9+.-]*://)[^/\s:@]+:[^@/\s]+@"),
)

SERVICE_ALIASES = {
    "bt-agent.service": "io.github.ncr.omaphones",
    "dayflow.service": "io.github.duketopceo.dayflow",
    "dimd.service": "io.github.duketopceo.dim",
    "hyprmoncfgd.service": "crmne.hyprmoncfg",
    "omarchy-fan-daemon.service": "lukedaduke.fan",
    "voxtype.service": "hancore.voxtype-enhance",
}


class InventoryError(ValueError):
    """Raised when an input file cannot be safely interpreted."""


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in SECRET_VALUE_RES:
        if pattern.pattern.startswith("(?i)"):
            redacted = pattern.sub(lambda match: match.group(1) + "[REDACTED]@" if "://" in match.group(0) else "[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def redact(value: Any, key: str | None = None) -> Any:
    """Redact secret-shaped keys and values before putting data in output."""
    if key and SECRET_KEY_RE.search(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, tuple):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _redact_text(value)
    return value


def read_json(path: Path) -> Any:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InventoryError(f"cannot read {path.name}: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InventoryError(f"input exceeds {MAX_INPUT_BYTES} bytes: {path.name}")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InventoryError(f"invalid JSON in {path.name}: {exc}") from exc


def read_ndjson(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise InventoryError(f"cannot read {path.name}: {exc}") from exc
    if len(raw) > MAX_INPUT_BYTES:
        raise InventoryError(f"input exceeds {MAX_INPUT_BYTES} bytes: {path.name}")
    entries: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InventoryError(f"invalid NDJSON at {path.name}:{line_number}: {exc}") from exc
        if not isinstance(value, dict):
            raise InventoryError(f"NDJSON entry is not an object at {path.name}:{line_number}")
        entries.append(value)
    return entries


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if isinstance(item, (str, int, float))]


def _manifest_record(path: Path) -> dict[str, Any]:
    source_name = path.name
    source = "backup" if ".bak." in source_name else ("link" if path.is_symlink() else "directory")
    manifest_path = path / "manifest.json"
    if not manifest_path.is_file():
        return {
            "id": source_name,
            "source": source,
            "source_names": [source_name],
            "manifest_valid": False,
            "name": source_name,
            "version": None,
            "author": None,
            "license": None,
            "kinds": [],
            "entry_points": {},
            "architecture_support": "unknown",
            "dependencies": [],
            "warning": "missing manifest.json",
        }
    try:
        manifest = read_json(manifest_path)
    except InventoryError as exc:
        return {
            "id": source_name,
            "source": source,
            "source_names": [source_name],
            "manifest_valid": False,
            "name": source_name,
            "version": None,
            "author": None,
            "license": None,
            "kinds": [],
            "entry_points": {},
            "architecture_support": "unknown",
            "dependencies": [],
            "warning": str(exc),
        }
    if not isinstance(manifest, dict):
        return {
            "id": source_name,
            "source": source,
            "source_names": [source_name],
            "manifest_valid": False,
            "name": source_name,
            "version": None,
            "author": None,
            "license": None,
            "kinds": [],
            "entry_points": {},
            "architecture_support": "unknown",
            "dependencies": [],
            "warning": "manifest must be an object",
        }
    plugin_id = str(manifest.get("id") or source_name)
    entry_points = manifest.get("entryPoints")
    if not isinstance(entry_points, dict):
        entry_points = {}
    architectures = manifest.get("architectures", manifest.get("architectureSupport"))
    if isinstance(architectures, list):
        architecture_support = ",".join(str(item) for item in architectures)
    elif architectures:
        architecture_support = str(architectures)
    else:
        architecture_support = "unknown"
    dependencies = manifest.get("dependencies", [])
    if not isinstance(dependencies, list):
        dependencies = []
    return {
        "id": plugin_id,
        "source": source,
        "source_names": [source_name],
        "manifest_valid": True,
        "name": str(manifest.get("name") or plugin_id),
        "version": manifest.get("version"),
        "author": manifest.get("author"),
        "license": manifest.get("license"),
        "kinds": _as_string_list(manifest.get("kinds")),
        "entry_points": {str(k): str(v) for k, v in entry_points.items()},
        "architecture_support": architecture_support,
        "dependencies": _as_string_list(dependencies),
    }


def discover_manifests(plugin_root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    if not plugin_root.is_dir():
        return [], [f"plugin root is unavailable: {plugin_root.name or 'root'}"]
    records: list[dict[str, Any]] = []
    warnings: list[str] = []
    for path in sorted(plugin_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or path.name.startswith("."):
            continue
        record = _manifest_record(path)
        records.append(record)
        if record.get("warning"):
            warnings.append(f"{record['id']}: {record['warning']}")
    return records, warnings


def _walk_ids(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        plugin_id = value.get("id")
        if isinstance(plugin_id, str) and plugin_id:
            yield plugin_id
        for child in value.values():
            yield from _walk_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_ids(child)


def extract_shell_surfaces(shell_config: Mapping[str, Any]) -> dict[str, set[str]]:
    bar = shell_config.get("bar")
    layout = bar.get("layout", {}) if isinstance(bar, Mapping) else {}
    direct: set[str] = set()
    hosted: set[str] = set()
    configured: set[str] = set()
    disabled: set[str] = set()
    if isinstance(layout, Mapping):
        for entries in layout.values():
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, Mapping):
                    continue
                plugin_id = entry.get("id")
                if isinstance(plugin_id, str) and plugin_id:
                    direct.add(plugin_id)
                widgets = entry.get("widgets", [])
                if isinstance(widgets, list):
                    for widget in widgets:
                        if not isinstance(widget, Mapping):
                            continue
                        nested = widget.get("entry", widget)
                        if isinstance(nested, Mapping):
                            nested_id = nested.get("id")
                            if isinstance(nested_id, str) and nested_id:
                                hosted.add(nested_id)
    plugins = shell_config.get("plugins", [])
    if isinstance(plugins, list):
        configured.update(plugin_id for plugin_id in _walk_ids(plugins) if plugin_id)
    disabled_values = shell_config.get("disabledPlugins", [])
    if isinstance(disabled_values, list):
        disabled.update(str(item) for item in disabled_values if isinstance(item, str))
    return {"direct": direct, "hosted": hosted, "configured": configured, "disabled": disabled}


def _runtime_for(plugin_id: str, services: Mapping[str, Any]) -> dict[str, Any]:
    value = services.get(plugin_id, {})
    if isinstance(value, str):
        value = {"health": value}
    if not isinstance(value, Mapping):
        value = {}
    state = str(value.get("state", "")).lower()
    loaded = bool(value.get("loaded", state in {"active", "running", "loaded"}))
    running = bool(value.get("running", state in {"active", "running"}))
    health = value.get("health")
    if health not in {"healthy", "degraded", "unknown"}:
        health = "unknown"
    return {"loaded": loaded, "running": running, "health": str(health)}


def _dependency_class(kinds: Sequence[str], dependencies: Sequence[str]) -> str:
    if dependencies:
        return "external-dependency"
    if "service" in kinds:
        return "service"
    if "bar-widget" in kinds or "bar" in kinds:
        return "bar-surface"
    if "panel" in kinds:
        return "panel"
    if "overlay" in kinds:
        return "overlay"
    return "plugin"


def _status(
    *,
    enabled: bool,
    direct: bool,
    hosted: bool,
    configured: bool,
    runtime: Mapping[str, Any],
) -> str:
    if runtime["health"] == "degraded":
        return "degraded"
    if runtime["health"] == "healthy":
        return "healthy"
    if runtime["running"]:
        return "running"
    if runtime["loaded"]:
        return "loaded"
    if direct:
        return "placed"
    if hosted:
        return "hosted"
    if enabled or configured:
        return "configured"
    return "disabled"


def audit_inventory(
    *,
    plugin_root: Path,
    shell_config: Mapping[str, Any],
    registry_entries: Sequence[Mapping[str, Any]],
    services: Mapping[str, Any] | None = None,
    dispositions: Mapping[str, Any] | None = None,
    git_status: Mapping[str, str] | None = None,
    command_status: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic, sanitized inventory from supplied inputs."""
    services = services or {}
    dispositions = dispositions or {}
    git_status = git_status or {}
    command_status = command_status or {}
    surfaces = extract_shell_surfaces(shell_config)
    manifests, warnings = discover_manifests(plugin_root)
    by_manifest_id: dict[str, list[dict[str, Any]]] = {}
    for record in manifests:
        by_manifest_id.setdefault(str(record["id"]), []).append(record)
    registry_by_id: dict[str, Mapping[str, Any]] = {}
    for entry in registry_entries:
        plugin_id = entry.get("id")
        if isinstance(plugin_id, str) and plugin_id:
            registry_by_id.setdefault(plugin_id, entry)
    all_ids = set(by_manifest_id) | set(registry_by_id) | set(surfaces["direct"]) | set(surfaces["hosted"])
    plugins: list[dict[str, Any]] = []
    for plugin_id in sorted(all_ids):
        candidates = by_manifest_id.get(plugin_id, [])
        primary = next((item for item in candidates if item.get("source") != "backup"), None)
        primary = primary or (candidates[0] if candidates else None)
        registry = registry_by_id.get(plugin_id, {})
        if primary is None:
            source = "host" if registry.get("firstParty") else "registry"
            name = str(registry.get("name") or plugin_id)
            version = None
            author = None
            license_name = None
            kinds = _as_string_list(registry.get("kinds"))
            entry_points: dict[str, str] = {}
            architecture_support = "unknown"
            dependencies: list[str] = []
            manifest_valid: bool | None = None
        else:
            source = str(primary.get("source") or "unknown")
            name = str(primary.get("name") or plugin_id)
            version = primary.get("version")
            author = primary.get("author")
            license_name = primary.get("license")
            kinds = _as_string_list(primary.get("kinds"))
            entry_points = dict(primary.get("entry_points") or {})
            architecture_support = str(primary.get("architecture_support") or "unknown")
            dependencies = _as_string_list(primary.get("dependencies"))
            manifest_valid = bool(primary.get("manifest_valid"))
        enabled = bool(registry.get("enabled", False))
        direct = plugin_id in surfaces["direct"]
        hosted = plugin_id in surfaces["hosted"]
        configured = enabled or plugin_id in surfaces["configured"]
        disabled = plugin_id in surfaces["disabled"] or not enabled
        runtime = _runtime_for(plugin_id, services)
        status = _status(enabled=enabled, direct=direct, hosted=hosted, configured=configured, runtime=runtime)
        entry = {
            "id": plugin_id,
            "name": name,
            "version": version,
            "author": author,
            "owner": "omarchy" if registry.get("firstParty") else (author or "external"),
            "license": license_name,
            "source": source,
            "source_names": sorted({str(item.get("source_names", [plugin_id])[0]) for item in candidates}),
            "source_status": git_status.get(plugin_id, "unknown"),
            "manifest_valid": manifest_valid,
            "manifest_occurrences": len(candidates),
            "kinds": kinds,
            "entry_points": entry_points,
            "dependency_class": _dependency_class(kinds, dependencies),
            "architecture_support": architecture_support,
            "state": {
                "registry_enabled": enabled,
                "configured": configured,
                "direct_bar": direct,
                "hosted": hosted,
                "loaded": runtime["loaded"],
                "running": runtime["running"],
                "health": runtime["health"],
            },
            "status": status,
            "disposition": str(dispositions.get(plugin_id, "observe")),
            "commands": {
                command: command_status.get(command, "unknown")
                for command in dependencies
            },
            "warnings": [],
        }
        if len(candidates) > 1:
            warning = f"duplicate manifest id: {plugin_id}"
            entry["warnings"].append(warning)
            warnings.append(warning)
        if primary and not primary.get("manifest_valid", False):
            warning = f"{plugin_id}: missing or invalid manifest"
            entry["warnings"].append(warning)
            if warning not in warnings:
                warnings.append(warning)
        if plugin_id in surfaces["hosted"] and not direct:
            entry["warnings"].append("hosted surface; not directly placed in bar layout")
        if disabled and (direct or hosted or configured) and not enabled:
            entry["warnings"].append("disabled registry state conflicts with shell surface")
        plugins.append(redact(entry))

    unique_warnings = list(dict.fromkeys(str(item) for item in warnings))
    enabled_count = sum(1 for entry in plugins if entry["state"]["registry_enabled"])
    direct_count = sum(1 for entry in plugins if entry["state"]["direct_bar"])
    hosted_count = sum(1 for entry in plugins if entry["state"]["hosted"])
    non_bar_enabled = sum(
        1
        for entry in plugins
        if entry["state"]["registry_enabled"] and not entry["state"]["direct_bar"]
    )
    duplicate_count = sum(1 for entry in plugins if entry["manifest_occurrences"] > 1)
    return {
        "schema_version": 1,
        "host": {
            "architecture": platform.machine() or "unknown",
            "system": platform.system() or "unknown",
            "kernel": platform.release() or "unknown",
        },
        "counts": {
            "discovered": len(plugins),
            "enabled": enabled_count,
            "direct_bar": direct_count,
            "enabled_non_bar": non_bar_enabled,
            "hosted": hosted_count,
            "duplicates": duplicate_count,
            "warnings": len(unique_warnings),
        },
        "warnings": unique_warnings,
        "plugins": plugins,
    }


def _load_optional_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return read_json(path)


def _probe_environment() -> dict[str, str]:
    allowed = {
        "PATH",
        "HOME",
        "USER",
        "LOGNAME",
        "LANG",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "OMARCHY_PATH",
    }
    return {key: value for key, value in os.environ.items() if key in allowed and value}


def _run_live_registry() -> list[dict[str, Any]]:
    executable = shutil.which("omarchy-shell")
    if not executable:
        return []
    try:
        result = subprocess.run(
            [executable, "shell", "listPlugins"],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT_SECONDS,
            check=False,
            env=_probe_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0 or len(result.stdout.encode("utf-8", errors="ignore")) > MAX_COMMAND_BYTES:
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, list):
        return [value for value in payload if isinstance(value, dict)]
    if isinstance(payload, dict):
        return [payload]
    entries: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            entries.append(value)
    return entries


def _run_git_status(plugin_root: Path) -> dict[str, str]:
    statuses: dict[str, str] = {}
    if not plugin_root.is_dir():
        return statuses
    git = shutil.which("git")
    if not git:
        return statuses
    for path in sorted(plugin_root.iterdir(), key=lambda item: item.name):
        if not path.is_dir() or path.name.startswith("."):
            continue
        try:
            result = subprocess.run(
                [git, "-C", str(path), "status", "--porcelain"],
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT_SECONDS,
                check=False,
                env=_probe_environment(),
            )
        except (OSError, subprocess.TimeoutExpired):
            statuses[path.name] = "unavailable"
            continue
        statuses[path.name] = "dirty" if result.returncode == 0 and result.stdout.strip() else "clean" if result.returncode == 0 else "unavailable"
    return statuses


def audit_fixture(fixture_root: Path, *, probe_git: bool = False) -> dict[str, Any]:
    """Audit a directory containing fixture inputs without host access."""
    plugin_root = fixture_root / "plugins"
    shell = _load_optional_json(fixture_root / "shell.json", {})
    registry_path = fixture_root / "registry.ndjson"
    registry = read_ndjson(registry_path) if registry_path.exists() else []
    services = _load_optional_json(fixture_root / "services.json", {})
    dispositions = _load_optional_json(fixture_root / "dispositions.json", {})
    return audit_inventory(
        plugin_root=plugin_root,
        shell_config=shell if isinstance(shell, Mapping) else {},
        registry_entries=registry,
        services=services if isinstance(services, Mapping) else {},
        dispositions=dispositions if isinstance(dispositions, Mapping) else {},
        git_status=_run_git_status(plugin_root) if probe_git else {},
    )


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip() or "—"


def render_markdown(inventory: Mapping[str, Any]) -> str:
    counts = inventory.get("counts", {})
    lines = [
        "# Active plugin estate review",
        "",
        "> Generated by `scripts/audit-live-plugins.py`; paths and secret values are intentionally omitted.",
        "",
        "## Summary",
        "",
        f"- Discovered: **{_escape_cell(counts.get('discovered', 0))}**",
        f"- Registry-enabled: **{_escape_cell(counts.get('enabled', 0))}**",
        f"- Direct bar entries: **{_escape_cell(counts.get('direct_bar', 0))}**",
        f"- Enabled non-bar entries: **{_escape_cell(counts.get('enabled_non_bar', 0))}**",
        f"- Tray-hosted widgets: **{_escape_cell(counts.get('hosted', 0))}**",
        f"- Duplicate manifest IDs: **{_escape_cell(counts.get('duplicates', 0))}**",
        "",
        "## Host profile",
        "",
        f"- Architecture: **{_escape_cell(inventory.get('host', {}).get('architecture'))}**",
        f"- System: **{_escape_cell(inventory.get('host', {}).get('system'))}**",
        f"- Kernel: **{_escape_cell(inventory.get('host', {}).get('kernel'))}**",
        "",
        "## State semantics",
        "",
        "- `configured` means the registry or shell knows about the surface; it does not prove that a helper is running.",
        "- `placed` and `hosted` describe direct bar and tray-hosted surfaces respectively.",
        "- `healthy`, `degraded`, `running`, and `loaded` require runtime evidence; `unknown` is intentional when no probe is available.",
        "- `observe` means the inventory has not yet made an ownership or retirement decision.",
        "",
        "## Plugin inventory",
        "",
        "| ID | Version | Source | Owner | Surface | Status | Health | Dependency | Architecture | Disposition |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for entry in inventory.get("plugins", []):
        if not isinstance(entry, Mapping):
            continue
        state = entry.get("state", {})
        surface = []
        if state.get("direct_bar"):
            surface.append("direct-bar")
        if state.get("hosted"):
            surface.append("hosted")
        if not surface and state.get("configured"):
            surface.append("implicit")
        if not surface:
            surface.append("disabled")
        lines.append(
            "| `{}` | {} | {} | {} | {} | {} | {} | {} | {} | {} |".format(
                _escape_cell(entry.get("id")),
                _escape_cell(entry.get("version")),
                _escape_cell(entry.get("source")),
                _escape_cell(entry.get("owner")),
                _escape_cell(", ".join(surface)),
                _escape_cell(entry.get("status")),
                _escape_cell(state.get("health")),
                _escape_cell(entry.get("dependency_class")),
                _escape_cell(entry.get("architecture_support")),
                _escape_cell(entry.get("disposition")),
            )
        )
    lines.extend(
        [
            "",
            "## Contract follow-up",
            "",
            "External findings and owner handoffs are summarized in `docs/reviews/active-plugin-contract.md`.",
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = inventory.get("warnings", [])
    if warnings:
        lines.extend(f"- {_escape_cell(warning)}" for warning in warnings)
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _default_paths() -> tuple[Path, Path, Path | None, Path | None, Path | None]:
    home = Path.home()
    plugin_root = Path(os.environ.get("OMARCHY_PLUGIN_ROOT", home / ".config" / "omarchy" / "plugins"))
    shell_config = Path(os.environ.get("OMARCHY_SHELL_CONFIG", home / ".config" / "omarchy" / "shell.json"))
    return plugin_root, shell_config, None, None, None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plugin-root", type=Path)
    parser.add_argument("--shell-config", type=Path)
    parser.add_argument("--registry-file", type=Path, help="NDJSON registry fixture; omit to query omarchy-shell")
    parser.add_argument("--services-file", type=Path, help="JSON service-state fixture")
    parser.add_argument("--dispositions-file", type=Path, help="JSON disposition map")
    parser.add_argument("--fixture-root", type=Path, help="fixture directory; no live host access")
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path, help="write the report to this path instead of stdout")
    parser.add_argument("--no-git", action="store_true", help="skip source git status probes")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.fixture_root:
        try:
            inventory = audit_fixture(args.fixture_root, probe_git=not args.no_git)
        except InventoryError as exc:
            print(str(exc), file=sys.stderr)
            return 2
    else:
        default_plugin_root, default_shell, _, _, _ = _default_paths()
        plugin_root = args.plugin_root or default_plugin_root
        shell_path = args.shell_config or default_shell
        try:
            shell = read_json(shell_path) if shell_path.exists() else {}
            registry = read_ndjson(args.registry_file) if args.registry_file else _run_live_registry()
            services = read_json(args.services_file) if args.services_file else {}
            dispositions = read_json(args.dispositions_file) if args.dispositions_file else {}
        except InventoryError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        inventory = audit_inventory(
            plugin_root=plugin_root,
            shell_config=shell if isinstance(shell, Mapping) else {},
            registry_entries=registry,
            services=services if isinstance(services, Mapping) else {},
            dispositions=dispositions if isinstance(dispositions, Mapping) else {},
            git_status={} if args.no_git else _run_git_status(plugin_root),
        )
    report = json.dumps(inventory, indent=2, sort_keys=True) + "\n" if args.format == "json" else render_markdown(inventory)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
    else:
        sys.stdout.write(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
