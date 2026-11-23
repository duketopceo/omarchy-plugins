"""0.4.2 visual redesign logic: tiles, rings, profiles, Dayflow view, fonts (node)."""
import json
import os
import shutil
import subprocess
import stat
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def js(module: str, expr: str):
    path = PLUGIN / module
    script = f"const M=require({json.dumps(str(path))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


def row(key, status, app="claude-code", where="Home", title=None):
    return {"key": key, "status": status, "app": app, "where": where, "title": title or key}


# ---- Agents: tiles, pills, icons ----

def test_tiles_all_fit_when_under_cap():
    rows = [row("a", "needs"), row("b", "idle")]
    out = js("Agents.js", f"M.tiles({json.dumps(rows)}, 6)")
    assert [t["key"] for t in out["tiles"]] == ["a", "b"] and out["more"] is None


def test_tiles_collapse_idle_into_one_tile():
    rows = [row("n", "needs"), row("w", "working"), row("d", "done")] + [row(f"i{i}", "idle") for i in range(5)]
    out = js("Agents.js", f"M.tiles({json.dumps(rows)}, 6)")
    assert [t["key"] for t in out["tiles"]] == ["n", "w", "d", "i0", "i1"]
    assert out["more"] == {"n": 3, "label": "+3 idle"}


def test_tiles_overflow_of_active_agents_reads_more_not_idle():
    rows = [row(f"w{i}", "working") for i in range(8)]
    out = js("Agents.js", f"M.tiles({json.dumps(rows)}, 6)")
    assert len(out["tiles"]) == 5 and out["more"] == {"n": 3, "label": "+3 more"}


def test_tiles_empty_and_cap_floor():
    assert js("Agents.js", "M.tiles([], 6)") == {"tiles": [], "more": None}
    assert js("Agents.js", "M.tiles(null, 0)") == {"tiles": [], "more": None}


def test_rows_order_is_needs_working_done_idle():
    sess = [{"id": k, "source": "herdr", "app": "codex", "name": k, "status": s}
            for k, s in [("i", "idle"), ("d", "done"), ("w", "working"), ("n", "blocked")]]
    rows = js("Agents.js", f"M.rows({json.dumps({'sessions': sess})})")
    assert [r["key"] for r in rows] == ["n", "w", "d", "i"]


def test_pills_drop_zero_counts_and_idle():
    rows = [row("a", "needs"), row("b", "working"), row("c", "working"), row("d", "idle")]
    assert js("Agents.js", f"M.pills({json.dumps(rows)})") == [
        {"status": "needs", "n": 1, "label": "1 needs you"}, {"status": "working", "n": 2, "label": "2 working"}]
    assert js("Agents.js", f"M.pills({json.dumps([row('a', 'idle')])})") == []


def test_host_icon_names_and_initial():
    assert js("Agents.js", "M.hostOf('Mac mini @ mac-mini')") == "mac-mini"
    assert js("Agents.js", "M.hostOf('Home')") == "Home"
    assert js("Agents.js", "M.hostOf(null)") == ""
    assert js("Agents.js", "M.iconNames('claude-code')")[0] == "claude-code"
    assert js("Agents.js", "M.iconNames('opencode')")[0] == "ai.opencode"
    assert js("Agents.js", "M.iconNames('mystery')") == []
    assert js("Agents.js", "M.initial('claude-code')") == "C"
    assert js("Agents.js", "M.appKey('../x')") == ""


# ---- Status: profiles, rings, chips ----

LIST = "  performance:\n      CpuDriver: amd\n* balanced:\n      CpuDriver: amd\n  power-saver:\n      Degraded: no\n"


def test_parse_profiles_names_and_active():
    assert js("Status.js", f"M.parseProfiles({json.dumps(LIST)})") == {
        "names": ["performance", "balanced", "power-saver"], "active": "balanced"}
    assert js("Status.js", "M.parseProfiles(null)") == {"names": [], "active": ""}
    assert js("Status.js", "M.parseProfiles('garbage; rm -rf /')") == {"names": [], "active": ""}


def test_profile_argv_only_for_listed_names():
    assert js("Status.js", f"M.profileArgv('performance', {json.dumps(LIST)})") == ["powerprofilesctl", "set", "performance"]
    assert js("Status.js", f"M.profileArgv('turbo', {json.dumps(LIST)})") == []
    assert js("Status.js", f"M.profileArgv('balanced; reboot', {json.dumps(LIST)})") == []
    assert js("Status.js", "M.profileArgv('balanced', '')") == []
    assert js("Status.js", "M.profileArgv(null, null)") == []


@pytest.mark.parametrize("id_,pct,charging,tone", [
    ("cpu", 40, False, "accent"), ("cpu", 90, False, "urgent"), ("memory", 95, False, "urgent"),
    ("battery", 80, False, "accent"), ("battery", 15, False, "urgent"), ("battery", 15, True, "accent"),
    ("battery", 100, False, "accent")])
def test_ring_tone(id_, pct, charging, tone):
    assert js("Status.js", f"M.ringTone({json.dumps(id_)}, {pct}, {json.dumps(charging)})") == tone


SYS = {"battery": {"capacity": 64, "status": "Charging"}, "cpu": 27, "memory": {"usedPct": 41, "used": 1, "total": 2},
       "network": {"iface": "wlan0", "type": "wifi", "name": "Home WiFi"},
       "tailscale": {"state": "Running", "online": True, "peers": 22}, "fan": "quiet", "fanPanel": True,
       "profile": "balanced", "profiles": LIST}


def system(s):
    return js("Status.js", f"M.system({json.dumps(s)})")


def test_system_rings_chips_profiles():
    v = system(SYS)
    assert [(r["id"], r["pct"], r["caption"], r["charging"]) for r in v["rings"]] == [
        ("battery", 64, "Battery", True), ("cpu", 27, "CPU", False), ("memory", 41, "Memory", False)]
    assert v["rings"][1]["level"] == 0.27
    assert [(c["id"], c["icon"], c["text"], c["action"]) for c in v["chips"]] == [
        ("network", "wifi", "Home WiFi", ""), ("tailscale", "vpn", "22 peers", ""), ("fan", "fan", "Quiet", "fan")]
    assert v["profiles"]["active"] == "balanced" and v["profiles"]["available"] is True
    assert [p["name"] for p in v["profiles"]["names"]] == ["performance", "balanced", "power-saver"]


def test_system_tailscale_off_ethernet_and_no_fan_no_daemon():
    v = system({**SYS, "tailscale": {"state": "Stopped", "online": False, "peers": 0}, "fan": None, "fanPanel": False,
                "network": {"iface": "eth0", "type": "ethernet", "name": ""}, "profile": None, "profiles": None})
    chips = {c["id"]: c for c in v["chips"]}
    assert chips["tailscale"]["text"] == "Off" and chips["tailscale"]["on"] is False
    assert chips["network"]["icon"] == "ethernet" and chips["network"]["text"] == "Ethernet"
    assert "fan" not in chips
    assert v["profiles"]["available"] is False and v["profiles"]["active"] == ""
    assert [p["name"] for p in v["profiles"]["names"]] == ["power-saver", "balanced", "performance"]


def test_system_missing_sources_are_left_out():
    assert system(None) == {"rings": [], "chips": [], "profiles": {"names": [], "active": "", "available": False}}
    v = system({"cpu": 150})
    assert [r["pct"] for r in v["rings"]] == [100] and v["rings"][0]["tone"] == "urgent"


# ---- More: Dayflow view, relative time, avatars ----

def rel(text, now_iso):
    return js("More.js", f"M.relTime({json.dumps(text)}, new Date({json.dumps(now_iso)}).getTime())")


@pytest.mark.parametrize("last,now,want", [
    ("2:00 PM", "2026-11-16T14:00:30", "just now"),
    ("2:00 PM", "2026-11-16T14:02:10", "2 min ago"),
    ("2:00 PM", "2026-11-16T15:00:00", "1 h ago"),
    ("8:31 AM", "2026-11-16T20:45:00", "12 h ago"),
    ("11:58 PM", "2026-11-16T00:10:00", "12 min ago"),
    ("8:31 AM", "2026-11-16T08:00:00", "yesterday"),
    ("12:05 AM", "2026-11-16T00:10:00", "5 min ago"),
    ("12:05 PM", "2026-11-16T12:06:00", "1 min ago"),
    ("14:02", "2026-11-16T14:04:00", "2 min ago"),
    ("soon", "2026-11-16T14:04:00", "soon"),
])
def test_rel_time(last, now, want):
    assert rel(last, now) == want


def test_initials_badge_and_argv():
    assert js("More.js", "M.initials('Alex Rivera')") == "AR"
    assert js("More.js", "M.initials('Family')") == "F"
    assert js("More.js", "M.initials('three word name')") == "TW"
    assert js("More.js", "M.initials('Chat ending 4567')") == ""
    assert js("More.js", "M.initials('\\ud83c\\udf89 party')") == "P"
    assert js("More.js", "M.badgeText(0)") == "" and js("More.js", "M.badgeText(7)") == "7"
    assert js("More.js", "M.badgeText(120)") == "99+" and js("More.js", "M.badgeText('x')") == ""
    assert js("More.js", "M.dayflowArgv('pause')") == ["dayflow", "pause"]
    assert js("More.js", "M.dayflowArgv('resume')") == ["dayflow", "resume"]
    assert js("More.js", "M.dayflowArgv('daemon')") == [] and js("More.js", "M.dayflowArgv(null)") == []


def test_dayflow_view_states():
    now = "new Date('2026-11-16T20:45:00').getTime()"
    base = {"state": "recording", "paused": False, "framesToday": 802, "lastFrame": "8:43 PM", "pending": 0,
            "storage": "18.4 GB", "panel": True}
    v = js("More.js", f"M.dayflowView({json.dumps(base)}, {now})")
    assert v == {"state": "recording", "title": "Recording", "action": "pause", "frames": "802", "last": "2 min ago",
                 "storage": "18.4 GB", "pending": 0, "panel": True}
    p = js("More.js", f"M.dayflowView({json.dumps({**base, 'paused': True, 'pending': 3, 'lastFrame': ''})}, {now})")
    assert p["state"] == "paused" and p["action"] == "resume" and p["title"] == "Paused"
    assert p["pending"] == 3 and p["last"] == "none yet"
    idle = js("More.js", f"M.dayflowView({json.dumps({**base, 'state': 'stopped', 'panel': False})}, {now})")
    assert idle["state"] == "idle" and idle["action"] == "" and idle["title"] == "Stopped" and idle["panel"] is False
    assert js("More.js", f"M.dayflowView(null, {now})") is None


# ---- Fonts and glyphs ----

def test_font_family_choice():
    assert js("Fonts.js", "M.family(true, 'JetBrainsMono Nerd Font', ['Adwaita Sans', 'x'])") == "Adwaita Sans"
    assert js("Fonts.js", "M.family(true, 'mono', ['x'])") == "mono"
    assert js("Fonts.js", "M.family(true, 'mono', null)") == "Adwaita Sans"
    assert js("Fonts.js", "M.family(false, 'mono', ['Adwaita Sans'])") == "mono"
    assert js("Fonts.js", "M.family(undefined, 'mono', ['Adwaita Sans'])") == "mono"


def test_page_and_profile_glyphs_exist():
    g = js("Glyphs.js", "M.GLYPHS")
    for pid in ("messages", "dayflow", "shots", "settings", "nonsense"):
        assert js("Glyphs.js", f"M.pageGlyph({json.dumps(pid)})") != ""
    assert js("Glyphs.js", "M.pageGlyph('messages')") == g["message"]
    assert js("Glyphs.js", "M.profileGlyph('power-saver')") == g["leaf"]
    assert js("Glyphs.js", "M.profileGlyph('performance')") == g["speed"]


# ---- helper: profiles come from `powerprofilesctl list`, never while the daemon is down ----

HELPER = PLUGIN / "bin/island-status"


def fake(bindir: Path, name: str, body: str) -> None:
    p = bindir / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def run_system(tmp_path: Path, tools):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    root = tmp_path / "root"
    (root / "proc").mkdir(parents=True, exist_ok=True)
    (root / "proc/stat").write_text("cpu 1 1 1 1 1 1 1\n")
    for name, body in tools.items():
        fake(bindir, name, body)
    r = subprocess.run(["/usr/bin/python3", str(HELPER), "system", "--root", str(root), "--cpu-sample", "0"],
                       capture_output=True, text=True, timeout=20, check=False,
                       env={"HOME": str(home), "PATH": str(bindir)})
    return json.loads(r.stdout)


PPD = 'case "$1" in get) echo balanced;; list) printf "  performance:\\n      CpuDriver: x\\n* balanced:\\n  power-saver:\\n";; esac'


def test_helper_profiles_header_lines_only(tmp_path):
    out = run_system(tmp_path, {"powerprofilesctl": PPD})
    assert out["profile"] == "balanced"
    assert out["profiles"] == "  performance:\n* balanced:\n  power-saver:"
    assert "CpuDriver" not in json.dumps(out)


def test_helper_skips_profiles_when_daemon_is_down(tmp_path):
    out = run_system(tmp_path, {"powerprofilesctl": PPD, "systemctl": "exit 3"})
    assert out["profile"] is None and out["profiles"] is None


def test_helper_profiles_with_active_daemon(tmp_path):
    out = run_system(tmp_path, {"powerprofilesctl": PPD, "systemctl": "exit 0"})
    assert out["profile"] == "balanced" and out["profiles"].count("\n") == 2


def test_font_family_accepts_list_like_sequences():
    # Qt.fontFamilies() is a sequence, not an Array.
    assert js("Fonts.js", "M.family(true, 'mono', {length: 1, 0: 'x'})") == "mono"
    assert js("Fonts.js", "M.family(true, 'mono', {length: 2, 0: 'x', 1: 'Adwaita Sans'})") == "Adwaita Sans"


def test_agent_marks_resolve_by_file_at_run_time():
    assert js("Agents.js", "M.assetCandidates('antigravity', false)") == [
        "file:///usr/share/omarchy/shell/plugins/agents/assets/agy.svg"]
    assert js("Agents.js", "M.assetCandidates('claude-code', true)") == [
        "file:///usr/share/omarchy/shell/plugins/agents/assets/claude-light.svg",
        "file:///usr/share/omarchy/shell/plugins/agents/assets/claude.svg"]
    assert js("Agents.js", "M.assetCandidates('../x', false)") == []
    assert js("Agents.js", "M.assetCandidates('', false)") == []
    assert js("Agents.js", "M.isLight(0.1, 0.1, 0.1)") is False
    assert js("Agents.js", "M.isLight(0.95, 0.95, 0.95)") is True
