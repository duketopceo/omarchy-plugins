import importlib.util
import os
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "plugins/lukedaduke.lidguard/bin/lidguard.py"
spec = importlib.util.spec_from_file_location("lidguard", SRC)
lg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lg)


def supply(base, name, typ, online):
    d = base / name
    d.mkdir()
    (d / "type").write_text(typ + "\n")
    if online is not None:
        (d / "online").write_text(f"{online}\n")
    return d / "online"


def test_ac_online_states(tmp_path, monkeypatch):
    monkeypatch.setenv(lg.PS_DIR_ENV, str(tmp_path))
    assert lg.ac_online() is None
    supply(tmp_path, "BAT0", "Battery", None)
    assert lg.ac_online() is None
    f = supply(tmp_path, "macsmc-ac", "Mains", 1)
    assert lg.ac_online() is True
    f.write_text("0\n")
    assert lg.ac_online() is False


def test_ac_online_missing_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(lg.PS_DIR_ENV, str(tmp_path / "nope"))
    assert lg.ac_online() is None


def test_hold_exits_on_unplug(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(lg.PS_DIR_ENV, str(tmp_path))
    monkeypatch.setenv("LIDGUARD_TICK", "0.02")
    f = supply(tmp_path, "macsmc-ac", "Mains", 1)
    real_sleep = time.sleep
    calls = {"n": 0}

    def sleeper(s):
        calls["n"] += 1
        if calls["n"] == 2:
            f.write_text("0\n")
        real_sleep(s)

    monkeypatch.setattr(lg.time, "sleep", sleeper)
    t0 = time.monotonic()
    assert lg.hold("inf") == 0
    assert time.monotonic() - t0 < 2
    assert "AC unplugged" in capsys.readouterr().err
    assert calls["n"] == 3  # offline seen on ticks 2 and 3


def test_hold_single_offline_blip_does_not_disarm(tmp_path, monkeypatch):
    monkeypatch.setenv(lg.PS_DIR_ENV, str(tmp_path))
    monkeypatch.setenv("LIDGUARD_TICK", "0.02")
    f = supply(tmp_path, "macsmc-ac", "Mains", 1)
    n = {"i": 0}
    real_sleep = time.sleep

    def sleeper(s):
        n["i"] += 1
        f.write_text("0\n" if n["i"] == 1 else "1\n")
        real_sleep(s)

    monkeypatch.setattr(lg.time, "sleep", sleeper)
    t0 = time.monotonic()
    assert lg.hold("0.2") == 0
    assert time.monotonic() - t0 >= 0.18  # ran to deadline


def test_hold_on_battery_at_arm_ends_on_time_only(tmp_path, monkeypatch):
    monkeypatch.setenv(lg.PS_DIR_ENV, str(tmp_path))
    monkeypatch.setenv("LIDGUARD_TICK", "0.02")
    supply(tmp_path, "macsmc-ac", "Mains", 0)
    t0 = time.monotonic()
    assert lg.hold("0.2") == 0
    assert time.monotonic() - t0 >= 0.18


def test_hold_bad_duration():
    assert lg.hold("abc") == 2
