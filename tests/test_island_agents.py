"""Agents: bin/island-agents (helper) and Agents.js (node)."""
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

PLUGIN = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island"
SCRIPT = PLUGIN / "bin/island-agents"
MOD = PLUGIN / "Agents.js"
NODE = shutil.which("node")

HERDR = {"spaces": [
    {"id": "s1", "name": "Home", "machine": None, "tabs": [
        {"id": "t1", "name": "shell", "terminals": [{"terminal": "term-1", "pane": "p", "status": None, "app": None,
                                                      "name": None, "sub_agents": []}]},
        {"id": "t2", "name": "codex", "terminals": [{"terminal": "term-2", "pane": "p", "status": "working",
                                                      "app": "codex", "name": None, "sub_agents": []}]},
        {"id": "t3", "name": "wisp", "terminals": [{"terminal": "term-3", "pane": "p", "status": "blocked",
                                                     "app": "claude-code", "name": None, "sub_agents": [
                                                         {"terminal": "term-4", "status": "done", "app": "claude-code"}]}]},
    ]},
    {"id": "s2", "name": "kimba", "machine": "cyberpowa", "tabs": [
        {"id": "t4", "name": "OpenCode", "terminals": [{"terminal": "term-5", "status": "idle", "app": "opencode"}]}]},
], "recent": []}

CLIENTS = [{"class": "herdr-app", "pid": 500, "address": "0xaaab73eb5d80", "title": "Herdr"},
           {"class": "foot", "pid": 600, "address": "0xaaab7473bcd0", "title": "x"}]


def fake(bindir: Path, name: str, body: str) -> None:
    p = bindir / name
    p.write_text("#!/bin/sh\n" + body + "\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)


def proc(root: Path, pid: int, ppid: int, comm: str = "x") -> None:
    d = root / "proc" / str(pid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "stat").write_text(f"{pid} ({comm} with) spaces) S {ppid} 1 1 0 -1\n")


def session(home: Path, pid: int, **fields) -> None:
    d = home / ".claude/sessions"
    d.mkdir(parents=True, exist_ok=True)
    body = {"pid": pid, "sessionId": "secret-id", "cwd": "/home/x/Documents/wisp", "kind": "interactive",
            "messagingSocketPath": "/tmp/sock", "name": "wisp", "status": "busy"}
    body.update(fields)
    (d / f"{pid}.json").write_text(json.dumps(body))


def run(tmp_path: Path, tools=None):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    root = tmp_path / "root"
    (root / "proc").mkdir(parents=True, exist_ok=True)
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    for name, body in (tools or {}).items():
        fake(bindir, name, body)
    env = {"HOME": str(home), "PATH": str(bindir)}
    r = subprocess.run([sys.executable, str(SCRIPT), "--root", str(root)], check=False, env=env,
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def herdr_tool():
    return {"herdr-app": f"[ \"$1\" = ls ] && echo '{json.dumps(HERDR)}'",
            "hyprctl": f"echo '{json.dumps(CLIENTS)}'"}


# ---- helper ----
def test_nothing_detected(tmp_path):
    assert run(tmp_path) == {"ok": True, "herdr": False, "claude": False, "sessions": []}


def test_herdr_terminals_flattened_with_window(tmp_path):
    out = run(tmp_path, herdr_tool())
    assert out["herdr"] is True
    ids = [s["id"] for s in out["sessions"]]
    # plain shell dropped; needs-you first, then working, done, idle (the cap keeps that order)
    assert ids == ["herdr:term-3", "herdr:term-2", "herdr:term-4", "herdr:term-5"]
    s3 = out["sessions"][0]
    assert s3 == {"source": "herdr", "id": "herdr:term-3", "app": "claude-code", "name": "wisp", "where": "Home",
                  "status": "blocked", "terminal": "term-3", "address": "0xaaab73eb5d80"}
    assert out["sessions"][3]["where"] == "kimba @ cyberpowa"


def test_claude_sessions_live_only_and_window_by_parent_chain(tmp_path):
    root = tmp_path / "root"
    proc(root, 700, 650)
    proc(root, 650, 600)
    proc(root, 600, 1)
    home = tmp_path / "home"
    session(home, 700, status="waiting")
    session(home, 701)  # dead pid: no /proc entry
    out = run(tmp_path, {"hyprctl": f"echo '{json.dumps(CLIENTS)}'"})
    assert out["claude"] is True
    assert out["sessions"] == [{"source": "claude", "id": "claude:700", "app": "claude", "name": "wisp",
                                "where": "wisp", "status": "waiting", "terminal": "", "address": "0xaaab7473bcd0"}]
    assert "secret-id" not in json.dumps(out) and "/tmp/sock" not in json.dumps(out)


def test_claude_background_session_has_no_window(tmp_path):
    root = tmp_path / "root"
    proc(root, 800, 1)
    session(tmp_path / "home", 800, kind="bg", name="nuclear sim", status="idle")
    out = run(tmp_path, {"hyprctl": "echo '[]'"})
    assert out["sessions"][0]["address"] == "" and out["sessions"][0]["name"] == "nuclear sim"


def test_herdr_failure_is_not_fatal(tmp_path):
    out = run(tmp_path, {"herdr-app": "exit 3"})
    assert out["herdr"] is True and out["sessions"] == []


def test_junk_session_file_skipped(tmp_path):
    d = tmp_path / "home/.claude/sessions"
    d.mkdir(parents=True)
    (d / "1.json").write_text("{not json")
    (d / "2.json").write_text("[1,2]")
    out = run(tmp_path)
    assert out["claude"] is True and out["sessions"] == []


# ---- Agents.js ----
def js(expr: str):
    if NODE is None:
        pytest.skip("node not installed")
    script = f"const A=require({json.dumps(str(MOD))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


def s(source, sid, status, name="x", app="claude", address="", terminal=""):
    return {"source": source, "id": sid, "app": app, "name": name, "where": "w", "status": status,
            "terminal": terminal, "address": address}


@pytest.mark.parametrize("source,status,want", [
    ("herdr", "blocked", "needs"), ("herdr", "working", "working"), ("herdr", "done", "done"),
    ("herdr", None, "idle"), ("claude", "waiting", "needs"), ("claude", "needs_input", "needs"),
    ("claude", "busy", "working"), ("claude", "idle", "idle"), ("claude", "weird", "idle"),
])
def test_status_vocabulary(source, status, want):
    assert js(f"A.normStatus({json.dumps(status)})") == want


def test_rows_needs_you_first_then_working_done_idle_then_name():
    data = {"ok": True, "sessions": [s("herdr", "a", "working", "b"), s("claude", "b", "idle", "a"),
                                     s("herdr", "c", "blocked", "z"), s("claude", "d", "waiting", "m"),
                                     s("herdr", "e", "done", "q"), s("herdr", "f", "working", "a")]}
    rows = js(f"A.rows({json.dumps(data)})")
    assert [r["key"] for r in rows] == ["d", "c", "f", "a", "e", "b"]
    assert rows[0]["statusLabel"] == "needs you"


def test_row_labels():
    r = js(f"A.rows({json.dumps({'sessions': [s('herdr', 'a', 'working', 'wisp', app='claude-code')]})})")[0]
    assert r["app"] == "Claude" and r["title"] == "wisp" and r["where"] == "w" and r["status"] == "working"


def test_rows_of_junk_is_empty():
    assert js("A.rows(null)") == []
    assert js("A.rows({sessions: 'x'})") == []


def test_counts_text():
    data = {"sessions": [s("herdr", "a", "blocked"), s("herdr", "b", "working"), s("herdr", "c", "working")]}
    assert js(f"A.countsText(A.rows({json.dumps(data)}))") == "1 needs you · 2 working"
    assert js("A.countsText([])") == ""


def test_focus_commands_claude_window():
    row = js(f"A.rows({json.dumps({'sessions': [s('claude', 'k', 'busy', address='0xaaab7473bcd0')]})})[0]")
    cmds = js(f"A.focusCommands({json.dumps(row)})")
    assert cmds == [["hyprctl", "dispatch", 'hl.dsp.focus({ window = "address:0xaaab7473bcd0" })']]


def test_focus_commands_herdr_terminal_then_window():
    row = js(f"A.rows({json.dumps({'sessions': [s('herdr', 'k', 'busy', address='aaab73eb5d80', terminal='term-3')]})})[0]")
    cmds = js(f"A.focusCommands({json.dumps(row)})")
    assert cmds == [["herdr-app", "do", "agent.focus", "--terminal", "term-3"],
                    ["hyprctl", "dispatch", 'hl.dsp.focus({ window = "address:0xaaab73eb5d80" })']]


def test_focus_commands_reject_bad_address_and_none_without_target():
    row = js(f"A.rows({json.dumps({'sessions': [s('claude', 'k', 'busy', address='0x1\" }) os.exit(')]})})[0]")
    assert js(f"A.focusCommands({json.dumps(row)})") == []
    assert row["focusable"] is False
    row2 = js(f"A.rows({json.dumps({'sessions': [s('claude', 'k', 'busy')]})})[0]")
    assert js(f"A.focusCommands({json.dumps(row2)})") == []


@pytest.mark.parametrize("terminal", ["-rf", "--terminal", "a b", ""])
def test_focus_commands_reject_odd_terminal_ids(terminal):
    rows = js(f"A.rows({json.dumps({'sessions': [s('herdr', 'k', 'busy', terminal=terminal)]})})")
    assert js(f"A.focusCommands({json.dumps(rows[0])})") == []
    assert rows[0]["focusable"] is False


def test_malformed_herdr_shape_does_not_drop_claude_sessions(tmp_path):
    root = tmp_path / "root"
    proc(root, 900, 1)
    session(tmp_path / "home", 900, status="busy")
    bad = json.dumps({"spaces": [{"name": "x", "tabs": 1}, {"name": "y", "tabs": [{"terminals": 5}]},
                                 {"name": "z", "tabs": [{"terminals": [{"terminal": "t", "app": "codex",
                                                                         "sub_agents": "no"}]}]}]})
    out = run(tmp_path, {"herdr-app": f"echo '{bad}'", "hyprctl": "echo '[]'"})
    ids = [x["id"] for x in out["sessions"]]
    assert "claude:900" in ids and "herdr:t" in ids


def test_session_cap_keeps_needs_you_sessions(tmp_path):
    many = {"spaces": [{"name": "s", "tabs": [{"name": "t", "terminals":
            [{"terminal": f"w{i}", "status": "working", "app": "codex"} for i in range(45)]
            + [{"terminal": "late", "status": "blocked", "app": "codex"}]}]}]}
    out = run(tmp_path, {"herdr-app": f"echo '{json.dumps(many)}'", "hyprctl": "echo '[]'"})
    assert len(out["sessions"]) == 40
    assert "herdr:late" in [x["id"] for x in out["sessions"]]
