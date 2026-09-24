#!/usr/bin/env python3
"""Read-only health checks for the current Asahi desktop integrations."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


COMMAND_TIMEOUT_SECONDS = 2.0
MAX_COMMAND_BYTES = 64 * 1024
CommandRunner = Callable[[list[str], float], tuple[int, str]]


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


def _run_fixed(argv: list[str], timeout: float = COMMAND_TIMEOUT_SECONDS) -> tuple[int, str]:
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=_safe_environment(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1, ""
    output = result.stdout or ""
    if len(output.encode("utf-8", errors="ignore")) > MAX_COMMAND_BYTES:
        return 1, ""
    return result.returncode, output


def _run(command_runner: CommandRunner, argv: list[str]) -> tuple[int, str]:
    try:
        return command_runner(argv, COMMAND_TIMEOUT_SECONDS)
    except (OSError, subprocess.SubprocessError):
        return 1, ""


def _service_check(
    command_runner: CommandRunner,
    service: str,
) -> dict[str, str]:
    code, output = _run(
        command_runner,
        ["/usr/bin/systemctl", "--user", "is-active", service],
    )
    status = "healthy" if code == 0 and output.strip() == "active" else "degraded"
    return {"name": service, "status": status}


def _audio_surface(command_runner: CommandRunner) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    reasons: list[str] = []
    optional_failure = False

    for service in ("pipewire.service", "wireplumber.service"):
        check = _service_check(command_runner, service)
        checks.append(check)
        if check["status"] != "healthy":
            reasons.append("audio service unavailable")

    wpctl_code, wpctl_output = _run(command_runner, ["/usr/bin/wpctl", "status"])
    wpctl_status = "healthy" if wpctl_code == 0 and bool(wpctl_output.strip()) else "degraded"
    checks.append({"name": "wpctl status", "status": wpctl_status})
    if wpctl_status != "healthy":
        reasons.append("audio device state unavailable")

    easyeffects = _service_check(command_runner, "easyeffects.service")
    checks.append(easyeffects)
    if easyeffects["status"] != "healthy":
        optional_failure = True
        reasons.append("optional DSP unavailable")

    status = "degraded" if reasons else "healthy"
    return {
        "status": status,
        "reasons": list(dict.fromkeys(reasons)),
        "optional_failure": optional_failure,
        "checks": checks,
    }


def _bluetooth_surface(command_runner: CommandRunner) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    reasons: list[str] = []
    code, output = _run(command_runner, ["/usr/bin/bluetoothctl", "show"])
    powered = code == 0 and "powered: yes" in output.lower()
    checks.append({"name": "bluetooth adapter", "status": "healthy" if powered else "degraded"})
    if not powered:
        reasons.append("Bluetooth adapter unavailable")

    service = _service_check(command_runner, "bt-agent.service")
    checks.append(service)
    if service["status"] != "healthy":
        reasons.append("Bluetooth integration service unavailable")

    return {
        "status": "degraded" if reasons else "healthy",
        "reasons": list(dict.fromkeys(reasons)),
        "optional_failure": False,
        "checks": checks,
    }


def _display_surface(command_runner: CommandRunner) -> dict[str, Any]:
    checks: list[dict[str, str]] = []
    reasons: list[str] = []
    code, output = _run(command_runner, ["/usr/bin/hyprctl", "monitors"])
    monitor_status = "healthy" if code == 0 and bool(output.strip()) else "degraded"
    checks.append({"name": "Hyprland monitors", "status": monitor_status})
    if monitor_status != "healthy":
        reasons.append("display state unavailable")

    service = _service_check(command_runner, "hyprmoncfgd.service")
    checks.append(service)
    optional_failure = service["status"] != "healthy"
    if optional_failure:
        reasons.append("optional display manager unavailable")

    return {
        "status": "degraded" if reasons else "healthy",
        "reasons": list(dict.fromkeys(reasons)),
        "optional_failure": optional_failure,
        "checks": checks,
    }


def _input_surface(input_root: Path) -> dict[str, Any]:
    available = False
    try:
        available = input_root.is_dir() and any(input_root.iterdir())
    except OSError:
        available = False
    return {
        "status": "healthy" if available else "degraded",
        "reasons": [] if available else ["input devices unavailable"],
        "optional_failure": False,
        "checks": [{"name": "input devices", "status": "healthy" if available else "degraded"}],
    }


def check_host_integration(
    *,
    command_runner: CommandRunner | None = None,
    input_root: Path = Path("/dev/input"),
    architecture: str | None = None,
) -> dict[str, Any]:
    """Return bounded status data without copying command output or paths."""
    runner = command_runner or _run_fixed
    surfaces = {
        "audio": _audio_surface(runner),
        "bluetooth": _bluetooth_surface(runner),
        "display": _display_surface(runner),
        "input": _input_surface(input_root),
    }
    overall = "degraded" if any(surface["status"] != "healthy" for surface in surfaces.values()) else "healthy"
    return {
        "schema_version": 1,
        "host": {
            "architecture": architecture or platform.machine() or "unknown",
            "system": platform.system() or "unknown",
        },
        "overall": overall,
        "surfaces": surfaces,
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Host integration health",
        "",
        f"- Overall: **{report.get('overall', 'unknown')}**",
        f"- Architecture: **{report.get('host', {}).get('architecture', 'unknown')}**",
        "",
        "| Surface | Status | Details |",
        "|---|---|---|",
    ]
    for name, surface in report.get("surfaces", {}).items():
        reasons = ", ".join(surface.get("reasons", [])) or "none"
        lines.append(f"| `{name}` | {surface.get('status', 'unknown')} | {reasons} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--input-root", type=Path, default=Path("/dev/input"))
    parser.add_argument("--strict", action="store_true", help="exit non-zero when any surface is degraded")
    args = parser.parse_args(argv)
    report = check_host_integration(input_root=args.input_root)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        sys.stdout.write(render_markdown(report))
    return 1 if args.strict and report["overall"] != "healthy" else 0


if __name__ == "__main__":
    raise SystemExit(main())
