"""Tests for the shared helper library shared/py/_omplug (U4)."""

from __future__ import annotations

import json
import os
import stat
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "shared" / "py"))

from _omplug import envelope, fsio, proc, sysfs, text  # noqa: E402


# --- proc -----------------------------------------------------------------

def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # A zombie still answers kill(0); treat it as dead.
    try:
        with open(f"/proc/{pid}/stat") as fh:
            return fh.read().split(") ")[-1][:1] != "Z"
    except OSError:
        return False


def test_safe_path_never_starts_with_user_bin() -> None:
    first = proc.SAFE_PATH.split(":")[0]
    assert first.startswith("/usr/") or first in ("/bin", "/sbin")
    assert ".local" not in proc.SAFE_PATH


def test_tool_resolves_only_under_fixed_path(tmp_path: Path, monkeypatch) -> None:
    fake = tmp_path / "evilbin"
    fake.mkdir()
    exe = fake / "sh"
    exe.write_text("#!/bin/sh\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{fake}:{os.environ.get('PATH', '')}")
    found = proc.tool("sh")
    assert found is not None and not found.startswith(str(fake))
    # Extra dirs are searched only after the system dirs.
    assert proc.tool("sh", extra_dirs=[str(fake)]) != str(exe)
    exe2 = fake / "omplug-only-here"
    exe2.write_text("#!/bin/sh\n")
    exe2.chmod(0o755)
    assert proc.tool("omplug-only-here") is None
    assert proc.tool("omplug-only-here", extra_dirs=[str(fake)]) == str(exe2)


def test_run_uses_minimal_env(monkeypatch) -> None:
    monkeypatch.setenv("OMPLUG_SECRET", "leak")
    res = proc.run([proc.tool("env")], timeout=5)
    assert res.ok and res.error is None
    names = {line.split("=", 1)[0] for line in res.out.splitlines() if "=" in line}
    assert "OMPLUG_SECRET" not in names
    assert "PATH=" + proc.SAFE_PATH in res.out.splitlines()


def test_run_kills_whole_group_at_deadline(tmp_path: Path) -> None:
    pidfile = tmp_path / "pids"
    script = f"sleep 30 & echo $! > {pidfile}; sleep 30"
    start = time.monotonic()
    res = proc.run([proc.tool("sh"), "-c", script], timeout=0.7)
    assert time.monotonic() - start < 5
    assert res.error == "timeout" and res.timed_out and not res.ok
    grandchild = int(pidfile.read_text().strip())
    deadline = time.monotonic() + 2
    while _alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(grandchild)


def test_run_kills_grandchild_holding_pipe_after_parent_exits(tmp_path: Path) -> None:
    pidfile = tmp_path / "pids"
    script = f"sleep 30 & echo $! > {pidfile}"
    res = proc.run([proc.tool("sh"), "-c", script], timeout=0.7)
    assert res.error == "timeout"
    grandchild = int(pidfile.read_text().strip())
    deadline = time.monotonic() + 2
    while _alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(grandchild)


def test_run_truncates_at_max_bytes_and_reports_it() -> None:
    res = proc.run([proc.tool("sh"), "-c", "yes x | head -c 100000"], timeout=5, max_bytes=1000)
    assert res.truncated
    assert res.error == "output_too_large" and not res.ok
    assert len(res.out) == 1000 and set(res.out) <= {"x", "\n"}


def test_run_reports_exit_status_and_stderr() -> None:
    res = proc.run([proc.tool("sh"), "-c", "echo out; echo err >&2; exit 3"], timeout=5, stderr=True)
    assert res.rc == 3 and res.out == "out\n" and res.err == "err\n"
    assert res.error is None and not res.truncated


def test_run_rejects_empty_and_missing() -> None:
    assert proc.run([]).error == "empty_argv"
    assert proc.run([None]).error == "empty_argv"
    assert proc.run(["/nonexistent/omplug-bin"]).error == "spawn_failed"


# --- fsio -----------------------------------------------------------------

def test_publish_writes_0600_atomically(tmp_path: Path) -> None:
    fsio.publish(tmp_path, "state.json", '{"a":1}')
    target = tmp_path / "state.json"
    assert target.read_text() == '{"a":1}'
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    fsio.publish(tmp_path, "state.json", b"two")
    assert target.read_bytes() == b"two"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["state.json"]


def test_publish_refuses_symlinked_directory(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)
    with pytest.raises(OSError):
        fsio.publish(link, "state.json", "x")
    assert not (real / "state.json").exists()


def test_publish_rejects_path_names(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
    for bad in ("sub/x", "..", "", "."):
        with pytest.raises(ValueError):
            fsio.publish(tmp_path, bad, "x")


def test_read_capped(tmp_path: Path) -> None:
    (tmp_path / "small").write_bytes(b"hello")
    (tmp_path / "big").write_bytes(b"x" * 100)
    (tmp_path / "link").symlink_to(tmp_path / "small")
    assert fsio.read_capped(tmp_path, "small", 10) == b"hello"
    assert fsio.read_capped(tmp_path, "big", 10) is None
    assert fsio.read_capped(tmp_path, "link", 10) is None
    assert fsio.read_capped(tmp_path, "missing", 10) is None
    fd = fsio.open_dir(tmp_path)
    try:
        assert fsio.read_capped(fd, "small", 10) == b"hello"
    finally:
        os.close(fd)


# --- text -----------------------------------------------------------------

def test_clean_text_strips_c0_c1_and_clips() -> None:
    raw = "a\x00b\x1bc\x7fd\x85e\x9ff‮g"
    out = text.clean_text(raw, 100)
    assert not any(ord(c) < 0x20 or 0x7F <= ord(c) <= 0x9F for c in out)
    assert out.startswith("a b c d e f")
    assert text.clean_text("abcdefgh", 3) == "abc"
    assert text.clean_text(None) == ""
    assert text.clean_text("  pad  ", 10) == "pad"


# --- envelope -------------------------------------------------------------

KEYS = {"schema", "ok", "error", "data", "capabilities"}


def test_envelope_success_shape() -> None:
    env = envelope.wrap(lambda: ({"v": 1}, {"fans": True}), schema=3)
    assert set(env) == KEYS
    assert env == {"schema": 3, "ok": True, "error": None, "data": {"v": 1}, "capabilities": {"fans": True}}


def test_envelope_on_unexpected_exception() -> None:
    def boom():
        raise RuntimeError("secret \x1b detail")

    env = envelope.wrap(boom, schema=2)
    assert set(env) == KEYS
    assert env["ok"] is False and env["schema"] == 2
    assert env["error"] == "internal:RuntimeError"
    assert env["data"] is None and env["capabilities"] == {}


def test_envelope_on_helper_error() -> None:
    def locked():
        raise envelope.HelperError("locked", capabilities={"key": False})

    env = envelope.wrap(locked)
    assert set(env) == KEYS
    assert env["ok"] is False and env["error"] == "locked" and env["capabilities"] == {"key": False}


def test_envelope_main_prints_json(capsys) -> None:
    rc = envelope.main(lambda: (None, {}), schema=1)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and set(out) == KEYS and out["ok"] is True


def test_envelope_main_survives_bad_return(capsys) -> None:
    rc = envelope.main(lambda: object(), schema=1)
    out = json.loads(capsys.readouterr().out)
    assert rc == 0 and set(out) == KEYS and out["ok"] is False


# --- sysfs ----------------------------------------------------------------

def _hwmon(root: Path, index: int, name: str, sensors: dict[str, tuple[str | None, int]], device: str | None = None) -> Path:
    d = root / "sys" / "class" / "hwmon" / f"hwmon{index}"
    d.mkdir(parents=True)
    (d / "name").write_text(name + "\n")
    for key, (label, value) in sensors.items():
        (d / f"{key}_input").write_text(f"{value}\n")
        if label is not None:
            (d / f"{key}_label").write_text(label + "\n")
    if device is not None:
        dev = root / "sys" / "devices" / device
        dev.mkdir(parents=True)
        (d / "device").symlink_to(dev)
    return d


def test_hwmon_resolves_by_name_and_label_across_index_changes(tmp_path: Path) -> None:
    a = tmp_path / "a"
    b = tmp_path / "b"
    _hwmon(a, 0, "macsmc_hwmon", {"temp1": ("CPU", 45000), "temp2": ("GPU", 50000), "fan1": ("Fan 1", 1200)})
    _hwmon(a, 1, "nvme", {"temp1": ("Composite", 39000)})
    _hwmon(b, 0, "nvme", {"temp1": ("Composite", 39000)})
    _hwmon(b, 3, "macsmc_hwmon", {"temp7": ("GPU", 50000), "temp2": ("CPU", 45000), "fan4": ("Fan 1", 1200)})
    for root in (a, b):
        cpu = sysfs.find_sensor("macsmc_hwmon", "CPU", kind="temp", root=root)
        gpu = sysfs.find_sensor("macsmc_hwmon", "GPU", kind="temp", root=root)
        fan = sysfs.find_sensor("macsmc_hwmon", "Fan 1", kind="fan", root=root)
        assert cpu is not None and cpu.value == 45000
        assert gpu is not None and gpu.value == 50000
        assert fan is not None and fan.value == 1200
        assert sysfs.find_sensor("macsmc_hwmon", "Missing", root=root) is None
        assert sysfs.find_sensor("coretemp", "CPU", root=root) is None


def test_hwmon_keeps_same_named_devices_distinct(tmp_path: Path) -> None:
    _hwmon(tmp_path, 0, "nvme", {"temp1": ("Composite", 30000)}, device="pci0000:00/nvme0")
    _hwmon(tmp_path, 1, "nvme", {"temp1": ("Composite", 40000)}, device="pci0000:00/nvme1")
    devs = sysfs.hwmon_devices(root=tmp_path)
    nvme = [d for d in devs if d.name == "nvme"]
    assert len(nvme) == 2
    assert len({d.key for d in nvme}) == 2
    values = sorted(d.sensor("Composite").value for d in nvme)
    assert values == [30000, 40000]
    assert len(sysfs.find_sensors("nvme", "Composite", root=tmp_path)) == 2


def test_hwmon_unlabelled_sensor_falls_back_to_key(tmp_path: Path) -> None:
    _hwmon(tmp_path, 2, "k10temp", {"temp1": (None, 55000)})
    s = sysfs.find_sensor("k10temp", "temp1", root=tmp_path)
    assert s is not None and s.value == 55000 and s.kind == "temp"


def _supply(root: Path, name: str, **attrs: str) -> None:
    d = root / "sys" / "class" / "power_supply" / name
    d.mkdir(parents=True)
    for key, value in attrs.items():
        (d / key).write_text(value + "\n")


def test_power_supply_enumeration_by_type_and_scope(tmp_path: Path) -> None:
    _supply(tmp_path, "macsmc-battery", type="Battery", capacity="80")
    _supply(tmp_path, "macsmc-ac", type="Mains", online="1")
    _supply(tmp_path, "hidpp_battery_0", type="Battery", scope="Device", capacity="50")
    _supply(tmp_path, "BAT0", type="Battery", scope="System", capacity="70")
    all_ = sysfs.power_supplies(root=tmp_path)
    assert {s.name for s in all_} == {"macsmc-battery", "macsmc-ac", "hidpp_battery_0", "BAT0"}
    sys_bats = sysfs.power_supplies(type="Battery", scope="System", root=tmp_path)
    assert sorted(s.name for s in sys_bats) == ["BAT0", "macsmc-battery"]
    dev = sysfs.power_supplies(type="Battery", scope="Device", root=tmp_path)
    assert [s.name for s in dev] == ["hidpp_battery_0"]
    mains = sysfs.power_supplies(type="Mains", root=tmp_path)
    assert mains[0].attr("online") == "1"


def test_empty_root_reports_nothing(tmp_path: Path) -> None:
    assert sysfs.hwmon_devices(root=tmp_path) == []
    assert sysfs.power_supplies(root=tmp_path) == []
    assert sysfs.drm_cards(root=tmp_path) == []


def test_drm_card_enumeration(tmp_path: Path) -> None:
    drm = tmp_path / "sys" / "class" / "drm"
    for name in ("card0", "card1", "card1-eDP-1", "card1-DP-3", "renderD128", "version"):
        (drm / name).mkdir(parents=True)
    driver = tmp_path / "sys" / "bus" / "platform" / "drivers" / "apple"
    driver.mkdir(parents=True)
    dev = tmp_path / "sys" / "devices" / "gpu1"
    dev.mkdir(parents=True)
    (dev / "driver").symlink_to(driver)
    (dev / "vendor").write_text("0x106b\n")
    (drm / "card1" / "device").symlink_to(dev)
    (drm / "card1-eDP-1" / "status").write_text("connected\n")
    (drm / "card1-DP-3" / "status").write_text("disconnected\n")
    cards = sysfs.drm_cards(root=tmp_path)
    assert [c.name for c in cards] == ["card0", "card1"]
    card1 = cards[1]
    assert card1.driver == "apple" and card1.vendor == "0x106b"
    assert {c.name: c.status for c in card1.connectors} == {"eDP-1": "connected", "DP-3": "disconnected"}
    assert cards[0].driver is None and cards[0].connectors == []


def test_read_attr_refuses_typec_identity(tmp_path: Path) -> None:
    ident = tmp_path / "sys" / "class" / "typec" / "port0-partner" / "identity"
    ident.mkdir(parents=True)
    (ident / "id_header").write_text("0x1\n")
    assert sysfs.read_attr(ident / "id_header") is None
    ptype = tmp_path / "sys" / "class" / "typec" / "port0-partner" / "type"
    ptype.write_text("x\n")
    assert sysfs.read_attr(ptype) is None
    ok = tmp_path / "plain"
    ok.write_text("value\n")
    assert sysfs.read_attr(ok) == "value"


def test_import_has_no_side_effects() -> None:
    import ast

    for path in (ROOT / "shared" / "py" / "_omplug").glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                pytest.fail(f"{path.name}: module-level call")


# --- against the committed hardware fixture corpus (U6) ---------------------

HW = ROOT / "tests" / "fixtures" / "hw"


@pytest.mark.skipif(not HW.is_dir(), reason="fixture corpus not present")
def test_readers_on_fixture_corpus() -> None:
    assert sysfs.drm_cards(root=HW / "amd-desktop")[0].driver == "amdgpu"
    bats = sysfs.power_supplies(type="Battery", scope="System", root=HW / "dell-precision")
    assert [b.name for b in bats] == ["BAT0"]
    assert sysfs.power_supplies(type="Battery", scope="System", root=HW / "no-battery") == []
    keys = [d.key for d in sysfs.hwmon_devices(root=HW / "asahi-m1max") if d.name == "tas2764"]
    assert len(keys) == len(set(keys)) > 1


def test_run_escalates_to_sigkill_when_group_ignores_sigterm(tmp_path: Path) -> None:
    pidfile = tmp_path / "pids"
    script = f"trap '' TERM; (trap '' TERM; sleep 30) & echo $! > {pidfile}; sleep 30"
    start = time.monotonic()
    res = proc.run([proc.tool("sh"), "-c", script], timeout=0.7)
    assert time.monotonic() - start < 5
    assert res.error == "timeout"
    grandchild = int(pidfile.read_text().strip())
    deadline = time.monotonic() + 2
    while _alive(grandchild) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(grandchild)


def test_read_attr_refuses_a_symlink_into_typec_identity(tmp_path: Path) -> None:
    ident = tmp_path / "sys" / "class" / "typec" / "port0-partner" / "identity"
    ident.mkdir(parents=True)
    (ident / "id_header").write_text("0x1\n")
    innocent = tmp_path / "sys" / "class" / "hwmon" / "hwmon9"
    innocent.mkdir(parents=True)
    (innocent / "name").symlink_to(ident / "id_header")
    assert sysfs.read_attr(innocent / "name") is None
