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


# ---- Messages tab helpers (scrubbed fixtures) ----

NOW = 1_800_000_000_000  # ms


@pytest.mark.parametrize("delta_ms,expected", [
    (5_000, "now"), (120_000, "2m"), (59 * 60_000, "59m"), (3_600_000, "1h"), (23 * 3_600_000, "23h"),
])
def test_rel_time_short(delta_ms, expected):
    assert run(f"M.relTime({NOW - delta_ms}, {NOW})") == expected


def test_rel_time_days_and_junk():
    two_days = NOW - 2 * 86_400_000
    assert run(f"M.relTime({two_days}, {NOW})") in {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"}
    old = run(f"M.relTime({NOW - 30 * 86_400_000}, {NOW})")
    assert old.split(" ")[0] in {"Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"}
    assert run(f"M.relTime('', {NOW})") == ""
    assert run(f"M.relTime('nope', {NOW})") == ""
    assert run(f"M.relTime({NOW + 5000}, {NOW})") == "now"  # clock skew never negative
    assert run(f"M.relTime('2026-01-01T00:00:00Z', {NOW})") != ""


@pytest.mark.parametrize("name,expected", [
    ("Ada Lovelace", "AL"), ("ada", "A"), ("Ada B. Cole", "AC"), ("  ", "?"), ("", "?"), ("(555)", "5"),
])
def test_initials(name, expected):
    assert run(f"M.initials({json.dumps(name)})") == expected


def test_hash_color_stable_and_hex():
    a = run("M.hashColor('Ada')")
    assert a == run("M.hashColor('Ada')")
    assert len(a) == 7 and a.startswith("#")
    assert len({run(f"M.hashColor('Person {i}')") for i in range(12)}) > 6


def test_sha256_matches_node_crypto():
    for s in ["", "abc", "+15551230001", "héllo", "x" * 200]:
        js = (f"const M=require({json.dumps(str(MODULE))});const c=require('crypto');"
              f"const s={json.dumps(s)};console.log(M.sha256(s)===c.createHash('sha256').update(s).digest('hex'))")
        out = subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout.strip()
        assert out == "true", s


def test_avatar_key_normalizes_and_list_parse():
    k = run("M.avatarKey(' Person@Example.com ')")
    assert k == run("M.avatarKey('person@example.com')") and len(k) == 32
    listing = f"{k}.jpg\n{'0' * 32}.none\njunk.jpg\n"
    assert run(f"M.parseAvatarList({json.dumps(listing)})") == {k: True}


def threads_json():
    return json.dumps([
        {"chat": A, "name": "Ada Lovelace", "last_text": "lunch   at\nnoon?", "unread": 2, "last_ts": "2026-01-02T00:00:00Z"},
        {"chat": B, "name": "Bo Park", "last_text": "thanks!", "unread": 0, "last_ts": "2026-01-03T00:00:00Z"},
        {"chat": G, "name": G, "last_text": "meeting moved", "unread": 1, "last_ts": "2026-01-01T00:00:00Z"},
    ])


def test_build_rows_model():
    rows = run(f"M.buildRows(M.parseThreads({json.dumps(threads_json())}), null, 10)")
    assert [r["name"] for r in rows] == ["Bo Park", "Ada Lovelace", "Group"]  # newest first, no raw handles or ids
    ada = rows[1]
    assert ada["preview"] == "lunch at noon?" and ada["unread"] == 2 and ada["initials"] == "AL"
    assert ada["ts"] == "2026-01-02T00:00:00Z" and len(ada["avatar"]) == 32 and ada["color"].startswith("#")
    assert run("M.totalUnread(" + json.dumps(rows) + ")") == 3


def test_build_rows_fallback_without_threads():
    st = f"M.parseState({json.dumps(state({A: 2, G: 1}, {G: {'name': 'Team'}}))})"
    rows = run(f"M.buildRows(null, {st}, 10)")
    assert {r["name"] for r in rows} == {"Conversation", "Team"} and all(r["preview"] == "" for r in rows)
    assert run("M.buildRows(null, null, 10)") == []


def test_filter_rows():
    rows = json.dumps(run(f"M.buildRows(M.parseThreads({json.dumps(threads_json())}), null, 10)"))
    assert [r["name"] for r in run(f"M.filterRows({rows}, ' ADA ')")] == ["Ada Lovelace"]
    assert [r["name"] for r in run(f"M.filterRows({rows}, 'moved')")] == ["Group"]
    assert run(f"M.filterRows({rows}, 'zzz')") == []
    assert len(run(f"M.filterRows({rows}, '')")) == 3


def test_goto_arg_and_offline_label():
    assert run(f"M.gotoArg({json.dumps(A)})") == A[1:]
    assert run(f"M.gotoArg({json.dumps(G)})") == G
    assert run("M.offlineLabel(true, true)") == ""
    assert run("M.offlineLabel(true, false)") == "Mac offline"
    assert run("M.offlineLabel(false, false)") == "Blip not reachable"
