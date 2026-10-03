"""Tests for scripts/measure-plugin-cost.py (U7): strace execve attribution."""

from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "measure-plugin-cost.py"

LOG = """\
4242  10:00:00.000001 execve("/usr/bin/python3", ["/usr/bin/python3", "/home/u/.config/omarchy/plugins/lukedaduke.fan/bin/fan_status.py"], 0x7ff /* 5 vars */) = 0
4243  10:00:05.000001 execve("/usr/bin/python3", ["/usr/bin/python3", "/home/u/.config/omarchy/plugins/lukedaduke.fan/bin/fan_status.py"], 0x7ff /* 5 vars */) = 0
4244  10:00:06.000001 execve("/usr/bin/bluetoothctl", ["/usr/bin/bluetoothctl", "show"], 0x7ff /* 5 vars */) = 0
4250  10:00:07.000001 execve("/home/u/Documents/github/personal/omarchy-plugins/plugins/lukedaduke.nexus/bin/probe_nexus.py", ["/home/u/x/plugins/lukedaduke.nexus/bin/probe_nexus.py"], 0x7ff /* 1 var */) = 0
4251  10:00:08.000001 execve("/usr/bin/nonexistent", ["nonexistent"], 0x7ff /* 1 var */) = -1 ENOENT (No such file or directory)
4252  10:00:09.000001 +++ exited with 0 +++
"""


def load():
    spec = importlib.util.spec_from_file_location("measure_plugin_cost", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_execs_are_attributed_to_plugins_per_minute() -> None:
    mod = load()
    result = mod.attribute(LOG.splitlines(), window_s=120)
    assert result["per_minute"]["lukedaduke.fan"] == 1.0
    assert result["per_minute"]["lukedaduke.nexus"] == 0.5


def test_non_plugin_execs_count_as_other_not_dropped() -> None:
    mod = load()
    result = mod.attribute(LOG.splitlines(), window_s=60)
    assert result["counts"]["other"] == 1


def test_failed_execs_are_not_counted() -> None:
    mod = load()
    result = mod.attribute(LOG.splitlines(), window_s=60)
    assert sum(result["counts"].values()) == 4


def test_record_writes_rate_and_date_into_scorecard(tmp_path: Path) -> None:
    import json
    mod = load()
    review = tmp_path / "lukedaduke.fan.md"
    card = {"plugin": "lukedaduke.fan", "criteria": {}, "manual": {"spawn_measurement": {"value": None, "date": None}}}
    review.write_text("# fan\n\n```scorecard\n" + json.dumps(card, indent=2) + "\n```\n")
    assert mod.record({"lukedaduke.fan": 0.5}, tmp_path, "2026-10-03") == ["lukedaduke.fan"]
    text = review.read_text()
    body = text.split("```scorecard\n", 1)[1].split("\n```", 1)[0]
    assert json.loads(body)["manual"]["spawn_measurement"] == {"value": 0.5, "date": "2026-10-03"}
    assert text.startswith("# fan\n")


TRUNCATED = """\
5000  10:00:00.000001 execve("/usr/bin/python3", ["/usr/bin/python3", "/home/lukekimball/.config/omarch"...], 0x7ff /* 5 vars */) = 0
"""

FORKED = """\
6000  10:00:00.000001 execve("/usr/bin/python3", ["/usr/bin/python3", "/home/u/.config/omarchy/plugins/lukedaduke.fan/bin/fan_status.py"], 0x7ff /* 5 vars */) = 0
6000  10:00:00.100000 clone3({flags=CLONE_VM|CLONE_VFORK, exit_signal=SIGCHLD, stack=0x7f, stack_size=0x9000}, 88) = 6001
6001  10:00:00.100100 execve("/usr/bin/ps", ["/usr/bin/ps", "-eo", "comm"], 0x7ff /* 5 vars */) = 0
6001  10:00:00.200000 vfork() = 6002
6002  10:00:00.200100 execve("/usr/bin/sensors", ["/usr/bin/sensors"], 0x7ff /* 5 vars */) = 0
7000  10:00:01.000001 execve("/usr/bin/hyprctl", ["/usr/bin/hyprctl", "monitors"], 0x7ff /* 5 vars */) = 0
"""


def test_truncated_argv_is_reported_not_counted_as_other() -> None:
    mod = load()
    result = mod.attribute(TRUNCATED.splitlines(), window_s=60)
    assert result["truncated"] == 1
    assert "other" not in result["counts"]


def test_record_refuses_a_truncated_trace(tmp_path: Path, monkeypatch) -> None:
    import pytest
    mod = load()
    # Never let --record touch the real docs/reviews, even if refusal regresses.
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    log = tmp_path / "t.trace"
    log.write_text(TRUNCATED)
    with pytest.raises(SystemExit):
        mod.main(["--log", str(log), "--window", "60", "--record"])


def test_children_of_a_plugin_helper_are_credited_to_the_plugin() -> None:
    mod = load()
    result = mod.attribute(FORKED.splitlines(), window_s=60)
    assert result["counts"]["lukedaduke.fan"] == 3
    assert result["counts"]["other"] == 1


def test_live_trace_uses_full_strings_and_safe_path(monkeypatch, tmp_path: Path) -> None:
    mod = load()
    seen = {}
    monkeypatch.setattr(mod, "shell_pid", lambda: 1234)

    def fake_which(name, path=None):
        seen["path"] = path
        return "/usr/bin/strace"

    def fake_run(cmd, **kw):
        seen["cmd"] = cmd
        (tmp_path / "x.trace").write_text("")
        class R:
            returncode = 0
        return R()

    monkeypatch.setattr(mod.shutil, "which", fake_which)
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    mod.live_trace(5, tmp_path / "x.trace")
    assert seen["path"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert "-s" in seen["cmd"] and seen["cmd"][seen["cmd"].index("-s") + 1] == "4096"
    assert "trace=execve,clone,clone3,fork,vfork" in seen["cmd"]
