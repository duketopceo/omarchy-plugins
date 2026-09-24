from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "check-host-integration.py"


def load_module():
    assert SCRIPT.exists(), f"host integration checker is missing: {SCRIPT}"
    spec = importlib.util.spec_from_file_location("check_host_integration", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def runner_for(overrides: dict[str, tuple[int, str]] | None = None):
    overrides = overrides or {}

    def run(argv, timeout=2.0):
        key = " ".join(argv)
        for needle, result in overrides.items():
            if needle in key:
                return result
        if "wpctl status" in key:
            return 0, "Audio\nSink: built-in\n"
        if "wireplumber.service" in key:
            return 0, "active\n"
        if "pipewire.service" in key:
            return 0, "active\n"
        if "easyeffects.service" in key:
            return 0, "active\n"
        if "bluetoothctl show" in key:
            return 0, "Controller powered: yes\n"
        if "bt-agent.service" in key:
            return 0, "active\n"
        if "hyprctl monitors" in key:
            return 0, "Monitor eDP-1: 1920x1200\n"
        if "hyprmoncfgd.service" in key:
            return 0, "active\n"
        return 127, ""

    return run


def test_healthy_host_reports_each_surface_without_raw_output(tmp_path: Path) -> None:
    module = load_module()
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "event0").write_text("")

    result = module.check_host_integration(
        command_runner=runner_for(),
        input_root=input_root,
        architecture="aarch64",
    )

    assert result["overall"] == "healthy"
    assert result["surfaces"]["audio"]["status"] == "healthy"
    assert result["surfaces"]["bluetooth"]["status"] == "healthy"
    assert result["surfaces"]["display"]["status"] == "healthy"
    assert result["surfaces"]["input"]["status"] == "healthy"
    assert "built-in" not in str(result)


def test_optional_easyeffects_failure_degrades_audio_without_failing_other_surfaces(tmp_path: Path) -> None:
    module = load_module()
    input_root = tmp_path / "input"
    input_root.mkdir()
    (input_root / "event0").write_text("")

    result = module.check_host_integration(
        command_runner=runner_for({"easyeffects.service": (1, "failed\n")}),
        input_root=input_root,
    )

    assert result["overall"] == "degraded"
    assert result["surfaces"]["audio"]["status"] == "degraded"
    assert result["surfaces"]["audio"]["optional_failure"] is True
    assert result["surfaces"]["bluetooth"]["status"] == "healthy"


def test_missing_input_devices_are_reported_as_degraded(tmp_path: Path) -> None:
    module = load_module()
    missing = tmp_path / "missing-input"

    result = module.check_host_integration(
        command_runner=runner_for(),
        input_root=missing,
    )

    assert result["overall"] == "degraded"
    assert result["surfaces"]["input"]["status"] == "degraded"
    assert "input devices unavailable" in result["surfaces"]["input"]["reasons"]
