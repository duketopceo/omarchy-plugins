import importlib.util
import json
import os
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIX = ROOT / "tests" / "fixtures" / "hw"
PROFILES = ["asahi-m1max", "dell-precision", "amd-desktop", "nvidia-optimus", "no-battery", "empty"]
MAC_RE = re.compile(r"\b[0-9A-Fa-f]{2}(?:[:-][0-9A-Fa-f]{2}){5}\b")

_spec = importlib.util.spec_from_file_location("capture_hw_fixture", ROOT / "scripts" / "capture-hw-fixture.py")
cap = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cap)


def sysfs(profile):
    return FIX / profile / "sys" / "class"


def hwmons(profile):
    """{name: [dir, ...]} using plain reads."""
    out = {}
    base = sysfs(profile) / "hwmon"
    if base.is_dir():
        for d in sorted(base.iterdir()):
            out.setdefault((d / "name").read_text().strip(), []).append(d)
    return out


def supplies(profile):
    base = sysfs(profile) / "power_supply"
    return {d.name: d for d in sorted(base.iterdir())} if base.is_dir() else {}


def files(d):
    return {p.name for p in d.iterdir()}


# --- capture script -------------------------------------------------------

def _fake_root(tmp_path):
    r = tmp_path / "root"
    ti = r / "sys/class/typec/port0-partner/identity"
    ti.mkdir(parents=True)
    (ti / "vendor").write_text("0x05ac\n")
    (r / "sys/class/typec/port0-partner/type").write_text("x\n")
    bat = r / "sys/class/power_supply/BAT0"
    bat.mkdir(parents=True)
    (bat / "type").write_text("Battery\n")
    (bat / "capacity").write_text("50\n")
    (bat / "serial_number").write_text("SN12345\n")
    hw = r / "sys/class/hwmon/hwmon0"
    hw.mkdir(parents=True)
    (hw / "name").write_text("wifi aa:bb:cc:dd:ee:ff\n")
    (hw / "temp1_input").write_text("40000\n")
    return r


def test_capture_excludes_typec_identity(tmp_path):
    r = _fake_root(tmp_path)
    out = tmp_path / "out"
    cap.main(["--out", str(out), "--root", str(r)])
    assert not [p for p in out.rglob("*") if "typec" in p.parts or "identity" in p.parts]
    assert not any(p.name == "vendor" and "identity" in str(p) for p in out.rglob("*"))
    # and the reader itself refuses the path
    assert cap.read_text(str(r / "sys/class/typec/port0-partner/identity/vendor")) is None


def test_capture_redacts_serial_and_mac(tmp_path):
    r = _fake_root(tmp_path)
    out = tmp_path / "out"
    cap.main(["--out", str(out), "--root", str(r)])
    allfiles = [p for p in out.rglob("*") if p.is_file()]
    assert not any(p.name == "serial_number" for p in allfiles)
    blob = "".join(p.read_text() for p in allfiles)
    assert "SN12345" not in blob
    assert "aa:bb:cc:dd:ee:ff" not in blob
    assert "00:00:00:00:00:00" in blob
    assert (out / "sys/class/power_supply/BAT0/capacity").read_text() == "50\n"


def test_capture_is_deterministic_and_symlink_free(tmp_path):
    r = _fake_root(tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    cap.main(["--out", str(a), "--root", str(r)])
    cap.main(["--out", str(b), "--root", str(r)])
    la = sorted((str(p.relative_to(a)), p.read_text()) for p in a.rglob("*") if p.is_file())
    lb = sorted((str(p.relative_to(b)), p.read_text()) for p in b.rglob("*") if p.is_file())
    assert la == lb and la
    assert not [p for p in a.rglob("*") if p.is_symlink()]


# --- fixture corpus -------------------------------------------------------

@pytest.mark.parametrize("profile", PROFILES)
def test_manifest(profile):
    m = json.loads((FIX / profile / "fixture.json").read_text())
    assert m["profile"] == profile
    assert m["source"] in ("live", "synthetic")
    assert m["captured"] == "2026-10-03"
    assert m["notes"]
    assert (m["source"] == "live") == (profile == "asahi-m1max")


@pytest.mark.parametrize("profile", PROFILES)
def test_loads_with_plain_reads_and_is_clean(profile):
    n = 0
    for p in (FIX / profile).rglob("*"):
        assert not p.is_symlink()
        if p.is_file():
            text = p.read_text()
            assert "typec" not in p.parts and p.name != "serial_number"
            assert not MAC_RE.search(text.replace("00:00:00:00:00:00", ""))
            n += 1
    assert n >= 2


def test_asahi_shape():
    hw = hwmons("asahi-m1max")
    smc = hw["macsmc_hwmon"][0]
    assert {"fan1_target", "fan2_target", "fan1_min", "fan1_max"} <= files(smc)
    assert not any(n in hw for n in ("coretemp", "k10temp"))
    assert (FIX / "asahi-m1max/sys/module/macsmc_hwmon/parameters/fan_control").read_text().strip() in ("Y", "N")
    bat = supplies("asahi-m1max")["macsmc-battery"]
    assert (bat / "type").read_text().strip() == "Battery"
    assert "charge_control_end_threshold" in files(bat)
    assert (sysfs("asahi-m1max") / "drm/card2/device/driver").read_text().strip() == "apple-drm"


def test_dell_shape():
    hw = hwmons("dell-precision")
    assert "dell_smm" in hw and "coretemp" in hw
    bat = supplies("dell-precision")["BAT0"]
    assert "power_now" not in files(bat)
    assert {"current_now", "voltage_now"} <= files(bat)
    assert not any(f.startswith("pwm") for d in hw["dell_smm"] for f in files(d))


def test_amd_desktop_shape():
    hw = hwmons("amd-desktop")
    assert "amdgpu" in hw and "k10temp" in hw
    assert not [n for n, d in supplies("amd-desktop").items() if (d / "type").read_text().strip() == "Battery"]


def test_nvidia_optimus_shape():
    base = sysfs("nvidia-optimus") / "drm"
    status = {c.name: (c / "device/power/runtime_status").read_text().strip() for c in base.iterdir()}
    drivers = {c.name: (c / "device/driver").read_text().strip() for c in base.iterdir()}
    nv = [c for c, d in drivers.items() if d == "nvidia"]
    assert nv and status[nv[0]] == "suspended"
    assert "i915" in drivers.values()
    assert "BAT1" in supplies("nvidia-optimus") and "BAT0" not in supplies("nvidia-optimus")


def test_no_battery_shape():
    s = supplies("no-battery")
    assert s and all((d / "type").read_text().strip() == "Mains" for d in s.values())
    assert "fan1_input" not in {f for ds in hwmons("no-battery").values() for d in ds for f in files(d)}


def test_empty_shape():
    for sub in ("hwmon", "power_supply", "drm"):
        assert not (sysfs("empty") / sub).exists()
