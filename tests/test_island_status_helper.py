"""bin/island-status: read-only machine state for the Island's pages."""
import importlib.machinery
import importlib.util
import json
import stat
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/bin/island-status"


def fake(bindir: Path, name: str, body: str) -> None:
    p = bindir / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def tree(tmp_path: Path) -> Path:
    root = tmp_path / "root"
    if root.exists():
        return root
    bat = root / "sys/class/power_supply/macsmc-battery"
    bat.mkdir(parents=True)
    (bat / "type").write_text("Battery\n")
    (bat / "capacity").write_text("80\n")
    (bat / "status").write_text("Not charging\n")
    ac = root / "sys/class/power_supply/macsmc-ac"
    ac.mkdir(parents=True)
    (ac / "type").write_text("Mains\n")
    for name, state in (("lo", "unknown"), ("wlan0", "up"), ("tailscale0", "unknown"), ("wg0", "unknown"),
                        ("docker0", "up")):
        d = root / "sys/class/net" / name
        d.mkdir(parents=True)
        (d / "operstate").write_text(state + "\n")
    (root / "sys/class/net/wlan0/wireless").mkdir()
    (root / "proc").mkdir()
    (root / "proc/stat").write_text("cpu  100 0 100 800 0 0 0 0 0 0\ncpu0 1 1 1 1\n")
    (root / "proc/meminfo").write_text("MemTotal:       1000 kB\nMemFree:  100 kB\nMemAvailable:    250 kB\n")
    return root


def run(tmp_path: Path, section: str, tools=None, root=None, xdg=None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name, body in (tools or {}).items():
        fake(bindir, name, body)
    env = {"HOME": str(home), "PATH": str(bindir)}
    if xdg:
        env["XDG_RUNTIME_DIR"] = str(xdg)
    r = subprocess.run([sys.executable, str(SCRIPT), section, "--root", str(root or tree(tmp_path)),
                        "--cpu-sample", "0"], check=False, env=env, capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def load():
    loader = importlib.machinery.SourceFileLoader("island_status", str(SCRIPT))
    spec = importlib.util.spec_from_loader("island_status", loader)
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


TS = json.dumps({"BackendState": "Running", "Self": {"Online": True, "HostName": "x", "TailscaleIPs": ["100.1.1.1"]},
                 "Peer": {"a": {}, "b": {}}})


def test_home_reads_battery_vpn_and_tailscale(tmp_path):
    out = run(tmp_path, "home", tools={"tailscale": f"echo '{TS}'"})
    assert out["battery"] == {"capacity": 80, "status": "Not charging"}
    assert out["vpn"] == {"on": True, "name": "wg0"}
    assert out["tailscale"] == {"state": "Running", "online": True, "peers": 2}


def test_tailscale_output_never_carries_addresses(tmp_path):
    out = run(tmp_path, "home", tools={"tailscale": f"echo '{TS}'"})
    assert "100.1.1.1" not in json.dumps(out)


def test_missing_tools_are_null_and_exit_zero(tmp_path):
    out = run(tmp_path, "system")
    assert out["profile"] is None and out["tailscale"] is None and out["fan"] is None
    assert out["fanPanel"] is False


def test_junk_tool_output_is_null(tmp_path):
    out = run(tmp_path, "home", tools={"tailscale": "echo not-json"})
    assert out["tailscale"] is None


def test_failing_tool_is_null(tmp_path):
    out = run(tmp_path, "system", tools={"powerprofilesctl": "exit 1"})
    assert out["profile"] is None


def test_system_reads_profile_memory_network_fallback(tmp_path):
    out = run(tmp_path, "system", tools={"powerprofilesctl": "echo balanced"})
    assert out["profile"] == "balanced"
    assert out["memory"] == {"usedPct": 75, "used": 750 * 1024, "total": 1000 * 1024}
    # no nmcli: first up interface that is not virtual, VPN or Tailscale
    assert out["network"] == {"iface": "wlan0", "type": "wifi", "name": ""}
    assert out["cpu"] == 0


def test_network_prefers_nmcli_connected_device(tmp_path):
    nm = "printf 'docker0:bridge:connected (externally):docker0\\nwlan0:wifi:connected:Home\\\\:Net\\n'"
    out = run(tmp_path, "system", tools={"nmcli": nm})
    assert out["network"] == {"iface": "wlan0", "type": "wifi", "name": "Home:Net"}


def test_fan_mode_read_from_runtime_dir(tmp_path):
    xdg = tmp_path / "run"
    (xdg / "omarchy-fan").mkdir(parents=True)
    (xdg / "omarchy-fan/current_fan_mode").write_text("quiet")
    out = run(tmp_path, "system", xdg=xdg)
    assert out["fan"] == "quiet"


def test_no_vpn_interface(tmp_path):
    root = tree(tmp_path)
    (root / "sys/class/net/wg0/operstate").write_text("down\n")
    out = run(tmp_path, "home", root=root)
    assert out["vpn"] == {"on": False, "name": ""}


def test_more_dayflow_fields(tmp_path):
    df = json.dumps({"capture_state": "recording", "paused": False, "frames_today": 656, "last_frame": "10:59 AM",
                     "blocks_pending": 2, "storage_text": "18.3 GB", "model": "secret-model"})
    out = run(tmp_path, "more", tools={"dayflow": f"echo '{df}'"})
    assert out["dayflow"] == {"state": "recording", "paused": False, "framesToday": 656, "lastFrame": "10:59 AM",
                              "pending": 2, "storage": "18.3 GB"}
    assert out["shots"] is None


def test_more_shots_needs_snapdex_ctl_and_lists_newest_first(tmp_path):
    home = tmp_path / "home"
    idx = home / "Pictures/Screenshots/index.md"
    idx.parent.mkdir(parents=True)
    idx.write_text("# Screenshots\n- [2026-11-01_10-00-00_a.png](2026-11-01_10-00-00_a.png) — old one\n"
                   "- [2026-11-16_09-00-00_b.png](2026-11-16_09-00-00_b.png) — new one\n")
    assert run(tmp_path, "more")["shots"] is None
    out = run(tmp_path, "more", tools={"snapdex-ctl": "exit 0"})
    assert out["shots"]["total"] == 2
    assert out["shots"]["items"][0] == {"name": "2026-11-16_09-00-00_b.png", "caption": "new one"}


def test_cpu_percent_between_snapshots():
    m = load()
    a = "cpu  100 0 100 800 0 0 0 0\n"
    b = "cpu  150 0 150 900 0 0 0 0\n"
    assert m.cpu_percent(a, b) == 50
    assert m.cpu_percent(a, a) == 0
    assert m.cpu_percent("junk", b) is None
