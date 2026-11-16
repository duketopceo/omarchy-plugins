"""Calendar.js: the next-event activity for the Island (node)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Calendar.js"
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")

MIN = 60_000
# js() runs node with TZ=UTC, so clock() output is deterministic.
T0 = 1_794_820_920_000  # 2026-11-16 09:22:00 UTC


def js(expr: str):
    script = f"const C=require({json.dumps(str(MOD))});console.log(JSON.stringify({expr}));"
    r = subprocess.run([NODE, "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={**os.environ, "TZ": "UTC"})
    return json.loads(r.stdout)


def ev(title, start_min, length_min=30, url=""):
    return {"title": title, "start": T0 + start_min * MIN, "end": T0 + (start_min + length_min) * MIN, "url": url}


def activity(events, now=T0):
    return js(f"C.activity({json.dumps(events)}, {now})")


def test_t0_is_0922_utc():
    assert js(f"new Date({T0}).toISOString()") == "2026-11-16T09:22:00.000Z"


def test_ae1_countdown_in_ear_and_card_row():
    a = activity([ev("Standup", 8)])
    assert a["active"] is True and a["id"] == "calendar"
    assert a["text"] == "in 8m"
    assert a["card"] == "Standup · 09:30"
    assert a.get("cardOnly") is not True


def test_outside_ten_minutes_is_card_only():
    a = activity([ev("Standup", 11)])
    assert a["active"] is True and a["cardOnly"] is True
    assert a["card"] == "Standup · 09:33"


def test_ten_minutes_exactly_counts_down():
    assert activity([ev("x", 10)])["text"] == "in 10m"


def test_partial_minute_rounds_up():
    a = js(f"C.activity([{{title:'x',start:{T0 + 8 * MIN + 1000},end:{T0 + 40 * MIN},url:''}}], {T0})")
    assert a["text"] == "in 9m"


def test_started_event_shows_now_for_ten_minutes():
    a = activity([ev("Standup", -3)])
    assert a["text"] == "now" and a.get("cardOnly") is not True
    b = activity([ev("Long", -12, 60)])
    assert b["cardOnly"] is True and b["text"] == "now"


def test_ended_event_skipped_for_next():
    a = activity([ev("Done", -40, 30), ev("Next", 5)])
    assert a["card"].startswith("Next")


def test_short_event_ends_before_ten_minutes():
    a = activity([ev("Short", -4, 3)])
    assert a["active"] is False


def test_no_events_inactive():
    assert activity([])["active"] is False
    assert js(f"C.activity(null, {T0})")["active"] is False


def test_url_only_when_allowlisted_https():
    assert activity([ev("x", 5, url="https://meet.google.com/abc-defg-hij")])["url"] == "https://meet.google.com/abc-defg-hij"
    assert activity([ev("x", 5, url="https://us02web.zoom.us/j/1")])["url"] == "https://us02web.zoom.us/j/1"
    for bad in ["http://meet.google.com/a", "https://meet.google.com.evil.example/a",
                "https://zoom.us@evil.example/j/1", "https://evilzoom.us/j/1", "javascript:alert(1)", "",
                "https://evil.example\\.zoom.us/j/1", "https://evil.example%2f.zoom.us/j/1"]:
        assert activity([ev("x", 5, url=bad)])["url"] == "", bad


def test_long_running_event_does_not_hide_upcoming_meeting():
    # A 3 h block that started 110 min ago plus a meeting in 5 min.
    a = activity([ev("Focus block", -110, 180), ev("Standup", 5, url="https://meet.google.com/abc-defg-hij")])
    assert a["text"] == "in 5m" and a["card"].startswith("Standup")
    assert a["url"] == "https://meet.google.com/abc-defg-hij"


def test_long_running_event_shown_when_nothing_else():
    a = activity([ev("Focus block", -110, 180)])
    assert a["active"] is True and a["cardOnly"] is True and a["card"].startswith("Focus block")


def test_just_started_event_beats_later_one():
    a = activity([ev("Started", -3), ev("Later", 30)])
    assert a["text"] == "now" and a["card"].startswith("Started")


def test_allowlist_matches_helper():
    # Calendar.js re-checks the helper's links; the two host lists must agree.
    import ast
    helper = MOD.parent / "bin/island-calendar"
    tree = ast.parse(helper.read_text())
    py = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) \
                and node.targets[0].id in ("MEETING_HOSTS", "SUFFIX_HOSTS"):
            py[node.targets[0].id] = sorted(ast.literal_eval(node.value))
    assert py == {"MEETING_HOSTS": sorted(js("C.HOSTS")), "SUFFIX_HOSTS": sorted(js("C.SUFFIX_HOSTS"))}


def test_next_event_is_earliest_by_start():
    a = activity([ev("Later", 50), ev("Sooner", 20)])
    assert a["card"].startswith("Sooner")


def test_card_title_trimmed():
    a = activity([ev("A" * 300, 5)])
    assert len(a["card"]) < 120
