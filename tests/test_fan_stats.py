from __future__ import annotations

import importlib.util
import json
import os
import signal
import subprocess
import sys
import time
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
    data, caps = stats.build("full")
    assert 0 <= data["mem"]["pct"] <= 100
    assert 0 <= data["cpu"]["load"] <= 100
    assert data["temp"]["c"] is None or isinstance(data["temp"]["c"], int)
    assert isinstance(caps["fan_control"], bool)
    json.dumps(data)


def test_empty_hwmon_temps() -> None:
    stats = load(STATS, "system_monitor_stats")
    temps = stats.temperatures([])
    assert temps["cpu"] is None
    assert temps["headline"] == {"c": None, "source": "none", "label": ""}
    assert stats.fans([]) == []
    assert stats.nvme_temp([]) is None


def test_kill_refuses_pid_one() -> None:
    kill = load(KILL, "kill_proc")
    for pid in (0, 1):
        env = kill.envelope.wrap(lambda: kill.kill(pid))
        assert env["ok"] is False and env["error"] == "refused"
    env = kill.envelope.wrap(lambda: kill.parse([]))
    assert env["ok"] is False and env["error"] == "usage"


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


def hwmon_tree(root: Path, name: str, files: dict[str, str]) -> Path:
    """A one-device sysfs fixture tree under root."""
    base = root / "sys/class/hwmon/hwmon0"
    base.mkdir(parents=True)
    (base / "name").write_text(name + "\n")
    for key, value in files.items():
        (base / key).write_text(value + "\n")
    return base


def test_fan_control_gated_on_capability(tmp_path: Path) -> None:
    """fan_control must reflect real capability, not just helper presence."""
    stats = load(STATS, "system_monitor_stats")

    def devices(root: Path):
        return stats.sysfs.hwmon_devices(root)

    # No driveable fan hwmon -> read-only; a temp-only sensor is not fan control.
    assert stats.fan_control_available([]) is False
    temp_only = tmp_path / "temp_only"
    hwmon_tree(temp_only, "coretemp", {"temp1_input": "42000"})
    assert stats.fan_control_available(devices(temp_only)) is False

    # macsmc fan*_target the daemon can drive -> control enabled
    mac = tmp_path / "mac"
    hwmon_tree(mac, "macsmc_hwmon", {"fan1_target": "2000"})
    assert stats.fan_control_available(devices(mac)) is True

    # dell_smm pwm* the daemon can drive -> control enabled
    dell = tmp_path / "dell"
    hwmon_tree(dell, "dell_smm", {"pwm1": "128"})
    assert stats.fan_control_available(devices(dell)) is True


def test_soc_power_w_heatpipe(tmp_path: Path) -> None:
    stats = load(STATS, "system_monitor_stats")
    hwmon_tree(tmp_path, "macsmc_hwmon", {
        "power4_input": "15973271", "power4_label": "Heatpipe Power",
        "power2_input": "86718147", "power2_label": "AC Input Power",
    })
    assert stats.soc_power_w(stats.sysfs.hwmon_devices(tmp_path)) == 16.0


def test_soc_power_w_absent(tmp_path: Path) -> None:
    stats = load(STATS, "system_monitor_stats")
    hwmon_tree(tmp_path, "macsmc_hwmon", {"power1_input": "1000000", "power1_label": "Total System Power"})
    assert stats.soc_power_w(stats.sysfs.hwmon_devices(tmp_path)) is None
    assert stats.soc_power_w([]) is None


def test_gpu_clients_shape() -> None:
    stats = load(STATS, "system_monitor_stats")
    procs = stats.scan_processes(Path("/proc"))
    clients = stats.gpu_clients(Path("/proc"), procs)
    assert isinstance(clients, list)
    for c in clients:
        assert isinstance(c["label"], str) and c["label"]
        assert isinstance(c["count"], int) and c["count"] >= 1


def test_collect_gpu_fields() -> None:
    stats = load(STATS, "system_monitor_stats")
    data, caps = stats.build("full")
    gpu = data["gpu"]
    assert gpu["load"] is None or isinstance(gpu["load"], int)
    assert isinstance(gpu["reason"], str)
    assert gpu["power_w"] is None or isinstance(gpu["power_w"], float)
    assert isinstance(gpu["clients"], list)
    assert caps["gpu_load"] is (gpu["load"] is not None)
    json.dumps(data)


def test_panel_retains_xdg_runtime_dir() -> None:
    """The collector env must pass XDG_RUNTIME_DIR through, not scrub it."""
    panel = PANEL.read_text()
    assert 'Quickshell.env("XDG_RUNTIME_DIR")' in panel
    assert '"XDG_RUNTIME_DIR": null' not in panel


def test_daemon_does_not_invent_a_target_user(monkeypatch) -> None:
    from importlib.machinery import SourceFileLoader

    daemon_path = ROOT / "plugins/lukedaduke.fan/bin/omarchy-fan-daemon"
    daemon = SourceFileLoader("omarchy_fan_daemon_unknown_uid", str(daemon_path)).load_module()
    monkeypatch.delenv("OMARCHY_FAN_UID", raising=False)
    monkeypatch.delenv("SUDO_UID", raising=False)  # guards that SUDO_UID is ignored
    monkeypatch.setattr(daemon.os, "getuid", lambda: 0)
    monkeypatch.setattr(daemon, "_active_run_user", lambda *_a: None)

    assert daemon.target_uid() == -1


# --- Fan daemon characterization (fixture sysfs trees) ----------------------
#
# These tests characterize the daemon against fixture sysfs trees; each one
# pins the tuned curve, smoothing and hwmon writes.

DAEMON = FAN_DIR / "bin/omarchy-fan-daemon"


def load_daemon(name: str = "omarchy_fan_daemon_fixture"):
    return SourceFileLoader(name, str(DAEMON)).load_module()


def make_macsmc(root: Path, fan_control: str = "N") -> Path:
    hwmon = root / "sys/class/hwmon/hwmon2"
    hwmon.mkdir(parents=True)
    (hwmon / "name").write_text("macsmc_hwmon\n")
    for name, value in {
        "fan1_min": "1499", "fan1_max": "4296",
        "fan2_min": "1499", "fan2_max": "4744",
        "fan1_target": "0", "fan2_target": "0",
    }.items():
        (hwmon / name).write_text(value + "\n")
    param = root / "sys/module/macsmc_hwmon/parameters"
    param.mkdir(parents=True)
    (param / "fan_control").write_text(fan_control + "\n")
    return hwmon


def make_dell(root: Path, pwm1_mode: int = 0o644) -> Path:
    hwmon = root / "sys/class/hwmon/hwmon3"
    hwmon.mkdir(parents=True)
    (hwmon / "name").write_text("dell_smm\n")
    for n in (1, 2):
        (hwmon / f"pwm{n}").write_text("128\n")
        (hwmon / f"pwm{n}_enable").write_text("2\n")
    (hwmon / "pwm1").chmod(pwm1_mode)
    return hwmon


def set_temp(root: Path, celsius: int) -> None:
    zone = root / "sys/class/thermal/thermal_zone0"
    zone.mkdir(parents=True, exist_ok=True)
    (zone / "temp").write_text(f"{celsius * 1000}\n")


def fan_control_param(root: Path) -> str:
    return (root / "sys/module/macsmc_hwmon/parameters/fan_control").read_text().strip()


def test_char_auto_curve_points() -> None:
    daemon = load_daemon()
    assert daemon.curve_pwm(35, daemon.AUTO_CURVE) == 0
    assert daemon.curve_pwm(40, daemon.AUTO_CURVE) == 0
    assert daemon.curve_pwm(44, daemon.AUTO_CURVE) == 35
    assert daemon.curve_pwm(50, daemon.AUTO_CURVE) == 92
    assert daemon.curve_pwm(70, daemon.AUTO_CURVE) == 255
    assert daemon.curve_pwm(50, [[60, 200], [40, 100]]) == 150  # unsorted input


def test_char_smoother_ramp_and_deadband() -> None:
    daemon = load_daemon()
    s = daemon.FanSmoother()
    assert s.smooth_temp(70) == 70.0
    assert s.smooth_temp(40) == 70.0 + 0.30 * (40 - 70.0)
    assert s.slew_pwm(255) == 12
    assert s.slew_pwm(255) == 24
    s.pwm = 100
    assert s.slew_pwm(0) == 96          # slow fall
    assert s.slew_pwm(97) == 96         # inside the deadband


def test_char_macsmc_floor_hands_back(tmp_path: Path) -> None:
    daemon = load_daemon()
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    (hwmon / "fan1_target").write_text("3000")
    daemon.set_fan_speed("macsmc", hwmon, 0, root=tmp_path)
    assert fan_control_param(tmp_path) == "N"
    assert (hwmon / "fan1_target").read_text() == "0"
    assert (hwmon / "fan2_target").read_text() == "0"


def test_char_macsmc_ramp_targets(tmp_path: Path) -> None:
    daemon = load_daemon()
    hwmon = make_macsmc(tmp_path, fan_control="N")
    daemon.set_fan_speed("macsmc", hwmon, 12, root=tmp_path)
    assert fan_control_param(tmp_path) == "Y"
    assert (hwmon / "fan1_target").read_text() == "1631"
    assert (hwmon / "fan2_target").read_text() == "1652"


def test_char_dell_manual_write(tmp_path: Path) -> None:
    daemon = load_daemon()
    hwmon = make_dell(tmp_path)
    daemon.set_fan_speed("dell", hwmon, 200, root=tmp_path)
    for n in (1, 2):
        assert (hwmon / f"pwm{n}_enable").read_text() == "1"
        assert (hwmon / f"pwm{n}").read_text() == "200"


# --- Packaged helper behavior: hand-back, heartbeat, status ------------------

def stat_mode(path: Path) -> int:
    return path.stat().st_mode & 0o777


def user_runtime(root: Path, uid: int | None = None) -> Path:
    uid = os.getuid() if uid is None else uid
    rdir = root / f"run/user/{uid}/omarchy-fan"
    rdir.mkdir(parents=True, exist_ok=True)
    return rdir


def request_mode(root: Path, mode: str, heartbeat_age: float | None) -> Path:
    rdir = user_runtime(root)
    (rdir / "current_fan_mode").write_text(mode)
    if heartbeat_age is not None:
        hb = rdir / "heartbeat"
        hb.write_text("1")
        stamp = time.time() - heartbeat_age
        os.utime(hb, (stamp, stamp))
    return rdir


def helper(root: Path):
    daemon = load_daemon("omarchy_fan_daemon_helper")
    return daemon, daemon.FanHelper(root=root, uid=os.getuid())


def status(root: Path) -> dict:
    return json.loads((root / "run/omarchy-fan/status.json").read_text())


def test_auto_curve_floor_at_35c(tmp_path: Path) -> None:
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    (hwmon / "fan1_target").write_text("3000")
    set_temp(tmp_path, 35)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert fan_control_param(tmp_path) == "N"
    assert (hwmon / "fan1_target").read_text() == "0"
    assert (hwmon / "fan2_target").read_text() == "0"


def test_auto_curve_smoothed_ramp_at_70c(tmp_path: Path) -> None:
    hwmon = make_macsmc(tmp_path, fan_control="N")
    set_temp(tmp_path, 70)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert fan_control_param(tmp_path) == "Y"
    assert (hwmon / "fan1_target").read_text() == "1631"
    assert (hwmon / "fan2_target").read_text() == "1652"
    h.tick()
    assert (hwmon / "fan1_target").read_text() == "1762"  # pwm 24: still ramping


def test_unclean_exit_marker_hands_back_before_curve(tmp_path: Path) -> None:
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    set_temp(tmp_path, 70)
    state = tmp_path / "run/omarchy-fan"
    state.mkdir(parents=True)
    (state / "running").write_text("1")
    _, h = helper(tmp_path)
    h.startup()
    assert fan_control_param(tmp_path) == "N"   # handed back first
    h.tick()
    assert fan_control_param(tmp_path) == "Y"   # then the curve resumes
    assert (hwmon / "fan1_target").read_text() == "1631"


def test_clean_start_does_not_touch_fans(tmp_path: Path) -> None:
    make_macsmc(tmp_path, fan_control="Y")
    _, h = helper(tmp_path)
    h.startup()
    assert fan_control_param(tmp_path) == "Y"
    assert (tmp_path / "run/omarchy-fan/running").is_file()


def test_status_reports_version_mode_controllable(tmp_path: Path) -> None:
    make_macsmc(tmp_path)
    set_temp(tmp_path, 40)
    daemon, h = helper(tmp_path)
    h.startup()
    h.tick()
    data = status(tmp_path)
    assert data["version"] == daemon.HELPER_VERSION
    assert data["mode"] == "auto"
    assert data["controllable"] is True
    assert stat_mode(tmp_path / "run/omarchy-fan/status.json") == 0o644


def test_stale_heartbeat_expires_fixed_preset(tmp_path: Path) -> None:
    hwmon = make_macsmc(tmp_path)
    set_temp(tmp_path, 35)
    request_mode(tmp_path, "high", heartbeat_age=150)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["mode"] == "auto"
    assert fan_control_param(tmp_path) == "N"      # auto curve floor, not HIGH
    assert (hwmon / "fan1_target").read_text().strip() == "0"


def test_missing_heartbeat_expires_fixed_preset(tmp_path: Path) -> None:
    make_macsmc(tmp_path)
    set_temp(tmp_path, 35)
    request_mode(tmp_path, "med", heartbeat_age=None)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["mode"] == "auto"


def test_fresh_heartbeat_keeps_preset_while_locked(tmp_path: Path) -> None:
    """Locked screen, shell alive: the heartbeat keeps arriving, so HIGH holds."""
    hwmon = make_macsmc(tmp_path)
    set_temp(tmp_path, 35)
    request_mode(tmp_path, "high", heartbeat_age=25)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["mode"] == "high"
    assert fan_control_param(tmp_path) == "Y"
    assert (hwmon / "fan1_target").read_text() == "4296"


def test_auto_curve_ignores_stale_heartbeat(tmp_path: Path) -> None:
    hwmon = make_macsmc(tmp_path)
    set_temp(tmp_path, 70)
    request_mode(tmp_path, "auto", heartbeat_age=10_000)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["mode"] == "auto"
    assert (hwmon / "fan1_target").read_text() == "1631"


def test_custom_curve_ignores_stale_heartbeat(tmp_path: Path) -> None:
    make_macsmc(tmp_path)
    set_temp(tmp_path, 70)
    request_mode(tmp_path, "custom", heartbeat_age=10_000)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["mode"] == "custom"


def test_dell_read_only_pwm_is_not_controllable(tmp_path: Path) -> None:
    hwmon = make_dell(tmp_path, pwm1_mode=0o444)
    set_temp(tmp_path, 70)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["controllable"] is False
    assert (hwmon / "pwm1_enable").read_text().strip() == "2"  # never taken over


def test_dell_writable_pwm_is_controllable(tmp_path: Path) -> None:
    hwmon = make_dell(tmp_path)
    set_temp(tmp_path, 70)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    assert status(tmp_path)["controllable"] is True
    assert (hwmon / "pwm1_enable").read_text() == "1"
    assert (hwmon / "pwm1").read_text() == "12"


def test_shutdown_hands_back_dell(tmp_path: Path) -> None:
    hwmon = make_dell(tmp_path)
    set_temp(tmp_path, 70)
    _, h = helper(tmp_path)
    h.startup()
    h.tick()
    h.shutdown()
    assert (hwmon / "pwm1_enable").read_text() == "2"
    assert (hwmon / "pwm2_enable").read_text() == "2"
    assert not (tmp_path / "run/omarchy-fan/running").exists()


def test_daemon_never_writes_platform_profile(tmp_path: Path) -> None:
    assert "platform_profile" not in DAEMON.read_text()
    make_macsmc(tmp_path)
    profile = tmp_path / "sys/firmware/acpi/platform_profile"
    profile.parent.mkdir(parents=True)
    profile.write_text("balanced\n")
    _, h = helper(tmp_path)
    h.startup()
    for celsius in (35, 50, 70):
        set_temp(tmp_path, celsius)
        h.tick()
    request_mode(tmp_path, "high", heartbeat_age=1)
    h.tick()
    h.shutdown()
    assert profile.read_text() == "balanced\n"


def test_daemon_never_opens_user_runtime_for_writing(tmp_path: Path, monkeypatch) -> None:
    make_macsmc(tmp_path)
    set_temp(tmp_path, 70)
    rdir = request_mode(tmp_path, "high", heartbeat_age=1)
    daemon, h = helper(tmp_path)
    writes: list[str] = []
    real_open = os.open
    write_flags = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND

    def spy(path, flags, *args, dir_fd=None, **kw):
        if flags & write_flags:
            base = os.readlink(f"/proc/self/fd/{dir_fd}") if dir_fd is not None else ""
            writes.append(os.path.join(base, os.fsdecode(path)))
        return real_open(path, flags, *args, dir_fd=dir_fd, **kw)

    monkeypatch.setattr(daemon.os, "open", spy)
    before = sorted(p.name for p in rdir.iterdir())
    h.startup()
    h.tick()
    h.shutdown()
    assert writes, "spy saw no writes at all"
    assert not [w for w in writes if "/run/user/" in w]
    assert sorted(p.name for p in rdir.iterdir()) == before


def _wait_for(predicate, timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False


def _run_daemon_until_sigterm(root: Path, ready) -> int:
    proc = subprocess.Popen(
        [sys.executable, str(DAEMON), "run", "--root", str(root), "--uid", str(os.getuid())],
    )
    try:
        assert _wait_for(ready), "daemon never took control"
        proc.send_signal(signal.SIGTERM)
        return proc.wait(timeout=10)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_sigterm_hands_back_macsmc(tmp_path: Path) -> None:
    make_macsmc(tmp_path, fan_control="N")
    set_temp(tmp_path, 70)
    rc = _run_daemon_until_sigterm(tmp_path, lambda: fan_control_param(tmp_path) == "Y")
    assert rc == 0
    assert fan_control_param(tmp_path) == "N"
    assert not (tmp_path / "run/omarchy-fan/running").exists()


def test_sigterm_hands_back_dell(tmp_path: Path) -> None:
    hwmon = make_dell(tmp_path)
    set_temp(tmp_path, 70)
    rc = _run_daemon_until_sigterm(
        tmp_path, lambda: (hwmon / "pwm1_enable").read_text().strip() == "1"
    )
    assert rc == 0
    assert (hwmon / "pwm1_enable").read_text() == "2"
    assert (hwmon / "pwm2_enable").read_text() == "2"


def test_handback_cli_restores_firmware(tmp_path: Path) -> None:
    """ExecStopPost path: a separate process hands back after any exit."""
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    (hwmon / "fan1_target").write_text("3000")
    subprocess.run(
        [sys.executable, str(DAEMON), "handback", "--root", str(tmp_path)], check=True, timeout=30
    )
    assert fan_control_param(tmp_path) == "N"
    assert (hwmon / "fan1_target").read_text() == "0"


def test_setter_refreshes_heartbeat_with_mode(tmp_path: Path, monkeypatch) -> None:
    """Choosing a preset is itself proof of a live shell: no 30 s expiry gap."""
    setter = load_fan_set()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    setter.write_mode("high")
    assert (tmp_path / "omarchy-fan" / "heartbeat").is_file()


# --- Review fixes: macsmc hand-back order, root guard, curve robustness -----

def reject_targets_when_param_off(daemon, monkeypatch, root: Path) -> list[tuple[str, str]]:
    """Model macsmc-hwmon: fanN_target writes fail (-EOPNOTSUPP) once fan_control=N."""
    real = daemon._write_attr
    log: list[tuple[str, str]] = []

    def kernel(path: Path, value: str) -> bool:
        path = Path(path)
        if path.name.endswith("_target") and fan_control_param(root) == "N":
            log.append((path.name, "rejected"))
            return False
        log.append((path.name, value))
        return real(path, value)

    monkeypatch.setattr(daemon, "_write_attr", kernel)
    return log


def test_hand_back_resets_targets_before_dropping_control(tmp_path: Path, monkeypatch) -> None:
    daemon = load_daemon("omarchy_fan_daemon_handback_order")
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    for name in ("fan1_target", "fan2_target"):
        (hwmon / name).write_text("4296")
    log = reject_targets_when_param_off(daemon, monkeypatch, tmp_path)
    daemon.hand_back("macsmc", hwmon, tmp_path)
    assert (hwmon / "fan1_target").read_text() == "0"
    assert (hwmon / "fan2_target").read_text() == "0"
    assert fan_control_param(tmp_path) == "N"
    assert ("fan1_target", "rejected") not in log


def test_hand_back_reenables_control_to_reset_targets(tmp_path: Path, monkeypatch) -> None:
    """Param already N but SMC still manual: flip Y, write 0, flip back to N."""
    daemon = load_daemon("omarchy_fan_daemon_handback_reenable")
    hwmon = make_macsmc(tmp_path, fan_control="N")
    for name in ("fan1_target", "fan2_target"):
        (hwmon / name).write_text("4296")
    reject_targets_when_param_off(daemon, monkeypatch, tmp_path)
    daemon.hand_back("macsmc", hwmon, tmp_path)
    assert (hwmon / "fan1_target").read_text() == "0"
    assert (hwmon / "fan2_target").read_text() == "0"
    assert fan_control_param(tmp_path) == "N"


def test_macsmc_floor_resets_targets_before_dropping_control(tmp_path: Path, monkeypatch) -> None:
    daemon = load_daemon("omarchy_fan_daemon_floor_order")
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    for name in ("fan1_target", "fan2_target"):
        (hwmon / name).write_text("3000")
    reject_targets_when_param_off(daemon, monkeypatch, tmp_path)
    daemon.set_fan_speed("macsmc", hwmon, 0, root=tmp_path)
    assert (hwmon / "fan1_target").read_text() == "0"
    assert (hwmon / "fan2_target").read_text() == "0"
    assert fan_control_param(tmp_path) == "N"


def _root_guard_daemon(monkeypatch, user_owned: bool):
    daemon = load_daemon("omarchy_fan_daemon_root_guard")
    calls: list[str] = []
    monkeypatch.setattr(daemon.os, "geteuid", lambda: 0)
    monkeypatch.setattr(daemon, "_user_owned", lambda *_a: user_owned)
    monkeypatch.setattr(daemon.FanHelper, "release_fans", lambda self: calls.append("release"))
    monkeypatch.setattr(daemon, "run_loop", lambda helper: calls.append("run_loop"))
    monkeypatch.setattr(daemon, "migrate_legacy_unit", lambda *a, **k: calls.append("migrate") or True)
    return daemon, calls


def test_root_from_user_owned_path_refuses_after_hand_back(monkeypatch, capsys) -> None:
    for argv in (["--uid", "1000"], ["run"], ["handback"], ["migrate-legacy-unit"]):
        daemon, calls = _root_guard_daemon(monkeypatch, user_owned=True)
        rc = daemon.main(argv)
        assert rc != 0, argv
        assert calls == ["release"], argv
        assert "refusing to run as root from a user-owned path" in capsys.readouterr().err


def test_root_from_package_path_proceeds(monkeypatch) -> None:
    daemon, calls = _root_guard_daemon(monkeypatch, user_owned=False)
    assert daemon.main(["--uid", "1000"]) == 0
    assert calls == ["run_loop"]


TESTER_HOME = Path("/home") / "tester"


class FakeAccount:
    """Stands in for a pwd entry; only the home directory is read."""

    pw_dir = str(TESTER_HOME)


def fake_home(monkeypatch, root: Path) -> Path:
    import pwd
    monkeypatch.setattr(pwd, "getpwuid", lambda _uid: FakeAccount())
    cdir = root / "home/tester/.config/omarchy"
    cdir.mkdir(parents=True, exist_ok=True)
    return cdir


def test_overflowing_custom_curve_falls_back_to_default(tmp_path: Path, monkeypatch) -> None:
    make_macsmc(tmp_path)
    set_temp(tmp_path, 70)
    (fake_home(monkeypatch, tmp_path) / "fan_curve.json").write_text("[[1e400, 1]]")
    request_mode(tmp_path, "custom", heartbeat_age=1)
    daemon, h = helper(tmp_path)
    assert daemon.load_curve(os.getuid(), tmp_path) == daemon.DEFAULT_CURVE
    h.startup()
    assert h.tick() == "custom"


def test_custom_curve_points_are_clamped(tmp_path: Path, monkeypatch) -> None:
    (fake_home(monkeypatch, tmp_path) / "fan_curve.json").write_text("[[-40, -5], [500, 999]]")
    daemon = load_daemon("omarchy_fan_daemon_clamp")
    assert daemon.load_curve(os.getuid(), tmp_path) == [[0, 0], [120, 255]]


def test_run_loop_survives_a_failing_tick(monkeypatch, capsys) -> None:
    daemon = load_daemon("omarchy_fan_daemon_loop")
    events: list[str] = []

    class Helper:
        ticks = 0

        def startup(self):
            events.append("startup")

        def tick(self):
            self.ticks += 1
            if self.ticks == 1:
                raise RuntimeError("boom")
            raise SystemExit(0)

        def shutdown(self):
            events.append("shutdown")

    monkeypatch.setattr(daemon.signal, "signal", lambda *_a: None)
    monkeypatch.setattr(daemon.time, "sleep", lambda _s: None)
    h = Helper()
    try:
        daemon.run_loop(h)
    except SystemExit:
        pass
    assert h.ticks == 2
    assert events == ["startup", "shutdown"]
    assert len(capsys.readouterr().err.strip().splitlines()) == 1


def rpm1(pwm: int) -> int:
    return round(1499 + (4296 - 1499) * pwm / 255)


def test_preset_expiry_falls_gradually(tmp_path: Path) -> None:
    for celsius in (50, 70):
        root = tmp_path / str(celsius)
        hwmon = make_macsmc(root)
        set_temp(root, celsius)
        rdir = request_mode(root, "high", heartbeat_age=1)
        daemon, h = helper(root)
        h.startup()
        h.tick()
        assert (hwmon / "fan1_target").read_text() == "4296"
        stamp = time.time() - 150
        os.utime(rdir / "heartbeat", (stamp, stamp))
        assert h.tick() == "auto"
        assert int((hwmon / "fan1_target").read_text()) >= rpm1(255 - daemon.PWM_FALL_STEP)


# --- Descriptor guards (fixture trees) --------------------------------------

def test_mode_file_symlink_is_ignored(tmp_path: Path) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard")
    rdir = user_runtime(tmp_path)
    (tmp_path / "elsewhere").write_text("high")
    (rdir / "current_fan_mode").symlink_to(tmp_path / "elsewhere")
    assert daemon.get_requested_mode(os.getuid(), tmp_path) == "auto"


def test_runtime_dir_symlink_is_ignored(tmp_path: Path) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard")
    real = tmp_path / "real"
    real.mkdir()
    (real / "current_fan_mode").write_text("high")
    (tmp_path / f"run/user/{os.getuid()}").mkdir(parents=True)
    (tmp_path / f"run/user/{os.getuid()}/omarchy-fan").symlink_to(real)
    assert daemon.get_requested_mode(os.getuid(), tmp_path) == "auto"


def test_foreign_owned_runtime_dir_is_ignored(tmp_path: Path) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard")
    other = os.getuid() + 1
    rdir = user_runtime(tmp_path, other)   # owned by us, not by ``other``
    (rdir / "current_fan_mode").write_text("high")
    (rdir / "heartbeat").write_text("1")
    assert daemon.get_requested_mode(other, tmp_path) == "auto"
    assert daemon.heartbeat_age(other, tmp_path) is None


def _foreign_regular_files(daemon, monkeypatch) -> None:
    """Report every regular file as owned by someone else (dirs stay ours)."""
    import stat as stat_mod
    real_fstat = os.fstat

    class Foreign:
        def __init__(self, st):
            self._st = st
            self.st_uid = st.st_uid + 1

        def __getattr__(self, name):
            return getattr(self._st, name)

    def fstat(fd):
        st = real_fstat(fd)
        return Foreign(st) if stat_mod.S_ISREG(st.st_mode) else st

    monkeypatch.setattr(daemon.os, "fstat", fstat)


def test_foreign_owned_files_are_ignored(tmp_path: Path, monkeypatch) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard_foreign")
    rdir = request_mode(tmp_path, "high", heartbeat_age=1)
    (fake_home(monkeypatch, tmp_path) / "fan_curve.json").write_text("[[0, 10], [100, 20]]")
    assert daemon.get_requested_mode(os.getuid(), tmp_path) == "high"   # sanity
    _foreign_regular_files(daemon, monkeypatch)
    assert daemon.get_requested_mode(os.getuid(), tmp_path) == "auto"
    assert daemon.heartbeat_age(os.getuid(), tmp_path) is None
    assert daemon.load_curve(os.getuid(), tmp_path) == daemon.DEFAULT_CURVE
    assert rdir.is_dir()


def test_oversized_mode_file_is_ignored(tmp_path: Path) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard")
    rdir = user_runtime(tmp_path)
    (rdir / "current_fan_mode").write_text("high" + " " * 70)
    assert daemon.get_requested_mode(os.getuid(), tmp_path) == "auto"


def test_heartbeat_symlink_is_ignored(tmp_path: Path) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard")
    rdir = user_runtime(tmp_path)
    (tmp_path / "beat").write_text("1")
    (rdir / "heartbeat").symlink_to(tmp_path / "beat")
    assert daemon.heartbeat_age(os.getuid(), tmp_path) is None


def test_fan_curve_symlink_and_oversize_are_ignored(tmp_path: Path, monkeypatch) -> None:
    daemon = load_daemon("omarchy_fan_daemon_guard")
    cdir = fake_home(monkeypatch, tmp_path)
    curve = "[[0, 10], [100, 20]]"
    (cdir / "fan_curve.json").write_text(curve)
    assert daemon.load_curve(os.getuid(), tmp_path) == [[0, 10], [100, 20]]   # sanity
    (cdir / "fan_curve.json").unlink()
    (tmp_path / "curve.json").write_text(curve)
    (cdir / "fan_curve.json").symlink_to(tmp_path / "curve.json")
    assert daemon.load_curve(os.getuid(), tmp_path) == daemon.DEFAULT_CURVE
    (cdir / "fan_curve.json").unlink()
    (cdir / "fan_curve.json").write_text(curve + " " * 70_000)
    assert daemon.load_curve(os.getuid(), tmp_path) == daemon.DEFAULT_CURVE


def test_custom_mode_follows_fixture_curve(tmp_path: Path, monkeypatch) -> None:
    """A flat-zero user curve at 70C floors the fans; AUTO/DEFAULT would ramp."""
    hwmon = make_macsmc(tmp_path, fan_control="Y")
    for name in ("fan1_target", "fan2_target"):
        (hwmon / name).write_text("3000")
    set_temp(tmp_path, 70)
    (fake_home(monkeypatch, tmp_path) / "fan_curve.json").write_text("[[0, 0], [120, 0]]")
    request_mode(tmp_path, "custom", heartbeat_age=None)
    _, h = helper(tmp_path)
    h.startup()
    assert h.tick() == "custom"
    assert fan_control_param(tmp_path) == "N"
    assert (hwmon / "fan1_target").read_text() == "0"


def test_foreign_owned_dirs_are_ignored(tmp_path: Path, monkeypatch) -> None:
    """Directory owner check alone: files look ours, the dirs do not."""
    import stat as stat_mod
    daemon = load_daemon("omarchy_fan_daemon_guard_dirs")
    request_mode(tmp_path, "high", heartbeat_age=1)
    (fake_home(monkeypatch, tmp_path) / "fan_curve.json").write_text("[[0, 10], [100, 20]]")
    real_fstat = os.fstat

    class Foreign:
        def __init__(self, st):
            self._st = st
            self.st_uid = st.st_uid + 1

        def __getattr__(self, name):
            return getattr(self._st, name)

    def fstat(fd):
        st = real_fstat(fd)
        return Foreign(st) if stat_mod.S_ISDIR(st.st_mode) else st

    monkeypatch.setattr(daemon.os, "fstat", fstat)
    assert daemon.get_requested_mode(os.getuid(), tmp_path) == "auto"
    assert daemon.heartbeat_age(os.getuid(), tmp_path) is None
    assert daemon.load_curve(os.getuid(), tmp_path) == daemon.DEFAULT_CURVE
