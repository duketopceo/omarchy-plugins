"""lukedaduke.fan U10: friendly process groups, spawn-free collector, gated panel."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FAN_DIR = ROOT / "plugins/lukedaduke.fan"
BIN = FAN_DIR / "bin"
STATS = BIN / "system_monitor_stats.py"
KILL = BIN / "kill_proc.py"
PANEL = FAN_DIR / "Panel.qml"
HW = ROOT / "tests/fixtures/hw"
PROFILES = ["asahi-m1max", "dell-precision", "amd-desktop", "nvidia-optimus", "no-battery", "empty"]


def load(path: Path, name: str):
    if str(BIN) not in sys.path:
        sys.path.insert(0, str(BIN))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def stats():
    return load(STATS, "fan_stats_u10")


# --- R-a aliases --------------------------------------------------------------

ALIASES = [
    ("kurultai", ["/home/u/.local/bin/kurultai", "mcp", "--env"], "Kurultai", "agent"),
    ("chrome-headless", ["/home/u/.cache/ms-playwright/chrome-headless-shell", "--remote-debugging-port=9222"],
     "Headless Chrome (agent browser)", "browser"),
    ("chromium", ["/usr/lib/chromium/chromium --headless=new --remote-debugging-port=4933"],
     "Headless Chrome (agent browser)", "browser"),
    ("chromium", ["/usr/lib/chromium/chromium --type=renderer --crashpad-handler-pid=8805"], "Chromium", "browser"),
    ("node-MainThread", ["node", "/home/u/.local/share/mise/installs/claude-code/2.1.0/cli.js", "--resume"],
     "Claude Code", "agent"),
    ("claude", ["/home/u/.local/share/mise/installs/claude/latest/claude", "--resume", "abc"], "Claude Code", "agent"),
    ("quickshell", ["quickshell", "-n", "-p", "/usr/share/omarchy/shell"], "Omarchy shell", "shell"),
    ("devin", ["devin", "--resume", "rain-salary"], "Devin", "agent"),
    ("devin", ["/home/u/.local/share/devin/cli/_versions/3000.11.3/bin/devin", "acp"], "Devin", "agent"),
    ("codex", ["codex", "exec"], "Codex", "agent"),
    ("Hyprland", ["Hyprland"], "Hyprland (desktop)", "shell"),
    ("python3", ["/usr/bin/python3", "/home/u/.config/omarchy/plugins/lukedaduke.power/battery_helper.py"],
     "Power monitor", "plugin"),
    ("python3", ["/usr/bin/python3", "/x/plugins/lukedaduke.fan/bin/system_monitor_stats.py", "--bar"],
     "Fan monitor", "plugin"),
    ("bun", ["/home/u/.local/bin/bun", "/home/u/.config/omarchy/plugins/nixfred.blip/collector.ts"],
     "nixfred.blip plugin", "plugin"),
    ("python3", ["python3", "/home/u/.local/bin/home-index-mcp"], "home-index-mcp (python)", "dev"),
    ("python3", ["/usr/bin/python3", "/home/u/.local/bin/kurultai-mcp-bridge.py", "work"], "Kurultai", "agent"),
    ("node-MainThread", ["node", "scripts/qa/capture-web.mjs", "--target", "dashboard"], "capture-web.mjs (node)", "dev"),
    ("ollama", ["/usr/bin/ollama", "serve"], "Ollama (local AI)", "app"),
    ("pipewire", ["/usr/bin/pipewire"], "Audio (PipeWire)", "system"),
    ("wireplumber", ["/usr/bin/wireplumber"], "Audio (PipeWire)", "system"),
    ("dockerd", ["/usr/bin/dockerd", "-H", "fd://"], "Docker", "system"),
    ("systemd-journal", ["/usr/lib/systemd/systemd-journald"], "systemd", "system"),
    ("kworker/0:1-events", [], "Kernel", "system"),
    ("godot", ["godot", "--path", "."], "godot", "app"),
]


@pytest.mark.parametrize("comm,argv,label,kind", ALIASES)
def test_alias_table(stats, comm, argv, label, kind) -> None:
    got = stats.classify(comm, argv)
    assert (got["label"], got["kind"]) == (label, kind)


# --- grouping ---------------------------------------------------------------

def test_grouping_sums_and_kill_target_only_for_single_process(stats) -> None:
    rows = [
        {"pid": 10, "start": 1, "label": "Chromium", "kind": "browser", "cpu": 12.5, "rss_kb": 400_000, "detail": "chromium --type=renderer"},
        {"pid": 11, "start": 2, "label": "Chromium", "kind": "browser", "cpu": 2.5, "rss_kb": 100_000, "detail": "chromium --type=gpu-process"},
        {"pid": 12, "start": 3, "label": "Chromium", "kind": "browser", "cpu": 0.0, "rss_kb": 50_000, "detail": "chromium"},
        {"pid": 13, "start": 4, "label": "Chromium", "kind": "browser", "cpu": 1.0, "rss_kb": 50_000, "detail": "chromium"},
        {"pid": 20, "start": 5, "label": "godot", "kind": "app", "cpu": 0.5, "rss_kb": 300_000, "detail": "godot --path ."},
    ]
    groups = {g["label"]: g for g in stats.group_processes(rows)}
    chrome = groups["Chromium"]
    assert chrome["count"] == 4
    assert chrome["cpu"] == pytest.approx(16.0)
    assert chrome["mem_mb"] == pytest.approx(600_000 / 1024, abs=0.1)
    assert chrome["pids"] == [10, 11, 13]  # top 3 by cpu
    assert chrome["kill_pid"] == 0  # grouped: no kill action
    assert "4 processes" in chrome["detail"]
    godot = groups["godot"]
    assert godot["count"] == 1
    assert godot["kill_pid"] == 20
    assert godot["kill_start"] == 5
    assert "processes" not in godot["detail"]


def test_groups_busy_first_then_by_memory(stats) -> None:
    rows = [
        {"pid": 1 + i, "start": i, "label": f"g{i}", "kind": "app", "cpu": cpu, "rss_kb": rss, "detail": ""}
        for i, (cpu, rss) in enumerate([(0.2, 900_000), (40.0, 10_000), (0.0, 2_000_000), (5.0, 50_000)])
    ]
    order = [g["label"] for g in stats.group_processes(rows)]
    assert order == ["g1", "g3", "g2", "g0"]


# --- R-b redaction ------------------------------------------------------------

SECRETS = [
    "sk-abc123def456ghi789jkl",
    "sk-or-v1-0a1b2c3d4e5f",
    "hunter2isMyPassword",
    "0123456789abcdef0123456789abcdef01234567",
    "ghp_AbCdEf1234567890xyzXYZ",
    "xoxb-1234-5678-abcdef",
    "QmFzZTY0ZW5jb2RlZFNlY3JldFZhbHVlMTIz",
]


def secret_argv() -> list[str]:
    return [
        "node", "/srv/app/server.js",
        "--api-key=sk-abc123def456ghi789jkl",
        "OPENROUTER_API_KEY=sk-or-v1-0a1b2c3d4e5f",
        "--password", "hunter2isMyPassword",
        "0123456789abcdef0123456789abcdef01234567",
        "ghp_AbCdEf1234567890xyzXYZ",
        "--slack=xoxb-1234-5678-abcdef",
        "QmFzZTY0ZW5jb2RlZFNlY3JldFZhbHVlMTIz",
    ]


def test_redaction_drops_every_secret_shape(stats) -> None:
    out = " ".join(stats.redact_args(secret_argv()))
    for secret in SECRETS:
        assert secret not in out, secret
    # Still recognisable: flag names and the script survive.
    assert "--api-key" in out and "server.js" in out
    summary = stats.summarize_argv(secret_argv())
    assert len(summary) <= 60
    for secret in SECRETS:
        assert secret[:12] not in summary


def test_redaction_end_to_end_through_proc_scan(stats, tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    write_proc(proc, 4242, "node", secret_argv(), utime=10, rss_pages=40_000)
    state = tmp_path / "state"
    groups, _ = stats.process_groups(proc_root=proc, state_dir=state, now=100.0)
    blob = json.dumps(groups)
    for secret in SECRETS:
        assert secret not in blob, secret


def test_redaction_keeps_ordinary_flags(stats) -> None:
    out = stats.redact_args(["/usr/lib/chromium/chromium", "--type=renderer", "--crashpad-handler-pid=8805",
                             "mcp-server-sequential-thinking"])
    assert out == ["/usr/lib/chromium/chromium", "--type=renderer", "--crashpad-handler-pid=8805",
                   "mcp-server-sequential-thinking"]


# --- R-c /proc scan with a jiffies cache ----------------------------------------

def write_proc(proc: Path, pid: int, comm: str, argv: list[str], utime: int = 0, stime: int = 0,
               start: int = 1000, rss_pages: int = 1000) -> None:
    d = proc / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    rest = ["S", "1", str(pid), str(pid), "0", "-1", "4194560", "0", "0", "0", "0",
            str(utime), str(stime), "0", "0", "20", "0", "1", "0", str(start), "1000000", str(rss_pages)]
    (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(rest) + " 0 0 0\n")
    (d / "statm").write_text(f"{rss_pages * 2} {rss_pages} 100 1 0 1 0\n")
    (d / "comm").write_text(comm + "\n")
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + (b"\0" if argv else b""))


def test_cpu_percent_from_two_snapshots(stats, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(stats, "CLK_TCK", 100)
    proc = tmp_path / "proc"
    state = tmp_path / "state"
    write_proc(proc, 100, "godot", ["godot", "--path", "."], utime=500, rss_pages=50_000)
    write_proc(proc, 200, "Hyprland", ["Hyprland"], utime=50, rss_pages=30_000)
    first, meta = stats.process_groups(proc_root=proc, state_dir=state, now=1000.0)
    assert meta["warm"] is False
    assert all(g["cpu"] == 0 for g in first)  # first scan: 0, not lifetime garbage
    assert (state / "procs.json").is_file()
    assert (state / "procs.json").stat().st_mode & 0o777 == 0o600

    # 2 s later: godot burned 2 s of CPU (100 %), Hyprland 0.5 s (25 %).
    write_proc(proc, 100, "godot", ["godot", "--path", "."], utime=700, rss_pages=50_000)
    write_proc(proc, 200, "Hyprland", ["Hyprland"], utime=100, rss_pages=30_000)
    second, meta = stats.process_groups(proc_root=proc, state_dir=state, now=1002.0)
    assert meta["warm"] is True
    by = {g["label"]: g for g in second}
    assert by["godot"]["cpu"] == pytest.approx(100.0, abs=0.1)
    assert by["Hyprland (desktop)"]["cpu"] == pytest.approx(25.0, abs=0.1)
    assert by["godot"]["mem_mb"] == pytest.approx(50_000 * stats.PAGE_KB / 1024, abs=0.1)


def test_vanished_and_reused_pids_are_tolerated(stats, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(stats, "CLK_TCK", 100)
    proc = tmp_path / "proc"
    state = tmp_path / "state"
    write_proc(proc, 100, "godot", ["godot"], utime=500, start=10, rss_pages=50_000)
    write_proc(proc, 101, "gone", ["gone"], utime=500, rss_pages=50_000)
    stats.process_groups(proc_root=proc, state_dir=state, now=10.0)
    # pid 101 exits; pid 100 is reused by a new process with a later start time.
    import shutil
    shutil.rmtree(proc / "101")
    write_proc(proc, 100, "other", ["other"], utime=900, start=99, rss_pages=50_000)
    (proc / "102").mkdir()  # half-created pid dir with no files
    groups, _ = stats.process_groups(proc_root=proc, state_dir=state, now=12.0)
    by = {g["label"]: g for g in groups}
    assert "gone" not in by
    assert by["other"]["cpu"] == 0  # reused pid: no delta against the old process


def test_stale_or_corrupt_cache_reports_zero(stats, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(stats, "CLK_TCK", 100)
    proc = tmp_path / "proc"
    state = tmp_path / "state"
    state.mkdir(mode=0o700)
    (state / "procs.json").write_text("{not json")
    write_proc(proc, 100, "godot", ["godot"], utime=500, rss_pages=50_000)
    groups, meta = stats.process_groups(proc_root=proc, state_dir=state, now=10.0)
    assert meta["warm"] is False and groups[0]["cpu"] == 0


# --- R-c --bar mode spawns nothing ---------------------------------------------

def _forbid_spawn(monkeypatch, stats) -> None:
    def boom(*_a, **_k):
        raise AssertionError("bar mode must not spawn")
    monkeypatch.setattr(subprocess, "Popen", boom)
    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(stats.proc, "run", boom)


def test_bar_mode_spawns_nothing_and_reports_ram_temp_fan(stats, tmp_path: Path, monkeypatch) -> None:
    _forbid_spawn(monkeypatch, stats)
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "meminfo").write_text("MemTotal: 16000000 kB\nMemFree: 1000 kB\nMemAvailable: 4000000 kB\n"
                                  "SwapTotal: 0 kB\nSwapFree: 0 kB\n")
    data, caps = stats.build("bar", root=HW / "dell-precision", proc_root=proc, state_dir=tmp_path / "s")
    assert data["mode"] == "bar"
    assert data["mem"]["pct"] == 75
    assert data["temp"]["c"] == 55 and data["temp"]["source"] == "cpu"
    assert [f["rpm"] for f in data["fans"]] == [2310, 0]
    assert "fan_mode" in data
    assert "groups" not in data and "gpu" not in data
    assert caps["fan_control"] is False  # dell fixture exposes no pwm controls


def test_bar_mode_real_machine_spawns_nothing(stats, monkeypatch) -> None:
    _forbid_spawn(monkeypatch, stats)
    data, _ = stats.build("bar")
    assert 0 <= data["mem"]["pct"] <= 100


def test_no_external_tool_references_remain() -> None:
    source = STATS.read_text()
    for tool in ("\"ps\"", "'ps'", "\"df\"", "'df'", "inxi", "lspci", "dmidecode"):
        assert tool not in source, tool
    assert "_tool(\"ps\")" not in source


# --- R-g fixtures --------------------------------------------------------------

@pytest.mark.parametrize("profile", PROFILES)
def test_full_collect_on_every_fixture_returns_a_valid_envelope(stats, profile, tmp_path: Path, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(stats.proc, "run", lambda *a, **k: calls.append(a) or stats.proc.RunResult(error="spawn_failed"))
    proc = tmp_path / "proc"
    proc.mkdir()
    env = stats.envelope.wrap(lambda: stats.build("full", root=HW / profile, proc_root=proc,
                                                  state_dir=tmp_path / "s"))
    assert env["ok"] is True, env
    json.dumps(env)
    data = env["data"]
    for key in ("cpu", "mem", "gpu", "temps", "fans", "disks", "groups", "fan_mode"):
        assert key in data, key
    assert isinstance(env["capabilities"]["gpu_load"], bool)
    assert calls == []  # no fixture has an awake NVIDIA GPU


def test_asahi_reports_board_temps_honestly_and_no_gpu_load(stats, tmp_path: Path) -> None:
    proc = tmp_path / "proc"
    proc.mkdir()
    data, caps = stats.build("full", root=HW / "asahi-m1max", proc_root=proc, state_dir=tmp_path / "s")
    assert data["cpu"]["temp"] is None
    assert data["temp"]["source"] == "board"
    labels = {t["label"] for t in data["temps"]}
    assert "NAND Flash Temperature" in labels
    assert data["gpu"]["load"] is None
    assert "not available" in data["gpu"]["reason"].lower()
    assert data["gpu"]["power_w"] == pytest.approx(30.7, abs=0.1)
    assert [f["rpm"] for f in data["fans"]] == [2759, 2886]
    assert caps["fan_control"] is True and caps["gpu_load"] is False


def test_suspended_nvidia_is_never_woken(stats, tmp_path: Path, monkeypatch) -> None:
    calls: list = []
    monkeypatch.setattr(stats.proc, "run", lambda *a, **k: calls.append(a) or stats.proc.RunResult(error="spawn_failed"))
    proc = tmp_path / "proc"
    proc.mkdir()
    data, _ = stats.build("full", root=HW / "nvidia-optimus", proc_root=proc, state_dir=tmp_path / "s")
    assert calls == []
    assert "asleep" in data["gpu"]["reason"].lower()


def test_awake_nvidia_queries_nvidia_smi(stats, tmp_path: Path, monkeypatch) -> None:
    import shutil
    root = tmp_path / "hw"
    shutil.copytree(HW / "nvidia-optimus", root)
    (root / "sys/class/drm/card1/device/power/runtime_status").write_text("active\n")
    calls: list = []

    def fake_run(argv, *a, **k):
        calls.append(argv)
        return stats.proc.RunResult(rc=0, out="37, 51, NVIDIA RTX A2000 Laptop GPU\n")

    monkeypatch.setattr(stats.proc, "run", fake_run)
    monkeypatch.setattr(stats.proc, "tool", lambda name, *a: "/usr/bin/nvidia-smi" if name == "nvidia-smi" else None)
    proc = tmp_path / "proc"
    proc.mkdir()
    data, caps = stats.build("full", root=root, proc_root=proc, state_dir=tmp_path / "s")
    assert len(calls) == 1
    assert data["gpu"]["load"] == 37 and data["gpu"]["temp"] == 51
    assert caps["gpu_load"] is True


def test_live_full_collect_envelope(stats) -> None:
    env = stats.envelope.wrap(lambda: stats.build("full"))
    assert env["ok"] is True, env
    assert isinstance(env["data"]["groups"], list)
    assert len(json.dumps(env)) < stats.MAX_OUT_BYTES


# --- kill helper -----------------------------------------------------------------

def test_kill_refuses_mismatched_start_time(tmp_path: Path) -> None:
    kill = load(KILL, "fan_kill_u10")
    proc = tmp_path / "proc"
    write_proc(proc, 4321, "victim", ["victim"], start=777)
    with pytest.raises(kill.envelope.HelperError) as exc:
        kill.kill(4321, expected_start=778, proc_root=proc)
    assert exc.value.error == "changed"
    with pytest.raises(kill.envelope.HelperError):
        kill.kill(1)


# --- contract, shared library, QML structure -----------------------------------

def _contract():
    spec = importlib.util.spec_from_file_location("contract_u10", ROOT / "scripts/check-plugin-contract.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_fan_is_a_shared_library_consumer_with_zero_contract_errors() -> None:
    consumers = (ROOT / "shared/consumers.txt").read_text().split()
    assert "lukedaduke.fan" in consumers
    findings = _contract().scan_plugin(FAN_DIR, strict_estate=True)
    errors = [f for f in findings if f["severity"] == "error"]
    assert errors == []


def test_sync_shared_check_passes() -> None:
    out = subprocess.run([sys.executable, str(ROOT / "scripts/sync-shared.py"), "--check"],
                         capture_output=True, text=True)
    assert out.returncode == 0, out.stderr


def _timer_blocks(source: str) -> list[str]:
    return [b for _, b in _contract()._blocks(source, "Timer")]


def test_panel_timers_are_gated_and_bar_is_slow() -> None:
    source = PANEL.read_text()
    assert 'import "lib"' in source
    blocks = {re.search(r"id:\s*(\w+)", b).group(1): b for b in _timer_blocks(source) if re.search(r"id:\s*(\w+)", b)}
    bar = blocks["barTimer"]
    full = blocks["fullTimer"]
    interval = re.search(r"interval:\s*([^\n]+)", bar).group(1)
    assert "60000" in interval
    assert re.search(r"running:\s*[^\n]*gate\.visible", bar)
    assert re.search(r"running:\s*[^\n]*root\.opened", full)
    assert "--bar" in source
    assert "VisibilityGate" in source and "StaleLabel" in source and "DeadlineProcess" in source
    assert "execDetached" not in source


def test_panel_theme_and_plain_text() -> None:
    source = PANEL.read_text()
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", source)
    for _, block in _contract()._blocks(source, "Text"):
        if re.search(r"\btext\s*:", block):
            assert "Text.PlainText" in block


def test_manifest_and_catalog_version() -> None:
    manifest = json.loads((FAN_DIR / "manifest.json").read_text())
    assert manifest["version"] == "2.3.0"
    catalog = json.loads((ROOT / "catalog.json").read_text())
    entry = next(p for p in catalog["plugins"] if p["id"] == "lukedaduke.fan")
    assert entry["version"] == "2.3.0"


@pytest.mark.parametrize("label,kind", [
    ("Hyprland (desktop)", "shell"), ("Omarchy shell", "shell"), ("Xwayland", "shell"),
    ("systemd", "system"), ("Kernel", "system"),
])
def test_session_critical_processes_offer_no_kill(stats, label, kind) -> None:
    rows = [{"pid": 30, "start": 9, "label": label, "kind": kind, "cpu": 4.0, "rss_kb": 100_000, "detail": label}]
    group = stats.group_processes(rows)[0]
    assert group["kill_pid"] == 0 and group["kill_start"] == 0
    assert group["protected"] is True


def test_ordinary_single_process_app_stays_killable(stats) -> None:
    rows = [{"pid": 31, "start": 9, "label": "Docker", "kind": "system", "cpu": 4.0, "rss_kb": 1, "detail": "dockerd"}]
    group = stats.group_processes(rows)[0]
    assert group["kill_pid"] == 31 and group["protected"] is False
