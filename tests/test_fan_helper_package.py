"""omarchy-fan-helper package: PKGBUILD, unit, install hook, and plugin pkexec removal."""

from __future__ import annotations

import io
import os
import re
from importlib.machinery import SourceFileLoader
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FAN_DIR = ROOT / "plugins/lukedaduke.fan"
PKG_DIR = ROOT / "packaging/omarchy-fan-helper"
DAEMON = FAN_DIR / "bin/omarchy-fan-daemon"
PANEL = FAN_DIR / "Panel.qml"


def load_daemon():
    return SourceFileLoader("omarchy_fan_daemon_pkg", str(DAEMON)).load_module()


def pkgbuild() -> str:
    return (PKG_DIR / "PKGBUILD").read_text()


def unit() -> str:
    return (PKG_DIR / "omarchy-fan-daemon.service").read_text()


def install_hook() -> str:
    return (PKG_DIR / "omarchy-fan-helper.install").read_text()


def _function_body(script: str, name: str) -> str:
    match = re.search(rf"^{name}\(\)\s*\{{(.*?)^\}}", script, re.S | re.M)
    assert match, f"{name}() missing"
    return match.group(1)


def test_pkgbuild_is_any_arch_and_installs_to_usr_lib() -> None:
    text = pkgbuild()
    assert re.search(r"^pkgname=omarchy-fan-helper$", text, re.M)
    assert re.search(r"^arch=\('any'\)$", text, re.M)
    assert re.search(r"^install=omarchy-fan-helper\.install$", text, re.M)
    assert '"$pkgdir/usr/lib/omarchy-fan/omarchy-fan-daemon"' in text
    assert '"$pkgdir/usr/lib/systemd/system/omarchy-fan-daemon.service"' in text
    assert "plugins/lukedaduke.fan/bin/omarchy-fan-daemon" in text
    assert "/home/" not in text


def test_pkgver_matches_daemon_and_panel_versions() -> None:
    version = re.search(r"^pkgver=(\S+)$", pkgbuild(), re.M).group(1)
    assert version == load_daemon().HELPER_VERSION
    assert f'readonly property string expectedHelperVersion: "{version}"' in PANEL.read_text()


def test_packaged_unit_runs_from_usr_lib_and_hands_back() -> None:
    text = unit()
    assert "ExecStart=/usr/lib/omarchy-fan/omarchy-fan-daemon run" in text
    assert "ExecStopPost=/usr/lib/omarchy-fan/omarchy-fan-daemon handback" in text
    assert "RuntimeDirectory=omarchy-fan" in text
    assert "RuntimeDirectoryMode=0755" in text
    assert "/home" not in text
    assert "OMARCHY_FAN_UID" not in text


def test_unit_moved_out_of_plugin() -> None:
    assert not (FAN_DIR / "omarchy-fan-daemon.service").exists()
    assert not (FAN_DIR / "bin/omarchy-fan-daemon-start").exists()


def test_install_hook_migrates_and_remove_hands_back() -> None:
    hook = install_hook()
    for fn in ("post_install", "post_upgrade"):
        assert "/usr/lib/omarchy-fan/omarchy-fan-daemon migrate-legacy-unit" in _function_body(hook, fn)
    remove = _function_body(hook, "pre_remove")
    assert "systemctl disable --now omarchy-fan-daemon.service" in remove
    assert "/usr/lib/omarchy-fan/omarchy-fan-daemon handback" in remove
    assert remove.index("disable --now") < remove.index("handback")


def _legacy_tree(root: Path, exec_start: str) -> Path:
    unit_dir = root / "etc/systemd/system"
    unit_dir.mkdir(parents=True)
    legacy = unit_dir / "omarchy-fan-daemon.service"
    legacy.write_text(
        "[Service]\n"
        f"ExecStart={exec_start} --uid 1000\n"
        "Environment=\"OMARCHY_FAN_UID=1000\"\n"
    )
    param = root / "sys/module/macsmc_hwmon/parameters"
    param.mkdir(parents=True)
    (param / "fan_control").write_text("Y\n")
    hwmon = root / "sys/class/hwmon/hwmon2"
    hwmon.mkdir(parents=True)
    (hwmon / "name").write_text("macsmc_hwmon\n")
    return legacy


def test_install_hook_replaces_hand_installed_home_unit(tmp_path: Path) -> None:
    daemon = load_daemon()
    plugin_bin = tmp_path / "home/someone/.config/omarchy/plugins/lukedaduke.fan/bin"
    plugin_bin.mkdir(parents=True)  # owned by the (non-root) test user
    (plugin_bin / "omarchy-fan-daemon").write_text("")
    legacy = _legacy_tree(
        tmp_path,
        "/home/someone/.config/omarchy/plugins/lukedaduke.fan/bin/omarchy-fan-daemon",
    )
    calls: list[list[str]] = []
    out = io.StringIO()

    replaced = daemon.migrate_legacy_unit(tmp_path, run=lambda argv, **_k: calls.append(argv), out=out)

    assert replaced is True
    assert not legacy.exists()
    assert ["/usr/bin/systemctl", "disable", "--now", "omarchy-fan-daemon.service"] in calls
    assert calls.index(["/usr/bin/systemctl", "disable", "--now", "omarchy-fan-daemon.service"]) < \
        calls.index(["/usr/bin/systemctl", "enable", "--now", "omarchy-fan-daemon.service"])
    assert "replaced hand-installed" in out.getvalue()
    # The old daemon had no hand-back: the migration returns fans to firmware.
    assert (tmp_path / "sys/module/macsmc_hwmon/parameters/fan_control").read_text() == "N"


def test_install_hook_keeps_root_owned_unit(tmp_path: Path, monkeypatch) -> None:
    daemon = load_daemon()
    legacy = _legacy_tree(tmp_path, "/usr/lib/omarchy-fan/omarchy-fan-daemon")
    exe = tmp_path / "usr/lib/omarchy-fan/omarchy-fan-daemon"
    exe.parent.mkdir(parents=True)
    exe.write_text("")
    real_stat = os.lstat
    # Fixture files belong to the test user; report every component as root-owned.
    monkeypatch.setattr(
        daemon.os, "lstat",
        lambda p, *a, **k: os.stat_result((real_stat(p).st_mode, 0, 0, 1, 0, 0, 0, 0, 0, 0)),
    )
    calls: list[list[str]] = []
    replaced = daemon.migrate_legacy_unit(tmp_path, run=lambda argv, **_k: calls.append(argv), out=io.StringIO())
    assert replaced is False
    assert legacy.exists()
    assert calls == []


def test_plugin_has_no_pkexec_invocation() -> None:
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in [PANEL, *sorted((FAN_DIR / "bin").iterdir())]
        if path.is_file() and "pkexec" in path.read_text(errors="replace")
    ]
    assert offenders == []


def test_panel_reads_helper_status_and_hides_controls() -> None:
    panel = PANEL.read_text()
    assert 'path: "/run/omarchy-fan/status.json"' in panel
    assert "omarchy-fan-helper package" in panel
    assert "omarchy-fan-daemon-start" not in panel
    # Mode buttons only exist when the helper says a fan target is writable.
    assert re.search(r"Row \{\s*width: parent.width\s*spacing: Style.space\(6\)\s*visible: root.fanControl\s*Repeater \{\s*model: \[\"auto\"", panel)


def test_panel_heartbeat_is_a_spawn_free_filewrite() -> None:
    panel = PANEL.read_text()
    block = re.search(r"FileView \{\s*id: heartbeatFile(.*?)\n  \}", panel, re.S)
    assert block, "heartbeat FileView missing"
    assert "path: root.heartbeatPath" in block.group(1)
    assert re.search(r'heartbeatPath: \{[^}]*XDG_RUNTIME_DIR[^}]*"/omarchy-fan/heartbeat"', panel)
    timer = re.search(r"Timer \{\s*id: heartbeatTimer(.*?)\n  \}", panel, re.S)
    assert timer, "heartbeat Timer missing"
    body = timer.group(1)
    assert "interval: 30000" in body
    assert re.search(r"running: root\.heartbeatPath\.length > 0 && root\.fanControl", body)
    assert "heartbeatFile.setText(" in panel
    assert "execDetached" not in body and "Process" not in body


def test_panel_pending_mode_guard_hint_and_auto_reset() -> None:
    panel = PANEL.read_text()
    read = re.search(r"function readHelperStatus\(.*?\n  \}\n", panel, re.S)
    assert read, "readHelperStatus missing"
    assert "pendingMode" in read.group(0) and "pendingUntil" in read.group(0)
    assert re.search(r"helperModeActive && root\.pendingMode\.length === 0", read.group(0))
    for fn in ("setMode", "setCustom"):
        body = re.search(r"function %s\(.*?\n  \}\n" % fn, panel, re.S).group(0)
        assert "pendingUntil = Date.now()" in body
    assert "systemctl enable --now omarchy-fan-daemon.service" in panel
    # auto reset stays reachable when the helper exists but fanControl is false.
    assert 'mode === "auto" && root.helperState !== "missing"' in panel
    assert 'root.setMode("auto")' in panel
