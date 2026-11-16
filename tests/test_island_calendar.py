"""Calendar.js: the next-event activity for the Island (node)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

MOD = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.island/Calendar.js"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")

MIN = 60_000
# Local midnight is irrelevant: times are rendered with TZ=UTC below.
T0 = 1_794_820_920_000  # 2026-11-16 09:22:00 UTC


def js(expr: str):
    script = f"const C=require({json.dumps(str(MOD))});console.log(JSON.stringify({expr}));"
    r = subprocess.run(["node", "-e", script], capture_output=True, text=True, timeout=20, check=True,
                       env={"TZ": "UTC", "PATH": "/usr/bin:/bin"})
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
                "https://zoom.us@evil.example/j/1", "https://evilzoom.us/j/1", "javascript:alert(1)", ""]:
        assert activity([ev("x", 5, url=bad)])["url"] == "", bad


def test_next_event_is_earliest_by_start():
    a = activity([ev("Later", 50), ev("Sooner", 20)])
    assert a["card"].startswith("Sooner")


def test_card_title_trimmed():
    a = activity([ev("A" * 300, 5)])
    assert len(a["card"]) < 120
