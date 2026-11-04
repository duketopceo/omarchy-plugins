"""Messages.js for the notch island, run through node. Fixtures are scrubbed."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MODULE = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch/Messages.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = f"const M=require({json.dumps(str(MODULE))});console.log(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


def state(counts, groups=None):
    return json.dumps({"unreadCounts": counts, "groups": groups or {}, "toasted": ["x"]})


A = "+15551230001"
B = "person@example.com"
G = "chat000000000000000000000000000001"


def test_parse_state():
    r = run(f"M.parseState({json.dumps(state({A: 2, B: 0, G: 1}, {G: {'name': 'Team'}}))})")
    assert r == {"ok": True, "unread": 3, "counts": {A: 2, G: 1}, "groups": {G: "Team"}}


@pytest.mark.parametrize("text", ["", "nope", "[]", "null"])
def test_parse_state_junk(text):
    assert run(f"M.parseState({json.dumps(text)})")["ok"] is False


def test_parse_status():
    r = run('M.parseStatus("online=true unread=4 leader=true window=hidden threads=9 healthy=true push=true")')
    assert r == {"online": True, "leader": True, "unread": 4, "threads": 9}
    assert run('M.parseStatus("online=false unread=0 leader=true")')["online"] is False
    assert run('M.parseStatus("Target not found.")') is None


def test_parse_threads_and_refusal():
    raw = json.dumps([
        {"chat": A, "name": "Ada", "last_text": "hi", "unread": 1, "last_ts": "2026-01-01T00:00:01"},
        {"chat": B, "name": "Bo", "last_text": "yo", "unread": 0, "last_ts": "2026-01-02T00:00:01"},
    ])
    r = run(f"M.parseThreads({json.dumps(raw)})")
    assert [t["name"] for t in r] == ["Bo", "Ada"]
    assert run('M.parseThreads("blip: automation=off - set it")') is None


def test_allowlist_matching():
    allow = run(f"M.parseAllowlist({json.dumps(json.dumps({'allow': ['+1 (555) 123-0001', 'Person@Example.com']}))})")
    assert run(f"M.isAllowed({json.dumps(A)}, {json.dumps(allow)})") is True
    assert run(f"M.isAllowed({json.dumps(B)}, {json.dumps(allow)})") is True
    assert run(f"M.isAllowed('+15559990000', {json.dumps(allow)})") is False
    assert run("M.isAllowed('x', [])") is False


def test_new_message_detection():
    prev = f"M.parseState({json.dumps(state({A: 1, B: 1}))})"
    nxt = f"M.parseState({json.dumps(state({A: 1, B: 3, G: 1}))})"
    r = run(f"M.newMessages({prev}, {nxt}, [M.normHandle({json.dumps(B)})])")
    assert sorted(r, key=lambda x: x["chat"]) == sorted(
        [{"chat": B, "delta": 2, "allowed": True}, {"chat": G, "delta": 1, "allowed": False}],
        key=lambda x: x["chat"])
    # first snapshot and read-downs are not arrivals
    assert run(f"M.newMessages(null, {nxt}, [])") == []
    assert run(f"M.newMessages({nxt}, {prev}, [])") == []


def test_sender_name_never_a_handle():
    groups = json.dumps({G: "Team"})
    threads = json.dumps([{"chat": A, "name": A}, {"chat": B, "name": "Bo"}])
    assert run(f"M.senderName({json.dumps(G)}, {groups}, [])") == "Team"
    assert run(f"M.senderName({json.dumps(B)}, {{}}, {threads})") == "Bo"
    assert run(f"M.senderName({json.dumps(A)}, {{}}, {threads})") == ""


@pytest.mark.parametrize("name,preview,expected", [
    ("Ada", "see you at the park later today ok", "Ada: see you at the park…"),
    ("Ada", "ok", "Ada: ok"),
    ("Ada", "", "Ada"),
    ("", "hello there", "hello there"),
    ("", "", "New message"),
    ("A" * 30, "hi", "A" * 17 + "…: hi"),
])
def test_format_text(name, preview, expected):
    assert run(f"M.formatText({json.dumps(name)}, {json.dumps(preview)})") == expected


def test_step_flash_and_expiry():
    arr = [{"chat": A, "delta": 1, "allowed": True}]
    m = run(f"M.step(M.initial(), 2, {json.dumps(arr)}, 'Ada: hi', 1000)")
    assert m == {"unread": 2, "flashUntil": 9000, "text": "Ada: hi"}
    assert run(f"M.isActive({json.dumps(m)}, 8999)") is True
    assert run(f"M.isActive({json.dumps(m)}, 9000)") is False
    quiet = run(f"M.step(M.initial(), 3, [{{chat:'x',delta:1,allowed:false}}], '', 1000)")
    assert quiet["unread"] == 3 and quiet["flashUntil"] == 0


def test_badge_and_tab_rows():
    assert [run(f"M.badgeText({n})") for n in (0, 3, 150)] == ["", "3", "99+"]
    st = f"M.parseState({json.dumps(state({A: 2, G: 1}, {G: {'name': 'Team'}}))})"
    rows = run(f"M.tabRows(null, {st}, 5)")
    assert {r["name"] for r in rows} == {"Conversation", "Team"}
    th = json.dumps([{"chat": A, "name": A, "last_text": "one two", "unread": 1, "last_ts": "1"}])
    assert run(f"M.tabRows(M.parseThreads({json.dumps(th)}), null, 5)")[0]["name"] == "Contact"
