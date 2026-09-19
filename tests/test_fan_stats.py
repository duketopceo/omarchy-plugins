from __future__ import annotations

import importlib.util
import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAN_DIR = ROOT / "plugins/lukedaduke.fan"
STATS = FAN_DIR / "bin/system_monitor_stats.py"
KILL = FAN_DIR / "bin/kill_proc.py"
FAN_SET = FAN_DIR / "bin/omarchy-fan-set"
PANEL = FAN_DIR / "Panel.qml"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def load_fan_set():
    # No .py extension — load via SourceFileLoader like the daemon below.
    return SourceFileLoader("omarchy_fan_set", str(FAN_SET)).load_module()


def test_collect_json_bounds() -> None:
    stats = load(STATS, "system_monitor_stats")
    data = stats.collect(sample_seconds=0)
    assert data["ok"] is True
    assert 0 <= data["mem_pct"] <= 100
    assert 0 <= data["cpu_load"] <= 100
    assert isinstance(data["cpu_temp"], str)
    assert isinstance(data["fan_control"], bool)
    assert isinstance(data["daemon_running"], bool)
    json.dumps(data)


def test_empty_hwmon_temps(tmp_path: Path) -> None:
    stats = load(STATS, "system_monitor_stats")
    empty = tmp_path / "hwmon"
    empty.mkdir()
    devices = stats.hwmon_paths(base=empty)
    assert devices == {}
    cpu, fan1, fan2 = stats.cpu_temp_and_fans(devices)
    assert cpu == "--"
    assert fan1 == 0
    assert stats.nvme_temp(devices) == "--"


def test_kill_refuses_pid_one() -> None:
    kill = load(KILL, "kill_proc")
    assert kill.kill_pid(1) == 2
    assert kill.kill_pid(0) == 2
    assert kill.main([]) == 2


def test_daemon_descriptor_security(tmp_path: Path) -> None:
    from importlib.machinery import SourceFileLoader
    daemon_path = ROOT / "plugins/lukedaduke.fan/bin/omarchy-fan-daemon"
    daemon = SourceFileLoader("omarchy_fan_daemon", str(daemon_path)).load_module()

    uid = daemon.target_uid()
    assert isinstance(uid, int) and uid >= 0

    mode = daemon.get_requested_mode(uid)
    assert mode in {"auto", "low", "med", "high", "custom"} or mode.startswith("custom-")

    curve = daemon.load_curve(uid)
    assert isinstance(curve, list)
    assert len(curve) > 0
    assert all(len(p) == 2 for p in curve)


def test_fan_mode_path_consistency(tmp_path: Path, monkeypatch) -> None:
    """omarchy-fan-set and the collector must resolve the same mode path.

    This is the HIGH regression: the collector's env used to drop
    XDG_RUNTIME_DIR, so it read ~/.local/run while the setter wrote
    /run/user/<uid> — fan_mode was "auto" forever.
    """
    stats = load(STATS, "system_monitor_stats")
    setter = load_fan_set()

    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    setter.write_mode("high")

    expected = tmp_path / "omarchy-fan" / "current_fan_mode"
    assert expected.read_text() == "high"
    assert stats._runtime_dir() == tmp_path / "omarchy-fan"
    assert stats.read_fan_mode() == "high"


def test_fan_mode_fallback_path_consistency(tmp_path: Path, monkeypatch) -> None:
    """With no XDG_RUNTIME_DIR both helpers fall back to ~/.local/run."""
    stats = load(STATS, "system_monitor_stats")
    setter = load_fan_set()

    monkeypatch.delenv("XDG_RUNTIME_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    setter.write_mode("low")

    expected = tmp_path / ".local" / "run" / "omarchy-fan" / "current_fan_mode"
    assert expected.read_text() == "low"
    assert stats.read_fan_mode() == "low"


def test_read_fan_mode_validation(tmp_path: Path) -> None:
    stats = load(STATS, "system_monitor_stats")
    # Missing file -> auto
    assert stats.read_fan_mode(tmp_path / "absent") == "auto"
    # Unrecognized content fails safe to auto
    bad = tmp_path / "bad_mode"
    bad.write_text("ludicrous")
    assert stats.read_fan_mode(bad) == "auto"
    # Forward-compat custom-<name> strings are passed through
    named = tmp_path / "named_mode"
    named.write_text("custom-silent")
    assert stats.read_fan_mode(named) == "custom-silent"


def test_fan_control_gated_on_capability(tmp_path: Path, monkeypatch) -> None:
    """fan_control must reflect real capability, not just helper presence."""
    stats = load(STATS, "system_monitor_stats")
    monkeypatch.setattr(stats, "is_daemon_running", lambda: False)

    # No daemon and no driveable fan hwmon -> read-only
    assert stats.fan_control_available({}) is False
    # A temp-only sensor is not fan control
    sensor = tmp_path / "hwmon_temp"
    sensor.mkdir()
    (sensor / "temp1_input").write_text("42000")
    assert stats.fan_control_available({"coretemp": sensor}) is False

    # macsmc fan*_target the daemon can drive -> control enabled
    macsmc = tmp_path / "hwmon_macsmc"
    macsmc.mkdir()
    (macsmc / "fan1_target").write_text("2000")
    assert stats.fan_control_available({"macsmc_hwmon": macsmc}) is True

    # dell_smm pwm* the daemon can drive -> control enabled
    dell = tmp_path / "hwmon_dell"
    dell.mkdir()
    (dell / "pwm1").write_text("128")
    assert stats.fan_control_available({"dell_smm": dell}) is True

    # A running daemon consumes the mode file even without fan hwmon
    monkeypatch.setattr(stats, "is_daemon_running", lambda: True)
    assert stats.fan_control_available({}) is True


def test_panel_retains_xdg_runtime_dir() -> None:
    """The collector env must pass XDG_RUNTIME_DIR through, not scrub it."""
    panel = PANEL.read_text()
    assert 'Quickshell.env("XDG_RUNTIME_DIR")' in panel
    assert '"XDG_RUNTIME_DIR": null' not in panel

