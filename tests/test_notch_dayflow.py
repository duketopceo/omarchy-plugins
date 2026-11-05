"""Dayflow.js for the notch island (local Dayflow customization), run through node."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

NOTCH = Path(__file__).resolve().parents[1] / "plugins/io.github.duketopceo.notch"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def run(expr):
    js = (
        f"const D=require({json.dumps(str(NOTCH / 'Dayflow.js'))});"
        f"const T=require({json.dumps(str(NOTCH / 'Tabs.js'))});"
        f"const S=require({json.dumps(str(NOTCH / 'Settings.js'))});"
        f"const A=require({json.dumps(str(NOTCH / 'Activity.js'))});"
        f"console.log(JSON.stringify({expr}));"
    )
    return json.loads(subprocess.run(["node", "-e", js], check=True, capture_output=True, text=True).stdout)


STATUS = {"active_app": "herdr-app", "blocks_done": 26, "blocks_pending": 1, "capture_state": "recording",
          "frames_today": 844, "last_frame": "2:56 PM", "paused": False, "storage_text": "16.2 GB"}
NOW = 1_800_000_000
DAY0 = NOW - 15 * 3600   # local midnight stand-in: now is 3 PM


def block(start_min, cat, productive=True, app="Herdr", title="Working with Dana Smith"):
    s = DAY0 + start_min * 60
    return {"start_ts": s, "end_ts": s + 900, "start": "a", "end": "b", "title": title,
            "summary": "You talked to Dana Smith", "category": cat, "app_name": app, "productive": productive}


# Newest first, as `dayflow today --json` prints them.
TODAY = {"date": "x", "blocks": [
    block(14 * 60 + 30, "coding"),
    block(14 * 60 + 15, "coding", app="Chromium"),
    block(14 * 60, "communication", productive=False, app="Chromium"),
    block(9 * 60, "coding"),
    {"start_ts": 0, "end_ts": 0, "category": "x"},
    "junk",
]}


def test_parse_status_and_toggle():
    s = run(f"D.parseStatus({json.dumps(json.dumps(STATUS))})")
    assert s["ok"] and s["recording"] and not s["paused"] and s["frames"] == 844 and s["blocksPending"] == 1
    p = run(f"D.parseStatus({json.dumps(json.dumps(dict(STATUS, capture_state='paused', paused=True)))})")
    assert p["paused"] and not p["recording"]
    assert run(f"D.toggleArgs('/b/dayflow', {json.dumps(s)})") == ["/b/dayflow", "pause"]
    assert run(f"D.toggleArgs('/b/dayflow', {json.dumps(p)})") == ["/b/dayflow", "resume"]
    for junk in ("", "nope", "[]", "{}"):
        assert run(f"D.parseStatus({json.dumps(junk)}).ok") is False
    assert run("D.stateText(D.parseStatus(''))") == "Dayflow unavailable"


def test_parse_today_orders_blocks_and_computes_focus_apps_and_current():
    t = run(f"D.parseToday({json.dumps(json.dumps(TODAY))}, {NOW})")
    assert t["ok"] and len(t["blocks"]) == 4
    assert [b["start"] for b in t["blocks"]] == sorted(b["start"] for b in t["blocks"])
    assert t["trackedMin"] == 60 and t["productiveMin"] == 45 and t["focusPct"] == 75
    assert t["topApps"] == [{"name": "Chromium", "minutes": 30}, {"name": "Herdr", "minutes": 30}]   # ties: by name
    assert t["current"]["category"] == "coding" and t["currentIndex"] == 3
    assert t["streakMin"] == 30   # two back-to-back coding blocks
    stale = run(f"D.parseToday({json.dumps(json.dumps(TODAY))}, {NOW + 3 * 3600})")
    assert stale["current"] is None and stale["streakMin"] == 0
    assert run("D.parseToday('', 1).ok") is False and run("D.parseToday('{\"blocks\":[]}', 1).focusPct") == -1


def test_category_colors_match_dayflow_and_unknown_is_other():
    assert run("D.categoryColor('coding')") == "#388bee"
    assert run("D.categoryColor('Communication')") == "#f27326"
    assert run("D.categoryColor('weird')") == run("D.CATEGORY_COLORS.other")
    assert run("D.categoryColor(null)") == "#9ca3af"
    assert run("D.categoryLabel('coding')") == "Coding" and run("D.categoryLabel('')") == "Other"


def test_strip_segments_fit_the_window_and_mark_current():
    st = run(f"D.strip(D.parseToday({json.dumps(json.dumps(TODAY))}, {NOW}), {NOW}, {DAY0})")
    assert st["from"] == DAY0 + 8 * 3600 and st["to"] == DAY0 + 15 * 3600
    for seg in st["segments"]:
        assert 0 <= seg["x"] <= 1 and 0 < seg["w"] <= 1 and seg["color"].startswith("#")
    assert [s["current"] for s in st["segments"]] == [False, False, False, True]
    assert run(f"D.strip(D.emptyToday(), {NOW}, {DAY0}).segments") == []


def test_collapsed_slot_never_shows_titles_or_names():
    s = json.dumps(STATUS)
    t = f"D.parseToday({json.dumps(json.dumps(TODAY))}, {NOW})"
    text = run(f"D.slotText(D.parseStatus({json.dumps(s)}), {t})")
    assert text == "● Coding · 30m"
    assert "Dana" not in text and "Working" not in text
    paused = json.dumps(json.dumps(dict(STATUS, capture_state="paused", paused=True)))
    assert run(f"D.slotText(D.parseStatus({paused}), {t})") == ""
    assert run(f"D.idleViews(['weather'], true, D.parseStatus({json.dumps(s)}), {t})") == ["weather", "dayflow"]
    assert run(f"D.idleViews(['weather'], false, D.parseStatus({json.dumps(s)}), {t})") == ["weather"]
    assert run(f"D.idleViews(['weather'], true, D.parseStatus(''), {t})") == ["weather"]


def test_paused_activity_is_low_priority_and_gated_by_the_setting():
    paused = json.dumps(json.dumps(dict(STATUS, capture_state="paused", paused=True)))
    a = run(f"D.activity(true, D.parseStatus({paused}))")
    assert a["active"] and a["text"] == "Dayflow paused" and a["priority"] == 20
    assert run(f"D.activity(false, D.parseStatus({paused})).active") is False
    assert run(f"D.activity(true, D.parseStatus({json.dumps(json.dumps(STATUS))})).active") is False
    # Media (50), blocked agents (80) and screenshot flashes (30) all beat a paused capture.
    for other in (50, 80, 30):
        pick = run(f"A.pick([D.activity(true, D.parseStatus({paused})), {{id:'x',active:true,priority:{other},text:'t'}}]).id")
        assert pick == "x"
    assert run(f"A.pick([D.activity(true, D.parseStatus({paused}))]).id") == "dayflow"


def test_agents_briefing_forecast():
    agents = {"count": 4, "sessions": [
        {"source": "claude", "title": "fix  the\nnotch", "project": "p", "end": 30},
        {"source": "devin", "title": "kate", "project": "k", "end": 40},
        {"source": "claude", "title": "c", "project": "p", "end": 10},
        {"source": "codex", "title": "", "project": "q", "end": 20}]}
    a = run(f"D.parseAgents({json.dumps(json.dumps(agents))}, 3)")
    assert a["ok"] and a["count"] == 4
    assert a["bySource"][0] == {"source": "Claude", "count": 2}
    assert [x["title"] for x in a["latest"]] == ["kate", "fix the notch", ""]
    b = run(f"D.parseBriefing({json.dumps(json.dumps({'workstreams': [{'name': 'a', 'threads': [1]}, {'name': 'b', 'threads': [1, 2, 3]}]}))}, 3)")
    assert [w["name"] for w in b["workstreams"]] == ["b", "a"] and b["workstreams"][0]["threads"] == 3
    f = run("D.parseForecast(JSON.stringify({weekday:'Friday',items:[{category:'coding',pct:73.8},{category:'meetings',pct:7.1},{category:'x',pct:0.2}]}))")
    assert f["line"] == "Fri forecast: 74% coding · 7% meetings"
    for fn in ("parseAgents", "parseBriefing", "parseForecast"):
        assert run(f"D.{fn}('garbage').ok") is False


def test_throttle_and_tab_setting():
    assert run("D.due(0, 5, 10)") is True and run("D.due(1, 5, 10)") is False and run("D.due(1, 11, 10)") is True
    assert run("D.AGENTS_MS") >= 600000 and run("D.BRIEFING_MS") >= 1800000 and run("D.STATUS_MS") == 10000
    assert run("S.DEFAULTS.dayflow") is False and run("S.field('dayflow').type") == "bool"
    assert "dayflow" not in [t["id"] for t in run("T.visibleTabs(S.resolve(null))")]
    assert "dayflow" in [t["id"] for t in run("T.visibleTabs(S.resolve({dayflow:true}))")]
    assert run("T.byId('dayflow').size") == run("T.byId('home').size") == {"w": 720, "h": 380}
    assert run("D.duration(105)") == "1h 45m" and run("D.duration(60)") == "1h" and run("D.duration(5)") == "5m"
