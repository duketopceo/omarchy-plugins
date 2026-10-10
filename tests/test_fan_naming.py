"""U1: process naming rules + net/disk/history samplers for lukedaduke.fan."""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATS = ROOT / "plugins/lukedaduke.fan/bin/system_monitor_stats.py"


def load(name: str = "system_monitor_stats_u1"):
    spec = importlib.util.spec_from_file_location(name, STATS)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


EMPTY_CFG = {"names": {}, "rules": [], "min_mem_mb": 15, "top": 32, "find_max": 24}


def cfg(**kw):
    base = dict(EMPTY_CFG)
    base.update(kw)
    return base


# --- display_name resolution order (KTD1) ------------------------------------


def test_ollama_runner_via_exe_path() -> None:
    stats = load()
    name = stats.display_name(
        "llama-server",
        exe="/usr/lib/ollama/runners/cpu_avx2/llama-server",
        args="/usr/lib/ollama/runners/cpu_avx2/llama-server --model /x.gguf",
        cfg=cfg(),
    )
    assert name == "Ollama Backend"


def test_ollama_runner_via_cmdline() -> None:
    stats = load()
    # exe readlink failed -> argv0 fallback lacks 'ollama'; cmdline still has it
    name = stats.display_name(
        "llama-server",
        exe="/opt/llama/llama-server",
        args="llama-server --model /home/u/.ollama/models/blobs/sha256-dead --port 11434",
        cfg=cfg(),
    )
    assert name == "Ollama Backend"


def test_ollama_alt_runner_comm() -> None:
    stats = load()
    # Older ollama builds ship `ollama_llama_server` (comm truncates to 15)
    assert stats.display_name("ollama_llama_se", cfg=cfg()) == "Ollama Backend"


def test_llama_cpp_derives_model_and_port() -> None:
    stats = load()
    name = stats.display_name(
        "llama-server",
        exe="/home/u/src/llama.cpp/build/bin/llama-server",
        args="llama-server -m /models/qwen3-4b-instruct-q4km.gguf --port 8091",
        cfg=cfg(),
    )
    assert name == "llama.cpp qwen3-4b-instruct (:8091)"


def test_llama_cpp_long_flags() -> None:
    stats = load()
    name = stats.display_name(
        "llama-server",
        exe="/home/u/src/llama.cpp/build/bin/llama-server",
        args="llama-server --model=/models/Ornith-35B-Q4_K_M.gguf --port=8080",
        cfg=cfg(),
    )
    assert name == "llama.cpp Ornith-35B (:8080)"


def test_llama_cpp_no_model_keeps_plain_label() -> None:
    stats = load()
    name = stats.display_name(
        "llama-server",
        exe="/home/u/src/llama.cpp/build/bin/llama-server",
        args="llama-server --port 8081",
        cfg=cfg(),
    )
    assert name == "llama.cpp (:8081)"


def test_llama_server_other_origin_uses_map() -> None:
    stats = load()
    name = stats.display_name(
        "llama-server", exe="/opt/vendors/x/bin/llama-server",
        args="llama-server -m /m.gguf", cfg=cfg(),
    )
    assert name == "llama.cpp"


def test_unknown_comm_title_case_fallback() -> None:
    stats = load()
    name = stats.display_name(
        "unknown-thing", exe="/usr/bin/unknown-thing",
        args="unknown-thing --flag", cfg=cfg(),
    )
    assert name == "Unknown-Thing"


def test_user_rule_overrides_builtins() -> None:
    stats = load()
    user = cfg(rules=[{"match": {"arg": "ollama"}, "name": "My Ollama"}])
    name = stats.display_name(
        "llama-server", exe="/usr/lib/ollama/x/llama-server",
        args="llama-server --model /home/u/.ollama/blob", cfg=user,
    )
    assert name == "My Ollama"


def test_user_names_map_overrides_builtins() -> None:
    stats = load()
    user = cfg(names={"llama-server": "Mine"})
    name = stats.display_name(
        "llama-server", exe="/usr/lib/ollama/x/llama-server",
        args="llama-server --ollama", cfg=user,
    )
    assert name == "Mine"  # backward-compat: names map still wins (R7)


def test_user_rule_overrides_names_map() -> None:
    stats = load()
    user = cfg(
        names={"llama-server": "MapName"},
        rules=[{"match": {"comm": "llama-server"}, "name": "RuleName"}],
    )
    assert stats.display_name("llama-server", cfg=user) == "RuleName"


def test_user_rule_exe_and_arg_match() -> None:
    stats = load()
    user = cfg(rules=[
        {"match": {"exe": "/opt/agent", "arg": "--serve"}, "name": "Renamed"},
    ])
    assert stats.display_name(
        "agent", exe="/opt/agent/bin/run", args="/opt/agent/bin/run --serve",
        cfg=user) == "Renamed"
    # exe matches but arg does not -> falls through to title-case
    assert stats.display_name(
        "agent", exe="/opt/agent/bin/run", args="/opt/agent/bin/run --client",
        cfg=user) == "Agent"


# --- resources.json rules parsing --------------------------------------------


def _config_from_json(stats, monkeypatch, tmp_path: Path, payload) -> dict:
    f = tmp_path / "resources.json"
    f.write_text(json.dumps(payload))
    monkeypatch.setattr(stats, "CONFIG_PATH", f)
    stats._proc_config_cache = None
    return stats._proc_config()


def test_rules_parsed_and_applied(monkeypatch, tmp_path: Path) -> None:
    stats = load()
    parsed = _config_from_json(stats, monkeypatch, tmp_path, {
        "names": {"zsh": "Shell"},
        "rules": [{"match": {"arg": "special-token"}, "name": "Special"}],
        "top": 20,
    })
    assert parsed["names"]["zsh"] == "Shell"
    assert parsed["top"] == 20
    assert parsed["rules"] == [
        {"match": {"arg": "special-token"}, "name": "Special"}
    ]
    assert stats.display_name("thing", args="thing special-token",
                              cfg=parsed) == "Special"


def test_malformed_rules_skipped_with_warning(
        monkeypatch, tmp_path: Path, capsys) -> None:
    stats = load()
    parsed = _config_from_json(stats, monkeypatch, tmp_path, {
        "rules": [
            {"match": {"comm": "good"}, "name": "Good"},   # 0: ok
            "not-a-dict",                                   # 1: bad
            {"match": {"comm": "x"}},                       # 2: no name
            {"match": {}, "name": "Empty"},                 # 3: empty match
            {"match": {"comm": 7}, "name": "Num"},          # 4: non-str
            {"match": {"comm": "late"}, "name": "Late"},    # 5: ok
        ],
    })
    err = capsys.readouterr().err
    for idx in (1, 2, 3, 4):
        assert f"rule[{idx}]" in err
    assert len(parsed["rules"]) == 2
    assert stats.display_name("good", cfg=parsed) == "Good"
    assert stats.display_name("late", cfg=parsed) == "Late"
    # malformed entries didn't crash the parser; unmatched comms still resolve
    assert stats.display_name("x", cfg=parsed) == "X"


def test_rules_non_list_is_ignored(monkeypatch, tmp_path: Path, capsys) -> None:
    stats = load()
    parsed = _config_from_json(stats, monkeypatch, tmp_path, {
        "rules": {"comm": "x"}, "names": {"a": "A"}})
    assert parsed["rules"] == []
    assert parsed["names"]["a"] == "A"
    assert "rules" in capsys.readouterr().err


# --- Row identity fields (KTD2) ----------------------------------------------


def test_top_mem_rows_carry_identity() -> None:
    stats = load()
    rows = stats.top_mem(n=3, min_mb=1)
    assert rows, "no processes above 1MB? (requires a real Linux /proc)"
    for row in rows:
        for key in ("pid", "name", "comm", "display", "exe", "exe_path",
                    "args", "unit", "mem_mb", "mem_pct", "cpu_pct"):
            assert key in row, key
        assert row["comm"] == row["name"]
        assert len(row["args"]) <= stats.MAX_STR
        assert len(row["display"]) <= 48
        assert len(row["exe"]) <= 32
    json.dumps(rows)


def test_find_rows_carry_identity_and_bounds(monkeypatch) -> None:
    stats = load()
    huge_args = "needle " + "x" * 20000
    rows = [[str(900000 + i), "needle-proc", "4096", "1.0", huge_args]
            for i in range(40)]
    monkeypatch.setattr(stats, "_ps_rows", lambda *a, **k: rows)
    procs = stats.find_procs("needle", n=24)
    assert len(procs) == 24
    for row in procs:
        for key in ("comm", "exe", "args", "unit", "display"):
            assert key in row, key
        assert len(row["args"]) <= stats.MAX_STR
        assert len(row["exe"]) <= 32
        assert len(row["display"]) <= 48
    payload = json.dumps({"ok": True, "procs": procs})
    assert len(payload) < stats.MAX_OUT_BYTES


def test_find_min_rows_bounded(monkeypatch) -> None:
    stats = load()
    # 32 results cap: find_max under MAX_LIST keeps payload small
    rows = [[str(900000 + i), "needle", "2048", "0.5", "needle --run"]
            for i in range(32)]
    monkeypatch.setattr(stats, "_ps_rows", lambda *a, **k: rows)
    procs = stats.find_procs("needle", n=32)
    assert len(procs) == 32
    assert len(json.dumps({"procs": procs})) < stats.MAX_OUT_BYTES


# --- Net/disk samplers + persisted state (KTD5) ------------------------------


def _fresh_stats(monkeypatch, tmp_path: Path):
    stats = load()
    monkeypatch.setattr(stats, "_runtime_dir", lambda: tmp_path / "rt")
    stats._STATS_STATE = stats._empty_stats_state()
    return stats


def test_read_net_dev_parses(tmp_path: Path) -> None:
    stats = load()
    proc = tmp_path / "dev"
    proc.write_text(
        "Inter-|   Receive            |   Transmit\n"
        " face |bytes packets errs drop fifo frame compressed multicast"
        "|bytes packets errs drop fifo colls carrier compressed\n"
        "    lo: 100 1 0 0 0 0 0 0 100 1 0 0 0 0 0 0\n"
        " wlan0: 1000 10 0 0 0 0 0 0 500 5 0 0 0 0 0 0\n"
    )
    assert stats._read_net_dev(proc) == {"wlan0": (1000, 500)}


def test_read_diskstats_whole_disks_only(tmp_path: Path) -> None:
    stats = load()
    proc = tmp_path / "diskstats"
    proc.write_text(
        " 259 0 nvme0n1 8 0 400 0 4 0 600 0 0 0 0 0 0 0\n"   # whole disk
        " 259 1 nvme0n1p1 1 0 8 0 1 0 16 0 0 0 0 0 0 0\n"    # partition: skip
        "   7 0 loop0 1 0 8 0 1 0 16 0 0 0 0 0 0 0\n"        # loop: skip
        "   8 0 sda 2 0 200 0 3 0 300 0 0 0 0 0 0 0\n"       # whole disk
    )
    assert stats._read_diskstats(proc) == {"nvme0n1": (400, 600),
                                           "sda": (200, 300)}


def test_rate_deltas_exact() -> None:
    stats = load()
    state = {"ts": 1000.0,
             "net": {"wlan0": (1000, 500), "old0": (10, 10)},
             "disk": {"nvme0n1": (100, 200)}}
    net, disk = stats._rate_deltas(
        state, 1005.0,
        {"wlan0": (6000, 2500), "new0": (5, 5)},   # new0 has no prev
        {"nvme0n1": (150, 400)})
    assert net == {"down_bps": 1000, "up_bps": 400,
                   "ifaces": [{"name": "wlan0", "down_bps": 1000,
                               "up_bps": 400}]}
    assert disk == {"read_bps": 50 * 512 // 5, "write_bps": 200 * 512 // 5,
                    "devs": [{"name": "nvme0n1", "read_bps": 50 * 512 // 5,
                              "write_bps": 200 * 512 // 5}]}


def test_rate_deltas_reject_stale_or_shrunk() -> None:
    stats = load()
    state = {"ts": 100.0, "net": {"eth0": (5, 5)}, "disk": {"nvme0n1": (9, 9)}}
    # stale prev (>300s) -> nothing
    assert stats._rate_deltas(state, 500.0, {"eth0": (9, 9)}, {"nvme0n1": (10, 10)}) == (None, None)
    # counters reset (reboot) -> that dev contributes nothing, same rule as net
    net, disk = stats._rate_deltas(state, 110.0, {"eth0": (1, 1)}, {"nvme0n1": (1, 1)})
    assert net == {"down_bps": 0, "up_bps": 0, "ifaces": []}
    assert disk == {"read_bps": 0, "write_bps": 0, "devs": []}


def test_first_sample_emits_no_rates(monkeypatch, tmp_path: Path) -> None:
    stats = _fresh_stats(monkeypatch, tmp_path)
    monkeypatch.setattr(stats, "_read_net_dev", lambda: {"eth0": (100, 50)})
    monkeypatch.setattr(stats, "_read_diskstats", lambda: {"nvme0n1": (10, 20)})
    data = stats.collect(sample_seconds=0)
    assert "net" not in data
    assert "disk" not in data
    assert "history" not in data  # one sample in the ring


def test_second_sample_emits_rates_and_history(monkeypatch, tmp_path: Path) -> None:
    stats = _fresh_stats(monkeypatch, tmp_path)
    monkeypatch.setattr(stats, "_read_net_dev", lambda: {"eth0": (100, 50)})
    monkeypatch.setattr(stats, "_read_diskstats", lambda: {"nvme0n1": (10, 20)})
    stats.collect(sample_seconds=0)
    data = stats.collect(sample_seconds=0)
    assert data["net"] == {"down_bps": 0, "up_bps": 0, "ifaces": []}
    assert data["disk"] == {"read_bps": 0, "write_bps": 0, "devs": []}
    hist = data["history"]
    assert set(hist) == {"cpu_load", "cpu_temp", "mem_used"}
    assert all(isinstance(x, int) for x in hist["cpu_load"])
    assert len(hist["cpu_load"]) == 2


def test_absent_sources_emit_nothing(monkeypatch, tmp_path: Path) -> None:
    stats = _fresh_stats(monkeypatch, tmp_path)
    monkeypatch.setattr(stats, "_read_net_dev", lambda: {})
    monkeypatch.setattr(stats, "_read_diskstats", lambda: {})
    stats.collect(sample_seconds=0)
    data = stats.collect(sample_seconds=0)
    assert "net" not in data
    assert "disk" not in data
    assert "history" in data  # cpu/mem history still records


def test_state_survives_across_execs(monkeypatch, tmp_path: Path) -> None:
    stats = _fresh_stats(monkeypatch, tmp_path)
    monkeypatch.setattr(stats, "_read_net_dev", lambda: {"eth0": (100, 50)})
    monkeypatch.setattr(stats, "_read_diskstats", lambda: {"nvme0n1": (10, 20)})
    stats.collect(sample_seconds=0)
    state_file = tmp_path / "rt" / "stats_state.json"
    assert state_file.is_file()
    stats._STATS_STATE = None  # simulate a fresh exec reading the file
    data = stats.collect(sample_seconds=0)
    assert "net" in data and "disk" in data
    assert len(data["history"]["cpu_load"]) == 2
    # persisted file is bounded and valid JSON
    raw = state_file.read_bytes()
    assert len(raw) < 65536
    json.loads(raw)


def test_history_ring_load_is_bounded(monkeypatch, tmp_path: Path) -> None:
    stats = _fresh_stats(monkeypatch, tmp_path)
    rdir = tmp_path / "rt"
    rdir.mkdir(parents=True)
    (rdir / "stats_state.json").write_text(json.dumps({
        "ts": time.time() - 10,
        "net": {"eth0": [1, 2]},
        "disk": {"nvme0n1": [3, 4]},
        "hist": {"cpu_load": list(range(500)),  # oversize -> capped at 60
                 "cpu_temp": "not-a-list",
                 "mem_used": [1, "x", 2]},
    }))
    stats._STATS_STATE = None
    state = stats._stats_state()
    assert len(state["hist"]["cpu_load"]) == 60
    assert list(state["hist"]["mem_used"]) == [1, 2]
    assert list(state["hist"]["cpu_temp"]) == []
    assert state["net"] == {"eth0": (1, 2)}
    assert state["disk"] == {"nvme0n1": (3, 4)}


def test_state_file_symlink_is_ignored(monkeypatch, tmp_path: Path) -> None:
    stats = _fresh_stats(monkeypatch, tmp_path)
    rdir = tmp_path / "rt"
    rdir.mkdir(parents=True)
    target = tmp_path / "evil.json"
    target.write_text('{"ts": 1, "hist": {"cpu_load": [9] * 60}}')
    (rdir / "stats_state.json").symlink_to(target)
    stats._STATS_STATE = None
    state = stats._stats_state()
    assert list(state["hist"]["cpu_load"]) == []  # O_NOFOLLOW refused it
