"""More.js: Messages (Blip), Dayflow and Shots for the More pages (node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/More.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def js(expr: str):
    script = f"const M=require({json.dumps(str(MOD))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ})
    return json.loads(r.stdout)


STATE = {"unreadCounts": {"+15551234567": 3, "chat-g": 2, "+15550000000": 0, "muted-1": 4},
         "groups": {"chat-g": {"name": "Family", "guid": "x", "participants": ["+1"]}},
         "mutedChats": ["muted-1"], "watermark": "w", "toasted": ["secret text"]}


def messages(state):
    text = state if isinstance(state, str) else json.dumps(state)
    return js(f"M.messages({json.dumps(text)})")


def test_messages_unread_rows_named_and_masked():
    m = messages(STATE)
    assert m["ok"] is True and m["unread"] == 5
    assert m["rows"] == [
        {"label": "Chat ending 4567", "value": "3 unread", "muted": False, "chat": "+15551234567",
         "n": 3, "badge": "3", "initials": ""},
        {"label": "Family", "value": "2 unread", "muted": False, "chat": "chat-g",
         "n": 2, "badge": "2", "initials": "F"},
        {"label": "Chat ending ed-1", "value": "4 unread, muted", "muted": True, "chat": "muted-1",
         "n": 4, "badge": "4", "initials": ""}]
    # The handle rides along only so a row can open its chat; it is never drawn.
    assert all("+15551234567" not in r["label"] + r["value"] for r in m["rows"])


@pytest.mark.parametrize("chat,tail", [
    ("+15551234567", "15551234567"),
    ("15551234567", "15551234567"),
    ("iMessage;-;chat123", "iMessage;-;chat123"),
    ("user@example.com", "user@example.com"),
])
def test_blip_chat_argv_is_a_list_with_bare_handle(chat, tail):
    argv = js(f"M.blipChatArgv({json.dumps(chat)}, '/usr/share/omarchy/shell')")
    assert argv == ["qs", "-p", "/usr/share/omarchy/shell", "ipc", "call", "nixfred.blip", "notified", tail]


@pytest.mark.parametrize("chat", ["", "-flag", "+-flag", "has space", "a;rm -rf /", "x" * 257, None])
def test_blip_chat_argv_rejects_unsafe_ids(chat):
    assert js(f"M.blipChatArgv({json.dumps(chat)}, '/usr/share/omarchy/shell')") == []


def test_messages_live_ignores_muted_chats():
    assert messages(STATE)["live"] is True
    only_muted = {"unreadCounts": {"muted-1": 4}, "mutedChats": ["muted-1"]}
    assert messages(only_muted)["live"] is False


def test_messages_junk_is_not_ok():
    assert messages("{nope")["ok"] is False
    assert messages("[]")["ok"] is False
    assert messages({})["live"] is False


def test_dayflow_live_when_recording_or_paused():
    assert js('M.dayflowLive({state: "recording", paused: false})') is True
    assert js('M.dayflowLive({state: "stopped", paused: true})') is True
    assert js('M.dayflowLive({state: "stopped", paused: false})') is False
    assert js("M.dayflowLive(null)") is False


def test_dayflow_rows():
    d = {"state": "recording", "paused": False, "framesToday": 656, "lastFrame": "10:59 AM", "pending": 2,
         "storage": "18.3 GB"}
    assert js(f"M.dayflowRows({json.dumps(d)})") == [
        {"label": "Capture", "value": "Recording"}, {"label": "Frames today", "value": "656"},
        {"label": "Last frame", "value": "10:59 AM"}, {"label": "Blocks pending", "value": "2"},
        {"label": "Storage", "value": "18.3 GB"}]
    assert js(f"M.dayflowRows({json.dumps(dict(d, paused=True))})")[0]["value"] == "Paused"


SHOTS1 = {"items": [{"name": "2026-11-16_09-00-00_b.png", "caption": "new one"},
                    {"name": "2026-11-01_10-00-00_a.png", "caption": "old one"}], "total": 2}
SHOTS2 = {"items": [{"name": "2026-11-16_10-00-00_c.png", "caption": "newest"}] + SHOTS1["items"], "total": 3}


def test_shots_first_read_is_baseline_not_live():
    m = js(f"M.shotsStep(M.shotsInitial(), {json.dumps(SHOTS1)})")
    assert js(f"M.shotsLive({json.dumps(m)})") is False


def test_shots_new_newest_is_live_until_seen():
    m = js(f"M.shotsStep(M.shotsStep(M.shotsInitial(), {json.dumps(SHOTS1)}), {json.dumps(SHOTS2)})")
    assert js(f"M.shotsLive({json.dumps(m)})") is True
    seen = js(f"M.shotsSeen({json.dumps(m)})")
    assert js(f"M.shotsLive({json.dumps(seen)})") is False


def test_shots_rows_caption_and_time():
    assert js(f"M.shotsRows({json.dumps(SHOTS1)})") == [
        {"label": "new one", "value": "Nov 16 09:00", "name": "2026-11-16_09-00-00_b.png"},
        {"label": "old one", "value": "Nov 1 10:00", "name": "2026-11-01_10-00-00_a.png"}]
    assert js("M.shotsRows(null)") == []


def test_shots_empty_first_read_then_first_screenshot_is_live():
    m = js(f"M.shotsStep(M.shotsStep(M.shotsInitial(), {{items: []}}), {json.dumps(SHOTS1)})")
    assert js(f"M.shotsLive({json.dumps(m)})") is True


def test_shots_missing_read_keeps_baseline_and_is_not_live():
    m = js(f"M.shotsStep(M.shotsStep(M.shotsInitial(), {json.dumps(SHOTS1)}), null)")
    assert m["seen"] == SHOTS1["items"][0]["name"]
    assert js(f"M.shotsLive({json.dumps(m)})") is False


def test_more_labels():
    assert js("M.unreadText(0)") == "No unread messages"
    assert js("M.unreadText(2)") == "2 unread"
    assert js('M.dayflowState({state: "", paused: false})') == "Unknown"
    assert js("M.dayflowState(null)") == ""


def test_messages_ignores_bad_counts_and_bad_muted_list():
    m = messages({"unreadCounts": {"a": -2, "b": "x", "c": "3"}, "mutedChats": "c"})
    assert m["unread"] == 3 and m["live"] is True


def test_shots_unavailable_first_read_sets_no_baseline():
    # Snapdex appears later: its existing screenshots are the baseline, not "new".
    m = js(f"M.shotsStep(M.shotsStep(M.shotsInitial(), null), {json.dumps(SHOTS1)})")
    assert js(f"M.shotsLive({json.dumps(m)})") is False
