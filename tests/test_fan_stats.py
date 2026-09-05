from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "plugins/lukedaduke.fan/bin/system_monitor_stats.py"
KILL = ROOT / "plugins/lukedaduke.fan/bin/kill_proc.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_collect_json_bounds() -> None:
    stats = load(STATS, "system_monitor_stats")
    data = stats.collect(sample_seconds=0)
    assert data["ok"] is True
    assert 0 <= data["mem_pct"] <= 100
    assert 0 <= data["cpu_load"] <= 100
    assert isinstance(data["cpu_temp"], str)
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
